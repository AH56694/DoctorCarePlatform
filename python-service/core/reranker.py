import os  # 导入 os 模块，用于读取环境变量
import logging  # 导入日志模块
from typing import List, Optional, Tuple, Dict, Any  # 导入类型提示：Optional 表示可选类型（类似 Java 的 @Nullable），Tuple 元组类型，Dict 字典类型，Any 任意类型
from langchain_core.documents import Document  # 导入 LangChain 的 Document 类
from langchain_core.embeddings import Embeddings  # 导入 Embeddings 基类（文本向量化接口）
import numpy as np  # 导入 NumPy 数值计算库（类似 Java 的多维数组/矩阵运算），命名为 np（惯例别名）

logger = logging.getLogger(__name__)  # 获取当前模块的 Logger 实例


class RerankerResult:  # 定义重排序结果封装类
    """Rerank结果封装"""  # 类的 docstring

    def __init__(self, document: Document, score: float, original_index: int):  # 构造方法，接收文档对象、分数和原始索引
        self.document = document  # 文档对象（self.document 相当于 Java 中的 this.document）
        self.score = score  # 相关性分数（浮点数，越高越相关）
        self.original_index = original_index  # 文档在原始列表中的索引位置

    def __repr__(self):  # 重写 __repr__ 方法（类似 Java 的 toString()），定义对象的字符串表示形式
        return f"RerankerResult(score={self.score:.4f}, index={self.original_index})"  # :.4f 保留4位小数


class BaseReranker:  # 定义重排序器基类（抽象类，类似 Java 的 abstract class）
    """Reranker基类"""  # 类的 docstring

    def rerank(  # 定义重排序方法（子类必须实现）
        self,
        query: str,  # 查询文本
        documents: List[Document],  # 待重排序的文档列表
        top_k: int = 3  # 返回前 k 个最相关的结果，默认 3
    ) -> List[RerankerResult]:  # 返回重排序结果列表
        """
        对文档进行重排序

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前k个结果

        Returns:
            重排序后的文档列表
        """
        raise NotImplementedError  # 抛出未实现异常（类似 Java 的 abstract 方法，子类必须重写）


