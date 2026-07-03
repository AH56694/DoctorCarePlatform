import os  # 导入 os 模块，用于文件系统操作和路径处理
import requests  # 导入 requests 库，用于下载远程文件（HTTP 请求）
import tempfile  # 导入 tempfile 模块，用于创建临时文件（类似 Java 的 File.createTempFile）
import logging  # 导入日志模块
from typing import List  # 从 typing 导入 List 类型提示（类似 Java 的 List<>）
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, TextLoader, UnstructuredMarkdownLoader  # 导入各种文档加载器：PDF、Word、纯文本、Markdown
from langchain_text_splitters import RecursiveCharacterTextSplitter  # 导入递归字符文本分割器，按分隔符层级递归切分
from langchain_core.documents import Document  # 导入 LangChain 的 Document 类，封装文档内容和元数据
from PIL import Image  # 从 Pillow 库导入 Image 类，用于图片处理
import pytesseract  # 导入 Tesseract OCR 的 Python 封装，用于图片文字识别
from core.text_splitter import AdaptiveChunker, create_chunker  # 从 text_splitter 模块导入自适应分块器和工厂函数
from core.config import config  # 导入全局配置实例

# 配置日志
logger = config.logger  # 使用全局配置中的 logger 实例

# 全局变量，标记Tesseract是否可用
tesseract_available = False  # 布尔标记，初始为 False（模块级全局变量）

# 动态配置Tesseract路径
def setup_tesseract():  # 定义 Tesseract 路径检测和配置函数
    """动态配置Tesseract路径，支持多种安装位置"""  # 函数的 docstring
    global tesseract_available  # global 关键字声明使用全局变量（Python 中函数内修改全局变量必须用 global 声明）
    # 从环境变量读取Tesseract路径
    env_tesseract_path = os.getenv("TESSERACT_PATH")  # 读取环境变量中的 Tesseract 路径
    possible_paths = []  # 初始化候选路径列表

    # 如果环境变量设置了路径，优先使用
    if env_tesseract_path:  # 如果环境变量非空
        possible_paths.append(env_tesseract_path)  # 将环境变量路径添加到候选列表

    # 添加默认路径
    possible_paths.extend([  # extend 批量添加多个路径到列表
        r'C:/Program Files/Tesseract-OCR/tesseract.exe',  # 默认安装路径（r'' 原始字符串，不转义反斜杠）
        r'C:/Program Files (x86)/Tesseract-OCR/tesseract.exe',  # 32位安装路径
        r'E:/Tesseract-OCR/tesseract.exe',  # E盘安装路径
        '/usr/bin/tesseract',  # Linux/Mac
        '/usr/local/bin/tesseract',  # Linux/Mac alternative
    ])

    for path in possible_paths:  # 遍历所有候选路径
        if os.path.exists(path):  # 如果路径存在
            pytesseract.pytesseract.tesseract_cmd = path  # 设置 Tesseract 可执行文件路径
            logger.info(f"Tesseract found at: {path}")  # 记录找到的路径

            # 检查语言包
            tessdata_dir = os.path.join(os.path.dirname(path), 'tessdata')  # os.path.dirname 获取目录部分，os.path.join 拼接 tessdata 子目录
            if os.path.exists(tessdata_dir):  # 如果 tessdata 目录存在
                logger.info(f"Tessdata directory: {tessdata_dir}")  # 记录 tessdata 目录
                # 检查中文语言包
                chi_sim_path = os.path.join(tessdata_dir, 'chi_sim.traineddata')  # 中文简体语言包路径
                eng_path = os.path.join(tessdata_dir, 'eng.traineddata')  # 英文语言包路径

                if os.path.exists(chi_sim_path):  # 如果中文语言包存在
                    logger.info("Chinese language pack found: chi_sim.traineddata")  # 记录找到
                else:
                    logger.warning("Chinese language pack (chi_sim.traineddata) not found!")  # 记录警告

                if os.path.exists(eng_path):  # 如果英文语言包存在
                    logger.info("English language pack found: eng.traineddata")  # 记录找到
                else:
                    logger.warning("English language pack (eng.traineddata) not found!")  # 记录警告
            tesseract_available = True  # 标记 Tesseract 可用
            return  # 找到并配置好后直接返回

    logger.error("Tesseract not found in any known location!")  # 所有路径都没找到
    # 如果找不到，尝试使用系统PATH
    try:
        pytesseract.get_tesseract_version()  # 尝试从系统 PATH 中查找 Tesseract 版本
        logger.info("Tesseract found in system PATH")  # 在系统 PATH 中找到
        tesseract_available = True  # 标记可用
    except Exception as e:  # 捕获异常（系统 PATH 中也没有）
        logger.error(f"Tesseract not found: {e}")  # 记录错误
        logger.warning("Tesseract OCR not installed. Image OCR functionality will be disabled.")  # 记录警告
        tesseract_available = False  # 标记不可用

