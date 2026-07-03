from tools.registry import tool_registry  # 从 registry 模块导入全局工具注册器单例（类似 Java 的 Spring Bean 容器）
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类（类似 Java 的抽象父类和 DTO）
from tools.question_rewrite import QuestionRewriteTool  # 导入问题重写工具类
from tools.knowledge_search import KnowledgeSearchTool  # 导入知识库检索工具类
from tools.rerank import RerankTool  # 导入重排序工具类
from tools.memory_read import ConversationMemoryReadTool as MemoryReadTool  # 导入对话记忆读取工具，并用 as 起别名（类似 Java 的 import ... as）
from tools.memory_write import ConversationMemoryWriteTool as MemoryWriteTool  # 导入对话记忆写入工具，起别名
from tools.doc_summary import DocSummaryTool  # 导入文档摘要工具类
from tools.ocr_extract import OCRExtractTool as OCRTool  # 导入 OCR 文字提取工具，起别名 OCRTool
from tools.execution import tool_execution_tracker  # 导入全局工具执行跟踪器单例


def register_all_tools():  # 定义注册所有工具的函数（模块加载时自动调用）
    """注册所有可用工具"""
    tools = [  # 创建所有工具实例的列表（类似 Java 中 new 各个 Tool 实现类放入 List）
        QuestionRewriteTool(),  # 实例化问题重写工具
        KnowledgeSearchTool(),  # 实例化知识库检索工具
        RerankTool(),  # 实例化重排序工具
        MemoryReadTool(),  # 实例化对话记忆读取工具
        MemoryWriteTool(),  # 实例化对话记忆写入工具
        DocSummaryTool(),  # 实例化文档摘要工具
        OCRTool(),  # 实例化 OCR 文字提取工具
    ]

    for tool in tools:  # 遍历所有工具实例（类似 Java 的 for-each 循环）
        try:  # 尝试注册每个工具（类似 Java 的 try-catch）
            tool_registry.register_tool(tool)  # 将工具注册到全局注册器（类似 Java 的注册表模式）
        except Exception as e:  # 捕获注册过程中的异常
            import logging  # 延迟导入 logging 模块（仅在异常时才导入，减少不必要的模块加载）
            logging.getLogger(__name__).warning(f"Failed to register tool {tool.name}: {e}")  # 记录警告日志


register_all_tools()  # 模块加载时自动执行注册（类似 Java 的 static 初始化块）


__all__ = [  # 定义模块的公开导出列表（类似 Java 的 public 接口，控制 from tools import * 时导出的内容）
    "tool_registry",  # 全局工具注册器
    "tool_execution_tracker",  # 全局工具执行跟踪器
    "Tool",  # 工具抽象基类
    "ToolSchema",  # 工具 Schema 数据类
    "SchemaProperty",  # Schema 属性数据类
    "ToolMetadata",  # 工具元数据数据类
    "QuestionRewriteTool",  # 问题重写工具
    "KnowledgeSearchTool",  # 知识库检索工具
    "RerankTool",  # 重排序工具
    "MemoryReadTool",  # 对话记忆读取工具
    "MemoryWriteTool",  # 对话记忆写入工具
    "DocSummaryTool",  # 文档摘要工具
    "OCRTool",  # OCR 文字提取工具
    "register_all_tools",  # 注册所有工具的函数
]