class BGEReranker(BaseReranker):  # 定义 BGE 重排序器类，继承 BaseReranker（类似 Java 的 extends）
    """
    使用BGE模型进行重排序

    BGE-Reranker是一种中文语义重排序模型，可以显著提升检索质量
    """

    def __init__(  # 构造方法
        self,
        model_name: str = "BAAI/bge-reranker-base",  # 模型名称，默认使用 BGE 基础版
        use_fp16: bool = True,  # 是否使用 FP16 半精度（减少显存占用，加速推理）
        device: Optional[str] = None  # 设备类型，Optional[str] 表示可以是 str 或 None（类似 Java 的 String 可以为 null）
    ):
        """
        初始化BGE Reranker

        Args:
            model_name: 模型名称
            use_fp16: 是否使用FP16加速
            device: 设备类型，'cpu', 'cuda', 'mps'
        """
        self.model_name = model_name  # 保存模型名称
        self.use_fp16 = use_fp16  # 保存 FP16 配置
        self.device = device or self._get_default_device()  # or 短路求值：device 有值则使用，否则调用方法获取默认设备
        self.model = None  # 模型实例，初始为 None
        self._load_model()  # 调用模型加载方法

    def _get_default_device(self) -> str:  # 定义获取默认计算设备的私有方法
        """获取默认设备"""  # 方法的 docstring
        try:
            import torch  # 局部导入 PyTorch 深度学习框架（类似 Java 的 Class.forName 动态加载）
            if torch.cuda.is_available():  # 检查 CUDA（NVIDIA GPU）是否可用
                return "cuda"  # 返回 CUDA 设备标识
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():  # hasattr 检查对象是否有 mps 属性（Apple Silicon GPU）
                return "mps"  # 返回 MPS 设备标识
        except ImportError:  # 如果 PyTorch 未安装
            pass  # 跳过（空操作）
        return "cpu"  # 默认使用 CPU

    def _load_model(self):  # 定义加载模型的私有方法
        """加载模型"""  # 方法的 docstring
        try:
            from sentence_transformers import CrossEncoder  # 导入 CrossEncoder 交叉编码器（用于对"查询-文档"对进行相关性打分）
            logger.info(f"Loading BGE Reranker model: {self.model_name}")  # 记录正在加载的模型

            self.model = CrossEncoder(  # 创建 CrossEncoder 实例
                self.model_name,  # 模型名称（会自动从 HuggingFace 下载）
                max_length=512,  # 最大输入序列长度（token 数）
                device=self.device  # 计算设备
            )
            logger.info(f"BGE Reranker loaded successfully on {self.device}")  # 记录加载成功
        except ImportError as e:  # 捕获导入错误（库未安装）
            logger.warning(f"sentence-transformers not installed: {e}")  # 记录警告
            logger.warning("Falling back to simple reranking")  # 记录回退到简单重排序
            self.model = None  # 模型设为 None（后续会回退到简单模式）
        except Exception as e:  # 捕获其他异常
            logger.error(f"Failed to load BGE Reranker: {e}")  # 记录错误
            logger.warning("Falling back to simple reranking")  # 记录回退
            self.model = None

    def rerank(  # 重写基类的重排序方法（类似 Java 的 @Override）
        self,
        query: str,
        documents: List[Document],
        top_k: int = 3
    ) -> List[RerankerResult]:
        """
        对文档进行重排序

        Args:
            query: 查询文本
            documents: 文档列表
            top_k: 返回前k个结果

        Returns:
            重排序后的文档列表
        """
        if not documents:  # 如果文档列表为空
            return []  # 返回空列表

        if self.model is None:  # 如果模型未加载
            logger.warning("Reranker model not loaded, returning original order")  # 记录警告
            return [
                RerankerResult(doc, 1.0, i)  # 返回原始顺序的结果（分数都设为 1.0）
                for i, doc in enumerate(documents[:top_k])  # enumerate 同时获取索引和元素，[:top_k] 切片取前 top_k 个
            ]

        try:
            # 准备输入对
            pairs = [[query, doc.page_content] for doc in documents]  # 列表推导式：为每个文档构建 [查询, 文档内容] 对

            # 计算相关性分数
            scores = self.model.predict(pairs)  # 使用模型批量预测相关性分数

            # 如果返回的是单个值而不是数组
            if not isinstance(scores, np.ndarray):  # isinstance 检查对象是否为指定类型（类似 Java 的 instanceof）
                scores = np.array([scores])  # 将单个值包装为数组（np.array 创建 NumPy 数组）

            # 创建结果列表
            results = [
                RerankerResult(doc, float(score), i)  # 为每个文档创建结果对象
                for i, (doc, score) in enumerate(zip(documents, scores))  # zip 将两个列表按索引配对，enumerate 添加索引
            ]

            # 按分数降序排序
            results.sort(key=lambda x: x.score, reverse=True)  # lambda 匿名函数（类似 Java 的 (x) -> x.getScore()），reverse=True 降序

            # 返回top_k
            logger.info(f"Reranked {len(documents)} documents, top {top_k} scores: {[r.score for r in results[:top_k]]}")  # 记录重排序结果
            return results[:top_k]  # 切片返回前 top_k 个结果

        except Exception as e:
            logger.error(f"Reranking failed: {e}")  # 记录错误
            # 失败时返回原始顺序
            return [
                RerankerResult(doc, 1.0, i)
                for i, doc in enumerate(documents[:top_k])
            ]


class SimpleReranker(BaseReranker):  # 定义简单重排序器类，基于关键词匹配
    """
    简单的重排序器，使用关键词匹配和BM25

    作为BGE Reranker的备选方案
    """

    def __init__(self, alpha: float = 0.5):  # 构造方法，alpha 是语义分数权重
        """
        初始化简单重排序器

        Args:
            alpha: 语义分数权重 (1-alpha为关键词匹配权重)
        """
        self.alpha = alpha  # 保存权重参数

    def _calculate_keyword_score(self, query: str, document: Document) -> float:  # 定义计算关键词匹配分数的私有方法
        """计算关键词匹配分数"""  # 方法的 docstring
        # 简单的字符级别匹配（适用于中文）
        query_chars = set([c for c in query.lower() if c.isalnum()])  # 集合推导式：提取查询中的字母数字字符，set 去重
        doc_chars = set([c for c in document.page_content.lower() if c.isalnum()])  # 提取文档中的字母数字字符

        if not query_chars:  # 如果查询字符集为空
            return 0.0  # 返回 0 分

        # 计算Jaccard相似度
        intersection = query_chars & doc_chars  # & 集合交集运算（两个集合共有的元素）
        union = query_chars | doc_chars  # | 集合并集运算（两个集合的所有元素）

        jaccard = len(intersection) / len(union) if union else 0  # Jaccard 相似度 = 交集大小 / 并集大小，if union 防止除零

        # 计算覆盖率
        coverage = len(intersection) / len(query_chars) if query_chars else 0  # 覆盖率 = 交集大小 / 查询字符数

        return (jaccard + coverage) / 2  # 返回两个指标的平均值作为最终分数

    def rerank(  # 重写重排序方法
        self,
        query: str,
        documents: List[Document],
        top_k: int = 3
    ) -> List[RerankerResult]:
        """对文档进行简单重排序"""  # 方法的 docstring
        if not documents:  # 如果文档列表为空
            return []

        results = []  # 初始化结果列表

        for i, doc in enumerate(documents):  # 遍历文档列表
            keyword_score = self._calculate_keyword_score(query, doc)  # 计算关键词匹配分数
            # 简单重排序，保留原始分数
            combined_score = keyword_score  # 使用关键词分数作为最终分数
            results.append(RerankerResult(doc, combined_score, i))  # 添加到结果列表

        # 按分数降序排序
        results.sort(key=lambda x: x.score, reverse=True)  # lambda 匿名函数指定排序键，reverse=True 降序

        logger.info(f"Simple reranked {len(documents)} documents")  # 记录重排序完成
        return results[:top_k]  # 返回前 top_k 个结果