# 初始化Tesseract
setup_tesseract()  # 模块加载时自动执行 Tesseract 检测和配置

class DocumentParser:  # 定义文档解析器类
    def __init__(self):  # 构造方法
        # 从配置管理模块读取切分配置
        chunk_size = config.CHUNK_SIZE  # 获取文本块最大字符数
        chunk_overlap = config.CHUNK_OVERLAP  # 获取文本块重叠字符数
        min_chunk_size = config.MIN_CHUNK_SIZE  # 获取文本块最小字符数
        chunk_strategy = config.CHUNK_STRATEGY  # 获取切分策略

        # 使用自适应切分器
        self.chunker = create_chunker({  # 调用工厂函数创建切分器实例，传入配置字典
            "chunk_size": chunk_size,  # 文本块最大字符数
            "chunk_overlap": chunk_overlap,  # 重叠字符数
            "min_chunk_size": min_chunk_size,  # 最小字符数
            "strategy": chunk_strategy  # 切分策略名称
        })

        logger.info(f"DocumentParser initialized with strategy: {chunk_strategy}, chunk_size: {chunk_size}")  # 记录初始化信息

    def parse(self, file_path: str) -> List[Document]:  # 定义文档解析方法，返回 Document 列表
        """
        根据文件扩展名选择合适的加载器解析文档，并切分文本。
        支持本地路径和 HTTP/HTTPS URL。
        """
        # 检测是否为 URL(支持带或不带协议头)
        is_url = file_path.startswith(('http://', 'https://')) or \
                 (not os.path.exists(file_path) and
                  ('clouddn.com' in file_path or 'aliyuncs.com' in file_path or '/' in file_path))  # startswith 支持元组参数（匹配任一前缀），\ 是行续符
        temp_file = None  # 临时文件变量，初始为 None

        try:  # try-finally 确保临时文件被清理
            target_path = file_path  # 目标文件路径（本地路径或下载后的临时文件路径）

            # 如果是 URL，先下载到临时文件
            if is_url:  # 如果输入是 URL
                try:
                    # 如果没有协议头，添加 https://
                    download_url = file_path  # 复制 URL
                    if not download_url.startswith(('http://', 'https://')):  # 如果没有协议前缀
                        download_url = 'https://' + download_url  # 添加 https:// 前缀

                    response = requests.get(download_url, stream=True, timeout=30)  # 发送 GET 请求，stream=True 启用流式下载（大文件不会全部加载到内存）
                    response.raise_for_status()  # 检查响应状态码，非 2xx 则抛异常

                    # 推断扩展名，优先从 URL 获取，如果没有则尝试从 Content-Type 或 Content-Disposition 获取
                    # 简单起见，这里假设 URL 包含扩展名
                    ext = os.path.splitext(file_path)[1].lower()  # os.path.splitext 将路径分为 (目录+文件名, 扩展名)，[1] 取扩展名
                    if not ext:  # 如果 URL 中没有扩展名
                        # 尝试从 Content-Type 推断
                        content_type = response.headers.get('Content-Type', '').lower()  # 获取响应头中的 Content-Type
                        if 'pdf' in content_type:  # 如果是 PDF 类型
                            ext = '.pdf'  # 设置扩展名
                        elif 'word' in content_type:  # 如果是 Word 类型
                            ext = '.docx'  # 设置扩展名
                        elif 'markdown' in content_type:  # 如果是 Markdown 类型
                            ext = '.md'  # 设置扩展名
                        elif 'image' in content_type:  # 如果是图片类型
                            # 图片类型
                            if 'png' in content_type:  # PNG 图片
                                ext = '.png'
                            elif 'jpeg' in content_type or 'jpg' in content_type:  # JPEG 图片
                                ext = '.jpg'
                            elif 'gif' in content_type:  # GIF 图片
                                ext = '.gif'
                            elif 'bmp' in content_type:  # BMP 图片
                                ext = '.bmp'
                            else:
                                ext = '.png'  # 默认使用png
                        else:
                            ext = '.txt'  # 其他类型默认为文本文件

                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)  # 创建临时文件，delete=False 不自动删除（在 finally 中手动删除），suffix 指定扩展名
                    for chunk in response.iter_content(chunk_size=8192):  # 流式读取响应内容，每次读取 8KB
                        temp_file.write(chunk)  # 写入临时文件
                    temp_file.close()  # 关闭临时文件（写完后必须关闭才能被其他程序读取）
                    target_path = temp_file.name  # 将目标路径设为临时文件路径
                except Exception as e:
                    raise Exception(f"Failed to download file from URL: {e}")  # 抛出新异常（包装原始异常信息）
            else:
                if not os.path.exists(file_path):  # 如果本地文件不存在
                    raise FileNotFoundError(f"File not found: {file_path}")  # 抛出文件未找到异常

            ext = os.path.splitext(target_path)[1].lower()  # 获取文件扩展名（小写）

            if ext == '.pdf':  # 如果是 PDF 文件
                loader = PyPDFLoader(target_path)  # 创建 PDF 加载器
                documents = loader.load()  # 加载文档，返回 Document 列表
            elif ext == '.docx':  # 如果是 Word 文件
                loader = Docx2txtLoader(target_path)  # 创建 Word 加载器
                documents = loader.load()  # 加载文档
            elif ext == '.txt':  # 如果是纯文本文件
                loader = TextLoader(target_path, encoding='utf-8')  # 创建文本加载器，指定 UTF-8 编码
                documents = loader.load()  # 加载文档
            elif ext == '.md':  # 如果是 Markdown 文件
                loader = TextLoader(target_path, encoding='utf-8')  # 使用文本加载器（Markdown 本质也是文本）
                documents = loader.load()  # 加载文档
            elif ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif']:  # 如果是图片文件（in 检查是否在列表中）
                # 处理图片文件，使用OCR
                try:
                    logger.info(f"Processing image file: {target_path}")  # 记录正在处理的图片

                    # 检查Tesseract是否可用
                    if not tesseract_available:  # 如果 Tesseract 不可用
                        logger.warning("Tesseract OCR is not available. Image OCR functionality is disabled.")  # 记录警告
                        # 返回一个包含错误信息的文档
                        documents = [Document(  # 创建包含错误信息的 Document 对象
                            page_content="图片OCR处理失败: Tesseract OCR未安装或不可用",  # 文档内容
                            metadata={  # 元数据字典
                                "source": target_path,  # 文件来源路径
                                "page": 1,  # 页码
                                "file_type": "image",  # 文件类型
                                "error": "Tesseract OCR is not available"  # 错误信息
                            }
                        )]
                    else:
                        image = Image.open(target_path)  # 打开图片文件

                        # 优化图片预处理
                        # 1. 转换为灰度图（提高OCR准确率）
                        if image.mode != 'L':  # 如果图片不是灰度模式（'L' 表示灰度）
                            image = image.convert('L')  # 转换为灰度图

                        # 2. 调整图片大小（如果太大）
                        max_size = 2000  # 最大尺寸（像素）
                        if max(image.size) > max_size:  # image.size 是 (宽, 高) 元组，max() 取较大值
                            ratio = max_size / max(image.size)  # 计算缩放比例
                            new_size = tuple(int(dim * ratio) for dim in image.size)  # 生成新尺寸的元组
                            image = image.resize(new_size, Image.Resampling.LANCZOS)  # 使用 Lanczos 重采样方法调整图片大小（高质量缩放）
                            logger.info(f"Resized image from {image.size} to {new_size}")  # 记录调整信息

                        # 3. 尝试多种语言配置
                        ocr_text = ""  # OCR 识别结果，初始为空字符串
                        ocr_errors = []  # OCR 错误信息列表

                        # 尝试组合语言包
                        lang_configs = [  # 语言配置列表，按优先级排序
                            'chi_sim+eng',  # 简体中文+英文
                            'chi_sim',      # 仅简体中文
                            'eng',          # 仅英文
                            'chi_tra+eng',  # 繁体中文+英文
                        ]

                        for lang in lang_configs:  # 遍历每种语言配置
                            try:
                                logger.info(f"Trying OCR with language: {lang}")  # 记录正在尝试的语言
                                text = pytesseract.image_to_string(  # 调用 Tesseract OCR 识别文字
                                    image,  # 图片对象
                                    lang=lang,  # 语言配置
                                    config='--psm 3 --oem 3'  # Tesseract 配置参数：psm 3 自动页面分割，oem 3 使用 LSTM 引擎
                                )

                                if text and text.strip():  # 如果识别出非空文字
                                    ocr_text = text.strip()  # 保存去除首尾空白后的结果
                                    logger.info(f"OCR successful with language {lang}, text length: {len(ocr_text)}")  # 记录成功信息
                                    # 预览前100个字符
                                    preview = ocr_text[:100].replace('\n', ' ')  # 取前100字符，替换换行为空格
                                    logger.info(f"OCR preview: {preview}...")  # 记录预览
                                    break  # 成功识别则跳出循环（类似 Java 的 break）
                                else:
                                    logger.warning(f"No text detected with language: {lang}")  # 记录未检测到文字
                            except Exception as lang_error:  # 捕获当前语言识别的异常
                                error_msg = f"Language {lang} failed: {str(lang_error)}"  # 构建错误信息
                                ocr_errors.append(error_msg)  # 添加到错误列表
                                logger.warning(error_msg)  # 记录警告

                        # 如果所有语言都失败，尝试默认语言
                        if not ocr_text:  # 如果所有语言配置都未识别出文字
                            try:
                                logger.info("Trying OCR with default settings")  # 记录尝试默认设置
                                ocr_text = pytesseract.image_to_string(image).strip()  # 使用默认设置识别
                            except Exception as default_error:  # 捕获默认设置的异常
                                logger.error(f"Default OCR failed: {default_error}")  # 记录错误

                        # 最终检查
                        if not ocr_text or not ocr_text.strip():  # 如果仍然没有文字
                            ocr_text = "图片中未识别到文字"  # 设置默认提示
                            logger.warning("No text detected in image")  # 记录警告
                        else:
                            logger.info(f"OCR completed successfully. Text length: {len(ocr_text)}")  # 记录成功

                        # 创建文档对象
                        documents = [Document(  # 创建包含 OCR 结果的 Document
                            page_content=ocr_text,  # OCR 识别的文字内容
                            metadata={  # 元数据
                                "source": target_path,  # 文件来源
                                "page": 1,  # 页码
                                "file_type": "image",  # 文件类型
                                "ocr_errors": ocr_errors if ocr_errors else None  # OCR 错误列表（非空则保留，否则为 None）
                            }
                        )]
                except Exception as e:  # 捕获图片处理的异常
                    logger.error(f"Failed to OCR image {target_path}: {e}")  # 记录错误
                    # 返回一个包含错误信息的文档，而不是抛出异常
                    documents = [Document(  # 创建包含错误信息的 Document
                        page_content=f"图片OCR处理失败: {str(e)}",  # 错误信息作为内容
                        metadata={
                            "source": target_path,  # 文件来源
                            "page": 1,  # 页码
                            "file_type": "image",  # 文件类型
                            "error": str(e)  # 错误信息
                        }
                    )]
            else:
                raise ValueError(f"Unsupported file type: {ext}")  # 不支持的文件类型，抛出 ValueError

            # 使用自适应切分器进行文档切分
            # 对文档中的metadata进行处理 添加file_type（去掉扩展名的点号，如 .pdf → pdf）
            # 图片类型统一设为 image（metadata 中已手动设置），其他类型根据扩展名推断
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.tif']:  # 如果是图片格式
                file_type_value = 'image'  # 图片统一标记为 image
            else:  # 非图片格式
                file_type_value = ext.lstrip('.') if ext else ''  # lstrip('.') 去掉开头的点号，.pdf 变成 pdf
            documents = [Document(  # 创建包含 metadata 的 Document
                page_content=document.page_content,  # 保持原始内容
                metadata={  # 元数据
                    **document.metadata,  # 合并原始元数据（保留已有的 source、page 等字段）
                    "file_type": file_type_value  # 添加或覆盖文件类型（如 pdf、docx、image）
                }
            ) for document in documents]
            chunks = self.chunker.split_documents(documents)  # 调用切分器将文档切分为多个文本块
            return chunks  # 返回切分后的文本块列表

        finally:  # finally 块，无论是否异常都会执行
            # 清理临时文件
            if temp_file and os.path.exists(temp_file.name):  # 如果临时文件存在
                try:
                    os.unlink(temp_file.name)  # 删除临时文件（os.unlink 等价于 os.remove）
                except Exception:  # 删除失败则忽略
                    pass  # pass 是空操作语句（类似 Java 的 ; ），不做任何事
