import os  # 导入 os 模块（本文件未直接使用，但作为通用导入保留）
import re  # 导入正则表达式模块，用于文本清理和分割（类似 Java 的 java.util.regex）
from typing import List, Optional, Dict, Any  # 导入类型提示：List 列表，Optional 可空类型，Dict 字典，Any 任意类型
from langchain_core.documents import Document  # 导入 LangChain 的 Document 类，封装文档内容和元数据
try:  # try-except 用于处理导入兼容性
    from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter  # 优先从 langchain_text_splitters 包导入（新版）
except ImportError:  # 如果新版包不存在
    from langchain.text_splitter import RecursiveCharacterTextSplitter, TextSplitter  # 从旧版路径导入（向后兼容）
from langchain_experimental.text_splitter import SemanticChunker  # 导入语义分块器（实验性功能）
import logging  # 导入日志模块

logger = logging.getLogger(__name__)  # 获取当前模块的 Logger 实例

class SemanticChunkerSplitter(TextSplitter):  # 定义语义分块器类，继承 TextSplitter（类似 Java 的 extends）
    """
    基于语义的分块器，结合多种策略进行文档切分

    策略：
    1. 首先尝试按段落切分（保留段落完整性）
    2. 如果段落太长，再按句子切分
    3. 保留文档结构信息（标题、列表等）
    4. 添加重叠以保持上下文连贯性
    """

    def __init__(  # 构造方法
        self,
        chunk_size: int = 500,  # 每个文本块的最大字符数
        chunk_overlap: int = 50,  # 相邻文本块的重叠字符数
        min_chunk_size: int = 100,  # 文本块的最小字符数（太小的块会被合并）
        separator: str = "\n\n",  # 段落分隔符（双换行）
        sentence_separator: str = "\n",  # 句子分隔符（单换行）
        max_heading_length: int = 100  # 标题的最大长度
    ):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)  # 调用父类 TextSplitter 的构造方法（类似 Java 的 super()）
        self.min_chunk_size = min_chunk_size  # 保存最小文本块大小
        self.separator = separator  # 保存段落分隔符
        self.sentence_separator = sentence_separator  # 保存句子分隔符
        self.max_heading_length = max_heading_length  # 保存标题最大长度

        # 备用递归切分器
        self.fallback_splitter = RecursiveCharacterTextSplitter(  # 创建递归字符切分器作为备用
            chunk_size=chunk_size,  # 最大块大小
            chunk_overlap=chunk_overlap,  # 重叠大小
            separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]  # 分隔符优先级列表（从大到小依次尝试）
        )

    def split_text(self, text: str) -> List[str]:  # 定义文本分割方法（重写父类方法）
        """将文本分割成语义块"""  # 方法的 docstring
        if not text or not text.strip():  # 如果文本为空或只有空白字符
            return []  # 返回空列表

        # 清理文本
        text = self._clean_text(text)  # 调用文本清理方法

        # 策略1：按双换行符切分（段落）
        paragraphs = self._split_by_paragraphs(text)  # 调用段落分割方法

        chunks = []  # 初始化文本块列表
        current_chunk = ""  # 当前正在构建的文本块

        for paragraph in paragraphs:  # 遍历每个段落
            # 跳过空段落
            if not paragraph.strip():  # 如果段落去除空白后为空
                continue  # 跳过当前迭代（类似 Java 的 continue）

            # 如果单个段落就超过chunk_size，需要进一步切分
            if len(paragraph) > self._chunk_size:  # 如果段落长度超过最大块大小（_chunk_size 来自父类）
                # 先保存当前chunk
                if current_chunk.strip():  # 如果当前块非空
                    chunks.append(current_chunk.strip())  # 保存当前块
                    current_chunk = ""  # 重置当前块

                # 对长段落按句子切分
                sentence_chunks = self._split_long_paragraph(paragraph)  # 调用长段落分割方法
                chunks.extend(sentence_chunks)  # extend 将列表中的所有元素添加到 chunks（类似 Java 的 list.addAll）
            else:
                # 检查添加这个段落是否会超过chunk_size
                if len(current_chunk) + len(paragraph) + len(self.separator) > self._chunk_size:  # 检查合并后是否超限
                    # 保存当前chunk，开始新的
                    if current_chunk.strip():  # 如果当前块非空
                        chunks.append(current_chunk.strip())  # 保存
                    current_chunk = paragraph  # 开始新的块
                else:
                    # 添加到当前chunk
                    if current_chunk:  # 如果当前块已有内容
                        current_chunk += self.separator + paragraph  # 用分隔符连接后追加
                    else:
                        current_chunk = paragraph  # 直接赋值

        # 添加最后一个chunk
        if current_chunk.strip():  # 如果还有未保存的块
            chunks.append(current_chunk.strip())  # 保存最后一个块

        # 合并太小的chunks
        chunks = self._merge_small_chunks(chunks)  # 调用合并小文本块的方法

        logger.info(f"Semantic chunking resulted in {len(chunks)} chunks")  # 记录切分结果
        return chunks  # 返回切分后的文本块列表

    def _clean_text(self, text: str) -> str:  # 定义清理文本的私有方法
        """清理文本"""  # 方法的 docstring
        # 移除多余的空白字符
        text = re.sub(r'\r\n', '\n', text)  # re.sub 正则替换：将 Windows 换行符 \r\n 统一为 \n
        text = re.sub(r'[ \t]+', ' ', text)  # 将连续的空格/制表符替换为单个空格
        # 移除全角空格
        text = text.replace('　', ' ')  # 将中文全角空格替换为半角空格
        return text  # 返回清理后的文本

    def _split_by_paragraphs(self, text: str) -> List[str]:  # 定义按段落分割的私有方法
        """按段落切分"""  # 方法的 docstring
        # 按双换行符或单个换行符切分
        paragraphs = re.split(r'\n\s*\n|\n', text)  # 正则分割：匹配"换行+空白+换行"或"单个换行"
        return [p.strip() for p in paragraphs if p.strip()]  # 列表推导式：去除空白并过滤空字符串

    def _split_long_paragraph(self, paragraph: str) -> List[str]:  # 定义长段落分割的私有方法
        """对长段落按句子进一步切分"""  # 方法的 docstring
        # 句子结束符
        sentence_ends = r'(?<=[。！？；\n])|(?<=[.!?;]\s)'  # 正则：正向后顾断言 (?<=...) 匹配在指定字符之后的位置
        sentences = re.split(sentence_ends, paragraph)  # 按句子结束符分割

        chunks = []  # 初始化文本块列表
        current_chunk = ""  # 当前块

        for sentence in sentences:  # 遍历每个句子
            sentence = sentence.strip()  # 去除首尾空白
            if not sentence:  # 如果句子为空
                continue  # 跳过

            # 如果单个句子就超过chunk_size，按字符切分
            if len(sentence) > self._chunk_size:  # 句子太长
                if current_chunk.strip():  # 如果当前块有内容
                    chunks.append(current_chunk.strip())  # 保存
                    current_chunk = ""  # 重置

                # 按字符切分，但尽量在标点处断开
                sub_chunks = self._split_by_punctuation(sentence)  # 调用按标点分割的方法
                chunks.extend(sub_chunks)  # 添加子块
            else:
                if len(current_chunk) + len(sentence) > self._chunk_size:  # 合并后超限
                    if current_chunk.strip():  # 当前块非空
                        chunks.append(current_chunk.strip())  # 保存
                    current_chunk = sentence  # 开始新块
                else:
                    if current_chunk:  # 当前块有内容
                        current_chunk += sentence  # 直接追加
                    else:
                        current_chunk = sentence  # 开始新块

        if current_chunk.strip():  # 处理最后一个块
            chunks.append(current_chunk.strip())

        return chunks  # 返回分割结果

    def _split_by_punctuation(self, text: str) -> List[str]:  # 定义按标点符号分割的私有方法
        """按标点符号进一步切分长文本"""  # 方法的 docstring
        # 保留的分隔符
        delimiters = ['，', '。', '；', '、', ':', '：', '"', '"', "'", "'"]  # 中英文标点列表

        chunks = []  # 初始化结果列表
        current_pos = 0  # 当前处理位置
        text_len = len(text)  # 文本总长度

        while current_pos < text_len:  # 循环处理直到文本末尾
            # 找到最近的分隔符
            next_delimiter_pos = -1  # 下一个分隔符位置，-1 表示未找到
            delimiter = ''  # 找到的分隔符

            for d in delimiters:  # 遍历所有分隔符
                pos = text.find(d, current_pos)  # str.find 从 current_pos 开始查找分隔符位置
                if pos != -1 and (next_delimiter_pos == -1 or pos < next_delimiter_pos):  # 找到且更近
                    next_delimiter_pos = pos  # 更新位置
                    delimiter = d  # 记录分隔符

            if next_delimiter_pos == -1 or next_delimiter_pos - current_pos > self._chunk_size:  # 没找到分隔符或距离太远
                # 没有找到分隔符或下一个分隔符太远，直接取剩余字符
                chunk = text[current_pos:current_pos + self._chunk_size]  # 切片取 chunk_size 个字符
                if chunk.strip():  # 如果非空
                    chunks.append(chunk.strip())  # 添加
                current_pos += self._chunk_size  # 移动位置
            else:
                # 在分隔符处断开
                chunk = text[current_pos:next_delimiter_pos + 1]  # 切片取到分隔符（含分隔符）
                if chunk.strip():  # 如果非空
                    chunks.append(chunk.strip())  # 添加
                current_pos = next_delimiter_pos + 1  # 移动到分隔符之后

        return chunks  # 返回分割结果

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:  # 定义合并小文本块的私有方法
        """合并太小的chunks"""  # 方法的 docstring
        if not chunks:  # 如果列表为空
            return []  # 返回空列表

        merged = []  # 合并后的列表
        current = chunks[0]  # 取第一个块作为当前块

        for i in range(1, len(chunks)):  # range(1, n) 生成从 1 到 n-1 的整数序列（类似 Java 的 for(int i=1; i<n; i++)）
            # 如果当前chunk太小，尝试与下一个合并
            if len(current) < self.min_chunk_size and i < len(chunks):  # 当前块太小且还有下一个块
                current += self.separator + chunks[i]  # 合并当前块和下一个块
            else:
                if current.strip():  # 当前块非空
                    merged.append(current.strip())  # 保存到结果列表
                current = chunks[i]  # 移动到下一个块

        # 添加最后一个
        if current.strip():  # 如果最后一个块非空
            merged.append(current.strip())  # 保存

        return merged  # 返回合并后的列表

    def split_documents(self, documents: List[Document]) -> List[Document]:  # 定义分割文档列表的方法（重写父类）
        """分割文档列表"""  # 方法的 docstring
        result = []  # 初始化结果列表
        for doc in documents:  # 遍历每个文档
            chunks = self.split_text(doc.page_content)  # 对文档内容进行文本分割
            for i, chunk in enumerate(chunks):  # 遍历分割后的文本块
                result.append(Document(  # 创建新的 Document 对象
                    page_content=chunk,  # 文本块内容
                    metadata={  # 元数据字典
                        **doc.metadata,  # ** 解包运算符，展开原文档的所有元数据（类似 Java 的 putAll）
                        "chunk_index": i,  # 添加文本块索引
                        "total_chunks": len(chunks)  # 添加总块数
                    }
                ))
        return result  # 返回分割后的文档列表


