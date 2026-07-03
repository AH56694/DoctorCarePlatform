import os  # 导入 os 模块，用于操作系统功能（如文件路径操作）
import json  # 导入 json 模块，用于 JSON 序列化和反序列化（类似 Java 的 Jackson/Gson）
import requests  # 导入 requests 库，用于发送 HTTP 请求（类似 Java 的 HttpClient/OkHttp）
from typing import AsyncGenerator, Generator  # 导入类型提示：AsyncGenerator 异步生成器，Generator 同步生成器（Python 特有，类似 Java 的 Stream）
from langchain_community.llms import Tongyi  # 从 langchain 社区包导入通义千问 LLM 封装类
from langchain_core.prompts import PromptTemplate  # 导入 Prompt 模板类，用于构建提示词模板（支持变量占位符）
from langchain_core.output_parsers import StrOutputParser  # 导入字符串输出解析器，将 LLM 输出解析为字符串
from PIL import Image  # 从 Pillow 库导入 Image 类，用于图片处理（打开、转换、调整大小等）
import pytesseract  # 导入 Tesseract OCR 的 Python 封装，用于图片文字识别
from langchain.chat_models import init_chat_model

# 使用统一配置管理模块
from core.config import config  # 从 core 包导入全局配置实例（Python 中模块是单例的）

# 配置Tesseract OCR路径（空值时由 parser.py 自动检测）
if config.TESSERACT_PATH:  # 如果配置中设置了 Tesseract 路径（非空字符串在 Python 中为 True）
    pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_PATH  # 设置 tesseract 可执行文件路径