class CohereReranker(BaseReranker):  # 定义 Cohere 重排序器类，使用 Cohere 云端 API
    """
    使用Cohere API进行重排序

    需要COHERE_API_KEY环境变量
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "rerank-multilingual-v2.0"):  # 构造方法
        """
        初始化Cohere Reranker

        Args:
            api_key: Cohere API密钥（默认从环境变量读取）
            model: 使用的模型
        """
        self.api_key = api_key or os.getenv("COHERE_API_KEY")  # 优先使用传入的密钥，否则从环境变量读取
        self.model = model  # 保存模型名称
        self.client = None  # Cohere 客户端实例，初始为 None
        self._load_client()  # 调用客户端初始化方法

    def _load_client(self):  # 定义加载 Cohere 客户端的私有方法
        """加载Cohere客户端"""  # 方法的 docstring
        if not self.api_key:  # 如果没有 API 密钥
            logger.warning("COHERE_API_KEY not found, Cohere Reranker disabled")  # 记录警告
            return  # 提前返回

        try:
            from cohere import Client  # 导入 Cohere SDK 的 Client 类
            self.client = Client(self.api_key)  # 使用 API 密钥创建客户端实例
            logger.info("Cohere Reranker initialized successfully")  # 记录成功
        except ImportError:  # 捕获导入错误（SDK 未安装）
            logger.warning("cohere not installed")  # 记录警告
        except Exception as e:  # 捕获其他异常
            logger.error(f"Failed to initialize Cohere client: {e}")  # 记录错误

    def rerank(  # 重写重排序方法
        self,
        query: str,
        documents: List[Document],
        top_k: int = 3
    ) -> List[RerankerResult]:
        """使用Cohere API进行重排序"""  # 方法的 docstring
        if not documents:  # 如果文档列表为空
            return []

        if self.client is None:  # 如果客户端未初始化
            logger.warning("Cohere client not initialized, returning original order")  # 记录警告
            return [
                RerankerResult(doc, 1.0, i)  # 返回原始顺序
                for i, doc in enumerate(documents[:top_k])
            ]

        try:
            response = self.client.rerank(  # 调用 Cohere 重排序 API
                query=query,  # 查询文本
                documents=[doc.page_content for doc in documents],  # 提取所有文档的文本内容
                model=self.model,  # 使用的模型名称
                top_n=top_k  # 返回前 N 个结果
            )

            results = []  # 初始化结果列表
            for idx, result in enumerate(response.results):  # 遍历 API 返回的结果
                doc_index = result.index  # 获取文档在原始列表中的索引
                results.append(RerankerResult(  # 添加到结果列表
                    documents[doc_index],  # 原始文档对象
                    result.relevance_score,  # API 返回的相关性分数
                    doc_index  # 原始索引
                ))

            logger.info(f"Cohere reranked {len(documents)} documents")  # 记录完成
            return results

        except Exception as e:
            logger.error(f"Cohere reranking failed: {e}")  # 记录错误
            return [
                RerankerResult(doc, 1.0, i)  # 失败时返回原始顺序
                for i, doc in enumerate(documents[:top_k])
            ]


def create_reranker(  # 定义创建重排序器的工厂函数（类似 Java 的工厂模式）
    reranker_type: str = "bge",  # 重排序器类型，默认 "bge"
    config: Optional[Dict[str, Any]] = None  # 配置字典，Optional 表示可选参数
) -> BaseReranker:  # 返回基类类型（多态）
    """
    创建Reranker实例的工厂函数

    Args:
        reranker_type: Reranker类型，可选 'bge', 'cohere', 'simple'
        config: 配置字典

    Returns:
        Reranker实例
    """
    config = config or {}  # 如果 config 为 None 则使用空字典（or 短路求值）

    if reranker_type == "bge":  # 如果类型是 BGE
        return BGEReranker(  # 创建并返回 BGE 重排序器实例
            model_name=config.get("model_name", "BAAI/bge-reranker-base"),  # dict.get(key, default) 安全取值
            use_fp16=config.get("use_fp16", True),  # 是否使用 FP16
            device=config.get("device", None)  # 计算设备
        )
    elif reranker_type == "cohere":  # 如果类型是 Cohere
        return CohereReranker(  # 创建并返回 Cohere 重排序器实例
            api_key=config.get("api_key"),  # API 密钥
            model=config.get("model", "rerank-multilingual-v2.0")  # 模型名称
        )
    elif reranker_type == "simple":  # 如果类型是简单重排序
        return SimpleReranker(  # 创建并返回简单重排序器实例
            alpha=config.get("alpha", 0.5)  # 权重参数
        )
    else:  # 未知类型
        logger.warning(f"Unknown reranker type '{reranker_type}', using simple reranker")  # 记录警告
        return SimpleReranker()  # 默认返回简单重排序器


class HybridReranker(BaseReranker):  # 定义混合重排序器类，融合多个重排序器的结果
    """
    混合重排序器，结合多种Reranker的结果

    使用加权投票的方式融合多个Reranker的结果
    """

    def __init__(self, rerankers: List[Tuple[BaseReranker, float]]):  # 构造方法，接收 (重排序器, 权重) 元组列表
        """
        初始化混合重排序器

        Args:
            rerankers: (Reranker, 权重) 元组列表
        """
        self.rerankers = rerankers  # 保存重排序器列表

    def rerank(  # 重写重排序方法
        self,
        query: str,
        documents: List[Document],
        top_k: int = 3
    ) -> List[RerankerResult]:
        """使用混合策略对文档进行重排序"""  # 方法的 docstring
        if not documents:  # 如果文档列表为空
            return []

        if len(self.rerankers) == 1:  # 如果只有一个重排序器
            return self.rerankers[0][0].rerank(query, documents, top_k)  # 直接使用它，self.rerankers[0] 是第一个元组，[0] 取重排序器

        # 收集所有Reranker的结果
        all_scores = []  # 初始化所有评分列表
        for reranker, weight in self.rerankers:  # 解包元组（类似 Java 的 Map.Entry），分别获取重排序器和权重
            results = reranker.rerank(query, documents, top_k=len(documents))  # 对所有文档进行重排序
            # 归一化分数
            max_score = max(r.score for r in results) if results else 1.0  # 获取最高分，results 为空时默认 1.0
            min_score = min(r.score for r in results) if results else 0.0  # 获取最低分
            score_range = max_score - min_score if max_score != min_score else 1.0  # 计算分数范围，防止除零

            scores = {}  # 初始化当前重排序器的分数字典
            for r in results:  # 遍历结果
                # 归一化到[0,1]
                normalized = (r.score - min_score) / score_range if score_range != 0 else 0.5  # Min-Max 归一化到 [0, 1]
                scores[r.original_index] = normalized * weight  # 乘以权重

            all_scores.append(scores)  # 将当前重排序器的分数字典添加到列表

        # 合并分数
        combined_scores = {}  # 初始化合并后的分数字典
        for i, doc in enumerate(documents):  # 遍历所有文档
            combined_scores[i] = sum(scores.get(i, 0) for scores in all_scores)  # sum 求和所有重排序器对该文档的加权分数，dict.get(i, 0) 找不到键则返回 0

        # 创建结果
        results = [
            RerankerResult(doc, combined_scores[i], i)  # 使用合并后的分数创建结果
            for i, doc in enumerate(documents)  # 列表推导式遍历
        ]

        # 按分数降序排序
        results.sort(key=lambda x: x.score, reverse=True)  # lambda 指定按分数降序

        logger.info(f"Hybrid reranked {len(documents)} documents using {len(self.rerankers)} rerankers")  # 记录完成
        return results[:top_k]  # 返回前 top_k 个结果
