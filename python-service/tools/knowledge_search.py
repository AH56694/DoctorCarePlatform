from typing import Dict, Any  # 导入类型注解：Dict=字典类型，Any=任意类型
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.vector_store import vector_store  # 导入全局向量存储管理器单例（用于向量相似度检索）
from core.config import config  # 导入全局配置单例


class KnowledgeSearchTool(Tool):  # 知识库检索工具，继承自 Tool 抽象基类（类似 Java 的 extends Tool）
    """知识库检索工具"""

    def __init__(self):  # 构造函数，不需要额外参数（类似 Java 的无参构造器）
        input_schema = ToolSchema(  # 定义输入参数的 Schema（描述工具接收的参数结构）
            properties={  # 参数属性字典
                "query": SchemaProperty(  # 查询语句参数
                    type="string",  # 类型为字符串
                    description="检索查询语句",  # 参数描述
                    required=True  # 必填参数
                ),
                "top_k": SchemaProperty(  # 返回结果数量参数
                    type="number",  # 类型为数字
                    description="返回结果数量",  # 参数描述
                    required=False,  # 非必填
                    default=3  # 默认返回3条
                ),
                "similarity_threshold": SchemaProperty(  # 余弦相似度阈值参数
                    type="number",  # 类型为数字
                    description="余弦相似度阈值（0~1，越大越相似），只返回分数 >= 此阈值的结果",  # 参数描述
                    required=False,  # 非必填
                    default=0.5  # 默认阈值0.5
                ),
                "use_rerank": SchemaProperty(  # 是否使用重排序参数
                    type="boolean",  # 类型为布尔值
                    description="是否使用重排序",  # 参数描述
                    required=False,  # 非必填
                    default=True  # 默认开启重排序
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果的 Schema
            properties={  # 输出属性字典
                "documents": SchemaProperty(  # 文档列表输出
                    type="array",  # 类型为数组
                    description="检索到的文档列表",  # 描述
                    required=True  # 必填
                ),
                "count": SchemaProperty(  # 文档数量输出
                    type="number",  # 类型为数字
                    description="返回的文档数量",  # 描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=10000,  # 超时时间10秒
            max_retries=2,  # 最大重试2次
            permission="user",  # 用户级权限
            description="检索知识库中的相关文档"  # 工具描述
        )

        super().__init__(  # 调用父类 Tool 的构造函数（类似 Java 的 super()）
            name="knowledge_search",  # 工具名称
            description="检索知识库中的相关文档",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

        # 使用共享的向量存储管理器单例
        self.vector_store = vector_store  # 赋值向量存储实例（单例模式，全局共享）

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行知识库检索
        """执行知识库检索"""
        query = parameters.get("query")  # 获取查询语句，get 方法在 key 不存在时返回 None
        top_k = int(parameters.get("top_k", 3))  # 获取返回数量，默认3，转换为 int 类型
        similarity_threshold = parameters.get("similarity_threshold", 0.5)  # 获取余弦相似度阈值，默认0.5
        use_rerank = parameters.get("use_rerank", True)  # 获取是否使用重排序，默认 True

        # 执行检索
        docs = self.vector_store.search(  # 调用向量存储的 search 方法执行检索
            query=query,  # 查询文本
            k=top_k,  # 返回前 k 个结果
            similarity_threshold=similarity_threshold,  # 相似度阈值过滤
            use_rerank=use_rerank  # 是否对结果重排序
        )

        # 格式化结果（同时兼容 documents 和 chunks 两种 key）
        formatted_docs = []  # 初始化格式化后的文档列表
        scores = []  # 初始化分数列表
        for doc in docs:  # 遍历检索到的文档
            formatted_docs.append({  # 将每个文档转为字典格式
                "content": doc.page_content,  # 文档内容（page_content 是 LangChain Document 的属性）
                "metadata": doc.metadata  # 文档元数据（如来源、页码等）
            })
            scores.append(getattr(doc, 'score', 0.5))  # 获取文档的相似度分数，getattr 类似 Java 的反射获取属性，没有则默认0.5

        return {  # 返回结果字典
            "documents": formatted_docs,  # 文档列表（兼容 key: documents）
            "chunks": formatted_docs,  # 文档列表（兼容 key: chunks，与前面对象相同引用）
            "scores": scores,  # 各文档的相似度分数列表
            "count": len(formatted_docs)  # 文档数量（len 类似 Java 的 list.size()）
        }