class AdaptiveChunker:  # 定义自适应分块器类
    """
    自适应分块器，根据文档类型和内容动态调整分块策略
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):  # 构造方法，接收可选配置字典
        self.config = config or {}  # 如果 config 为 None 则使用空字典

        # 从配置读取参数，使用默认值
        self.chunk_size = self.config.get('chunk_size', 500)  # dict.get(key, default) 安全取值
        self.chunk_overlap = self.config.get('chunk_overlap', 50)  # 文本块重叠字符数
        self.min_chunk_size = self.config.get('min_chunk_size', 100)  # 最小文本块大小

        # 根据文档类型选择策略
        self.strategy = self.config.get('strategy', 'semantic')  # 切分策略，默认语义切分

        if self.strategy == 'semantic':  # 如果策略为语义切分
            self.splitter = SemanticChunkerSplitter(  # 创建语义分块器
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                min_chunk_size=self.min_chunk_size
            )
        else:  # 其他策略
            # 默认使用RecursiveCharacterTextSplitter
            self.splitter = RecursiveCharacterTextSplitter(  # 创建递归字符分割器
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]  # 分隔符优先级
            )

    def split_documents(self, documents: List[Document]) -> List[Document]:  # 定义分割文档的方法
        """分割文档"""  # 方法的 docstring
        logger.info(f"Splitting {len(documents)} documents using '{self.strategy}' strategy")  # 记录分割信息

        # 检测文档类型
        for doc in documents:  # 遍历文档列表
            file_type = doc.metadata.get('file_type', '').lower()  # 从元数据获取文件类型并转小写
            # 根据文件类型调整策略
            if file_type == 'image':  # 如果是图片（OCR 结果）
                # 图片OCR结果通常不需要进一步切分
                return documents  # 直接返回原文档列表

        return self.splitter.split_documents(documents)  # 使用选定的分割器切分文档

    def update_config(self, config: Dict[str, Any]):  # 定义更新配置的方法
        """更新配置并重新初始化切分器"""  # 方法的 docstring
        self.config.update(config)  # dict.update 合并新配置到现有配置（类似 Java 的 map.putAll）
        self.chunk_size = self.config.get('chunk_size', 500)  # 重新读取配置
        self.chunk_overlap = self.config.get('chunk_overlap', 50)
        self.min_chunk_size = self.config.get('min_chunk_size', 100)
        self.strategy = self.config.get('strategy', 'semantic')

        if self.strategy == 'semantic':  # 根据新策略创建分割器
            self.splitter = SemanticChunkerSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                min_chunk_size=self.min_chunk_size
            )
        else:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=["\n\n", "\n", "。", "！", "？", "；", "，", " ", ""]
            )


def create_chunker(config: Optional[Dict[str, Any]] = None) -> AdaptiveChunker:  # 定义创建分块器的工厂函数
    """创建分块器的工厂函数"""  # 方法的 docstring
    return AdaptiveChunker(config)  # 创建并返回自适应分块器实例
