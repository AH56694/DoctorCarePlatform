from typing import Dict, Any, List, Optional  # 导入类型注解：Dict=字典，Any=任意类型，List=列表，Optional=可选类型
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.reranker import create_reranker, BaseReranker, RerankerResult  # 导入重排序器工厂方法、基类和结果类
from langchain_core.documents import Document  # 导入 LangChain 的 Document 类（类似 Java 的 POJO，封装文本内容和元数据）
from core.config import config  # 导入全局配置单例


class RerankTool(Tool):  # 重排序工具，继承自 Tool 抽象基类
    """重排序工具 - 对检索结果进行语义重排序"""

    def __init__(self):  # 构造函数
        input_schema = ToolSchema(  # 定义输入参数 Schema
            properties={
                "query": SchemaProperty(  # 查询文本参数
                    type="string",  # 字符串类型
                    description="查询文本",  # 参数描述
                    required=True  # 必填
                ),
                "documents": SchemaProperty(  # 待重排序的文档列表参数
                    type="array",  # 数组类型
                    description="待重排序的文档列表",  # 参数描述
                    required=True  # 必填
                ),
                "top_k": SchemaProperty(  # 返回前 k 个结果参数
                    type="number",  # 数字类型
                    description="返回前k个结果",  # 参数描述
                    required=False,  # 非必填
                    default=3  # 默认返回前3个
                ),
                "reranker_type": SchemaProperty(  # 重排序类型参数
                    type="string",  # 字符串类型
                    description="重排序类型: bge, cohere, simple",  # 参数描述
                    required=False,  # 非必填
                    default="bge"  # 默认使用 bge 重排序模型
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果 Schema
            properties={
                "reranked_documents": SchemaProperty(  # 重排序后的文档列表输出
                    type="array",  # 数组类型
                    description="重排序后的文档列表",  # 描述
                    required=True  # 必填
                ),
                "scores": SchemaProperty(  # 相关性分数列表输出
                    type="array",  # 数组类型
                    description="各文档的相关性分数",  # 描述
                    required=True  # 必填
                ),
                "original_indices": SchemaProperty(  # 原始文档索引列表输出
                    type="array",  # 数组类型
                    description="原始文档索引",  # 描述
                    required=True  # 必填
                ),
                "count": SchemaProperty(  # 返回文档数量输出
                    type="number",  # 数字类型
                    description="返回的文档数量",  # 描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=20000,  # 超时时间20秒
            max_retries=2,  # 最大重试2次
            permission="user",  # 用户级权限
            description="对检索结果进行语义重排序以提高相关性"  # 工具描述
        )

        super().__init__(  # 调用父类构造函数（类似 Java 的 super()）
            name="rerank",  # 工具名称
            description="对检索结果进行语义重排序",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

        self.default_reranker_type = config.RERANKER_TYPE  # 从配置中获取默认的重排序器类型
        self.reranker = self._create_reranker(self.default_reranker_type)  # 创建默认的重排序器实例

    def _create_reranker(self, reranker_type: str) -> Optional[BaseReranker]:  # 私有方法，创建重排序器实例（下划线前缀表示私有）
        """创建Reranker实例"""
        try:  # 尝试创建
            return create_reranker(reranker_type)  # 调用工厂方法创建重排序器（类似 Java 的工厂模式）
        except Exception as e:  # 捕获创建异常
            config.logger.error(f"Failed to create reranker: {e}")  # 记录错误日志
            return None  # 创建失败返回 None（类似 Java 的 null）

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行重排序
        """执行重排序"""
        query = parameters.get("query")  # 获取查询文本
        documents = parameters.get("documents", [])  # 获取文档列表，默认空列表
        top_k = int(parameters.get("top_k", 3))  # 获取返回数量，默认3
        reranker_type = parameters.get("reranker_type", self.default_reranker_type)  # 获取重排序类型，默认使用默认值

        if not documents:  # 如果文档列表为空（空列表是 falsy 值）
            return {  # 返回空结果
                "reranked_documents": [],  # 空文档列表
                "scores": [],  # 空分数列表
                "original_indices": [],  # 空索引列表
                "count": 0  # 数量为0
            }

        docs = self._convert_to_documents(documents)  # 将输入转换为 LangChain Document 对象列表

        reranker = self.reranker  # 使用默认重排序器
        if reranker_type != self.default_reranker_type:  # 如果请求的重排序类型与默认不同
            reranker = self._create_reranker(reranker_type)  # 动态创建指定类型的重排序器

        if reranker is None:  # 如果重排序器不可用（创建失败）
            config.logger.warning("Reranker not available, returning original order")  # 记录警告
            return self._format_results(docs[:top_k], list(range(len(docs[:top_k]))), list(range(len(docs[:top_k]))))  # 返回原始顺序的结果（降级处理）

        try:  # 尝试执行重排序
            results = reranker.rerank(query, docs, top_k=top_k)  # 调用重排序器的 rerank 方法
            reranked_docs = [r.document for r in results]  # 列表推导式提取重排序后的文档（类似 Java 的 stream().map()）
            scores = [r.score for r in results]  # 提取分数列表
            original_indices = [r.original_index for r in results]  # 提取原始索引列表

            config.logger.info(f"Reranked {len(documents)} documents, returning top {len(reranked_docs)}")  # 记录重排序日志

            return self._format_results(reranked_docs, scores, original_indices)  # 格式化并返回结果

        except Exception as e:  # 捕获重排序异常
            config.logger.error(f"Rerank failed: {e}")  # 记录错误日志
            return self._format_results(docs[:top_k], list(range(len(docs[:top_k]))), list(range(len(docs[:top_k]))))  # 降级返回原始顺序

    def _convert_to_documents(self, documents: List[Any]) -> List[Document]:  # 将各种格式的输入统一转换为 LangChain Document 对象
        """将输入转换为Document对象"""
        result = []  # 初始化结果列表
        for doc in documents:  # 遍历输入的文档列表
            if isinstance(doc, Document):  # 如果已经是 Document 类型（isinstance 类似 Java 的 instanceof）
                result.append(doc)  # 直接添加
            elif isinstance(doc, dict):  # 如果是字典类型
                content = doc.get("content", doc.get("page_content", ""))  # 优先取 content，其次取 page_content，默认空字符串
                metadata = doc.get("metadata", {})  # 获取元数据，默认空字典
                result.append(Document(page_content=content, metadata=metadata))  # 创建新的 Document 对象
            elif isinstance(doc, str):  # 如果是纯字符串
                result.append(Document(page_content=doc, metadata={}))  # 用字符串作为内容，空元数据
        return result  # 返回转换后的列表

    def _format_results(self, documents: List[Document], scores: List[float], original_indices: List[int]) -> Dict[str, Any]:  # 格式化重排序结果
        """格式化结果"""
        formatted_docs = []  # 初始化格式化后的文档列表
        for doc in documents:  # 遍历文档
            if isinstance(doc, Document):  # 如果是 Document 类型
                formatted_docs.append({  # 转为字典格式
                    "content": doc.page_content,  # 文档内容
                    "metadata": doc.metadata  # 文档元数据
                })
            else:  # 其他类型直接添加
                formatted_docs.append(doc)  # 保留原始格式

        return {  # 返回格式化结果字典
            "reranked_documents": formatted_docs,  # 重排序后的文档列表
            "scores": scores,  # 相关性分数列表
            "original_indices": original_indices,  # 原始文档索引列表
            "count": len(formatted_docs)  # 文档数量
        }