class LLMService:  # 定义 LLM 服务类，封装大语言模型的调用逻辑
    def __init__(self):  # 构造方法，初始化 LLM 服务
        # 默认使用阿里云通义千问 (需要设置 DASHSCOPE_API_KEY 环境变量)
        api_key = config.DASHSCOPE_API_KEY  # 从配置中获取 DashScope API 密钥

        if not api_key:  # 如果 API 密钥为空（空字符串在 Python 中为 False）
            config.logger.warning("DASHSCOPE_API_KEY not found. LLM features will not work properly.")  # 记录警告日志
            self.llm = None  # 将 LLM 实例设为 None（Python 的空值，类似 Java 的 null）
        else:
            # 使用 qwen-plus 模型，效果比 turbo 好，适合知识库问答
            # 如果需要更强的推理能力，可以使用 qwen-max
            # 启用流式输出
            self.llm = init_chat_model(  # 创建通义千问 LLM 实例（类似 Java 的 new Tongyi()）
                model="deepseek-chat"
            )

        # 优化后的 Prompt 模板
        # 支持对话上下文和知识库上下文
        self.prompt = PromptTemplate.from_template(  # 从模板字符串创建 Prompt 模板，{variable} 为占位符
            """
            你是一个专业的AI知识库助手。请根据提供的知识库信息回答用户问题。

            重要规则：
            1. 如果知识库中有相关信息，请优先引用知识库内容进行回答
            2. 如果知识库中没有相关信息，请先说明"知识库中未找到相关信息，以下是我的理解："，然后根据你的知识进行回答
            3. 如果是问候、自我介绍等问题，可以直接回答，不需要强行引用知识库
            4. 回答要自然、友好，避免机械和死板
            5. 不要提及"AI服务不可用"、"系统错误"等技术问题，你始终处于正常工作状态

            对话历史（仅供参考，可能包含过时信息）：
            {conversation_context}

            相关知识库：
            {knowledge_context}

            用户当前问题：
            {question}

            请给出自然、友好的回答：
            """
        )

        # 标题生成模板
        self.summary_prompt = PromptTemplate.from_template(  # 创建标题生成的 Prompt 模板
            """
            请为以下用户问题生成一个简短的标题（Summary）。

            用户问题：
            {question}

            要求：
            1. 标题应概括问题的主要内容。
            2. 长度控制在10个字以内。
            3. 不需要任何前缀或后缀，直接返回标题文本。

            标题：
            """
        )

    """
     * 获取 LLM 的回答
     * @param question 用户问题
     * @param context_docs 上下文文档列表
     * @param conversation_context 对话上下文（可选）
     * @return LLM 的回答
     * """
    def get_answer(self, question: str, context_docs: list, conversation_context: str = "") -> str:  # 定义获取回答的方法，参数后的 : str 是类型提示，= "" 是默认参数值（类似 Java 的方法重载）
        import time  # 局部导入 time 模块（仅在此方法内使用，减少全局导入开销）
        start_time = time.time()  # 记录开始时间（类似 Java 的 System.currentTimeMillis()）

        if not self.llm:  # 如果 LLM 未初始化（None 在 Python 中为 False）
            # 当没有API密钥时，返回一个友好的默认响应
            config.logger.info(f"LLM get_answer completed in {time.time() - start_time:.4f}s (no API key)")  # f-string 中 :.4f 表示保留4位小数
            return "我是AI知识库助手，很高兴为您服务。由于系统未配置API密钥，我暂时无法提供详细回答。请联系管理员配置DASHSCOPE_API_KEY环境变量以启用完整功能。"

        # 处理包含图片的问题
        image_process_start = time.time()  # 记录图片处理开始时间
        processed_question = self.process_question_with_images(question)  # 调用图片处理方法，提取图片中的文字
        image_process_time = time.time() - image_process_start  # 计算图片处理耗时
        config.logger.info(f"Image processing completed in {image_process_time:.4f}s")  # 记录图片处理耗时

        # 处理知识库上下文
        if not context_docs:  # 如果没有知识库文档（空列表在 Python 中为 False）
            knowledge_context = "（无相关知识库信息）"  # 设置默认提示文本
        else:
            knowledge_context = "\n\n".join([  # 用双换行符连接所有文档内容
                doc.page_content if hasattr(doc, 'page_content') else str(doc)  # hasattr 检查对象是否有该属性（类似 Java 的反射），有则取 page_content，无则转字符串
                for doc in context_docs  # 列表推导式（Python 特有），类似 Java 的 stream().map().collect()
            ])

        # 处理对话上下文 - 过滤掉错误信息
        cleaned_context = self.clean_conversation_context(conversation_context)  # 调用清理方法过滤错误信息
        if not cleaned_context or cleaned_context.strip() == "":  # 如果清理后为空或只有空白字符
            cleaned_context = "（无对话历史）"  # 设置默认提示文本

        # 构建处理链
        chain = (  # LangChain 的链式调用（pipe 语法），类似 Java 的 Stream API
            self.prompt  # 第一步：用变量填充 Prompt 模板
            | self.llm  # 第二步：调用 LLM 生成回答（| 是 Python 的位运算符，LangChain 重载了 __or__ 方法实现管道语法）
            | StrOutputParser()  # 第三步：将 LLM 输出解析为字符串
        )

        try:  # try-except 异常处理（类似 Java 的 try-catch）
            llm_start = time.time()  # 记录 LLM 调用开始时间
            result = chain.invoke({  # 调用链式处理，invoke 是同步执行方法，传入字典作为参数
                "conversation_context": cleaned_context,  # 对话上下文
                "knowledge_context": knowledge_context,  # 知识库上下文
                "question": processed_question  # 用户问题（可能已提取图片文字）
            })
            llm_time = time.time() - llm_start  # 计算 LLM 调用耗时
            config.logger.info(f"LLM invocation completed in {llm_time:.4f}s")  # 记录 LLM 调用耗时
            config.logger.info(f"LLM get_answer completed in {time.time() - start_time:.4f}s")  # 记录总耗时
            return result  # 返回 LLM 生成的回答
        except Exception as e:  # 捕获所有异常（类似 Java 的 catch(Exception e)）
            config.logger.error(f"LLM Error: {e}")  # 记录错误日志
            config.logger.info(f"LLM get_answer completed in {time.time() - start_time:.4f}s (error)")  # 记录异常时的总耗时
            return "抱歉，我暂时无法回答这个问题，请稍后再试。"  # 返回友好的错误提示

    def clean_conversation_context(self, context: str) -> str:  # 定义清理对话上下文的方法
        """
        清理对话上下文，移除错误信息，防止污染后续回答
        """
        if not context:  # 如果上下文为空（None 或空字符串）
            return ""  # 返回空字符串

        # 需要过滤的错误关键词
        error_keywords = [  # 定义错误关键词列表
            "AI服务暂时不可用",
            "服务不可用",
            "系统错误",
            "无法连接",
            "网络错误",
            "超时",
            "API密钥",
            "配置错误"
        ]

        # 按行分割
        lines = context.split("\n")  # 按换行符分割为行列表（类似 Java 的 String.split）
        # 过滤包含错误关键词的行
        cleaned_lines = [  # 列表推导式：过滤掉包含错误关键词的行
            line for line in lines  # 遍历每一行
            if not any(keyword in line for keyword in error_keywords)  # any() 只要有一个关键词匹配就为 True，not any 表示都不匹配
        ]

        return "\n".join(cleaned_lines)  # 将过滤后的行用换行符重新拼接成字符串

    """
     * 流式获取 LLM 的回答
     * @param question 用户问题
     * @param context_docs 上下文文档列表
     * @param conversation_context 对话上下文（可选）
     * @return 流式生成器，逐个token返回
     * """
    def get_answer_stream(self, question: str, context_docs: list, conversation_context: str = "") -> Generator[str, None, None]:  # -> Generator[str, None, None] 表示返回字符串生成器（yield 关键字实现，类似 Java 的 Stream/Iterator）
        import time  # 局部导入 time 模块
        start_time = time.time()  # 记录开始时间

        if not self.llm:  # 如果 LLM 未初始化
            # 当没有API密钥时，返回错误信息
            config.logger.info(f"LLM get_answer_stream completed in {time.time() - start_time:.4f}s (no API key)")
            yield json.dumps({"type": "error", "content": "未配置API密钥"})  # yield 是 Python 特有关键字，暂停函数执行并返回一个值（类似 Java 的自定义 Iterator），json.dumps 将字典序列化为 JSON 字符串
            return  # 提前结束生成器函数

        # 处理包含图片的问题
        image_process_start = time.time()  # 记录图片处理开始时间
        processed_question = self.process_question_with_images(question)  # 处理图片问题
        image_process_time = time.time() - image_process_start  # 计算耗时
        config.logger.info(f"Image processing completed in {image_process_time:.4f}s")  # 记录耗时

        # 处理知识库上下文
        if not context_docs:  # 如果没有知识库文档
            knowledge_context = "（无相关知识库信息）"  # 默认提示
        else:
            knowledge_context = "\n\n".join([  # 拼接所有文档内容
                doc.page_content if hasattr(doc, 'page_content') else str(doc)  # hasattr 检查属性是否存在
                for doc in context_docs  # 列表推导式遍历
            ])

        # 处理对话上下文 - 过滤掉错误信息
        cleaned_context = self.clean_conversation_context(conversation_context)  # 清理上下文
        if not cleaned_context or cleaned_context.strip() == "":  # 如果为空
            cleaned_context = "（无对话历史）"  # 默认提示

        # 构建处理链
        chain = (  # LangChain 管道链
            self.prompt
            | self.llm
            | StrOutputParser()
        )

        try:
            # 发送开始信号
            yield json.dumps({"type": "start", "content": ""})  # yield 返回开始信号的 JSON 字符串

            # 流式调用
            llm_start = time.time()  # 记录 LLM 调用开始时间
            full_response = ""  # 初始化完整响应字符串
            for chunk in chain.stream({  # chain.stream 流式调用 LLM，每次返回一小段文本（chunk）
                "conversation_context": cleaned_context,
                "knowledge_context": knowledge_context,
                "question": processed_question
            }):
                full_response += chunk  # 累加每个 chunk 到完整响应
                yield json.dumps({"type": "token", "content": chunk})  # yield 返回每个 token 的 JSON 字符串
            llm_time = time.time() - llm_start  # 计算 LLM 流式调用耗时
            config.logger.info(f"LLM stream invocation completed in {llm_time:.4f}s")  # 记录耗时

            # 发送结束信号
            yield json.dumps({"type": "end", "content": full_response})  # yield 返回结束信号和完整响应
            config.logger.info(f"LLM get_answer_stream completed in {time.time() - start_time:.4f}s")  # 记录总耗时

        except Exception as e:  # 捕获异常
            config.logger.error(f"LLM Stream Error: {e}")  # 记录错误
            config.logger.info(f"LLM get_answer_stream completed in {time.time() - start_time:.4f}s (error)")  # 记录异常耗时
            yield json.dumps({"type": "error", "content": "暂时无法回答，请稍后再试"})  # yield 返回错误信息

    def generate_title(self, question: str) -> str:  # 定义生成对话标题的方法
        import time  # 局部导入 time 模块
        start_time = time.time()  # 记录开始时间

        if not self.llm:  # 如果 LLM 未初始化
            config.logger.info(f"LLM generate_title completed in {time.time() - start_time:.4f}s (no API key)")
            return "New Chat"  # 返回默认标题

        chain = (  # 构建标题生成的链式处理
            self.summary_prompt  # 使用标题生成的 Prompt 模板
            | self.llm  # 调用 LLM
            | StrOutputParser()  # 解析输出为字符串
        )

        try:
            llm_start = time.time()  # 记录 LLM 调用开始时间
            title = chain.invoke({"question": question})  # 调用链式处理，传入用户问题
            llm_time = time.time() - llm_start  # 计算 LLM 调用耗时
            # 清理可能的额外空白或引号
            result = title.strip().strip('"').strip("'")  # strip() 去除首尾空白，strip('"') 去除首尾双引号，strip("'") 去除首尾单引号（链式调用）
            config.logger.info(f"LLM title generation completed in {llm_time:.4f}s")  # 记录耗时
            config.logger.info(f"LLM generate_title completed in {time.time() - start_time:.4f}s")  # 记录总耗时
            return result  # 返回清理后的标题
        except Exception as e:  # 捕获异常
            config.logger.error(f"LLM Title Generation Error: {e}")  # 记录错误
            config.logger.info(f"LLM generate_title completed in {time.time() - start_time:.4f}s (error)")  # 记录异常耗时
            return "New Chat"  # 返回默认标题

    def extract_text_from_image(self, image_url: str) -> str:  # 定义从图片 URL 提取文字的方法
        """
        从图片URL中提取文字
        """
        try:
            # 处理相对路径，转换为完整URL
            if image_url.startswith('/api/'):  # 如果是相对路径（以 /api/ 开头）
                # 使用后端服务地址
                image_url = f"http://localhost:8080{image_url}"  # 拼接为完整 URL

            config.logger.info(f"Downloading image from: {image_url}")  # 记录下载地址

            # 下载图片
            response = requests.get(image_url, timeout=10)  # 发送 GET 请求下载图片，超时10秒
            response.raise_for_status()  # 如果响应状态码不是 2xx，抛出异常（类似 Java 的检查响应码）

            # 保存到临时文件
            temp_path = os.path.join(config.TEMP_DIR, "temp_image.png")  # os.path.join 拼接路径（跨平台安全）
            with open(temp_path, "wb") as f:  # with 语句自动管理资源（类似 Java 7 的 try-with-resources），"wb" 表示二进制写入模式
                f.write(response.content)  # 将下载的图片内容写入文件

            config.logger.info(f"Image saved to temp file, size: {len(response.content)} bytes")  # 记录文件大小

            # 使用OCR提取文字
            image = Image.open(temp_path)  # 打开图片文件
            text = pytesseract.image_to_string(image, lang='chi_sim+eng')  # 使用 Tesseract 进行 OCR，指定中英文识别

            config.logger.info(f"OCR result: {text[:100]}...")  # 打印前100个字符，text[:100] 是切片语法（类似 Java 的 substring）

            # 清理临时文件
            if os.path.exists(temp_path):  # 如果临时文件存在
                os.remove(temp_path)  # 删除临时文件

            return text.strip() if text.strip() else "图片中未识别到文字"  # 三元表达式：有文字则返回去除空白后的文字，否则返回提示
        except Exception as e:  # 捕获所有异常
            config.logger.error(f"Error extracting text from image: {e}")  # 记录错误
            return f"无法从图片中提取文字: {str(e)}"  # 返回错误信息

    def process_question_with_images(self, question: str) -> str:  # 定义处理包含图片的问题的方法
        """
        处理包含图片URL的问题，提取图片中的文字并添加到问题中
        """
        import re  # 局部导入正则表达式模块
        # 查找图片URL（支持完整URL和相对路径）
        image_urls = re.findall(r'图片URL: (/api/[^\n]+)', question)  # re.findall 用正则表达式查找所有匹配项，r'' 是原始字符串（不转义反斜杠）

        config.logger.info(f"Found image URLs: {image_urls}")  # 记录找到的图片 URL

        if image_urls:  # 如果找到了图片 URL（非空列表为 True）
            processed_question = question  # 复制原始问题
            for image_url in image_urls:  # 遍历每个图片 URL
                # 提取图片中的文字
                image_text = self.extract_text_from_image(image_url)  # 调用 OCR 方法提取文字
                # 将图片文字添加到问题中
                processed_question += f"\n\n图片内容: {image_text}"  # 将 OCR 结果追加到问题末尾
            return processed_question  # 返回增强后的问题
        else:
            return question  # 没有图片则返回原始问题

    def generate(self, prompt: str, temperature: float = 0.7, max_tokens: int = 150) -> str:  # 定义简单文本生成方法，temperature 控制随机性，max_tokens 限制输出长度
        """
        简单的文本生成方法（用于闲聊等场景）
        """
        import time  # 局部导入 time 模块
        start_time = time.time()  # 记录开始时间

        if not self.llm:  # 如果 LLM 未初始化
            config.logger.info(f"LLM generate completed in {time.time() - start_time:.4f}s (no API key)")
            return "我是AI助手，很高兴为您服务。"  # 返回默认回复

        try:
            # 使用简单的 prompt
            simple_prompt = PromptTemplate.from_template("{input}")  # 创建简单的 Prompt 模板，只有一个 {input} 占位符
            chain = simple_prompt | self.llm | StrOutputParser()  # 构建链式处理

            result = chain.invoke({"input": prompt})  # 调用链式处理

            config.logger.info(f"LLM generate completed in {time.time() - start_time:.4f}s")  # 记录耗时
            return result  # 返回生成结果
        except Exception as e:  # 捕获异常
            config.logger.error(f"LLM generate Error: {e}")  # 记录错误
            return "抱歉，我暂时无法回答这个问题。"  # 返回默认回复


# 创建单例实例
llm_service = LLMService()  # 创建 LLM 服务的全局单例实例

# 导出（保持兼容性）
llm = llm_service  # 创建别名导出，方便其他模块使用 llm 调用
