from workflows.knowledge_qa_agent import KnowledgeQAAgent  # 从 knowledge_qa_agent 模块导入 KnowledgeQAAgent 类
from workflows.chitchat_agent import ChitChatAgent  # 从 chitchat_agent 模块导入 ChitChatAgent 类
from workflows.admin_copilot_agent import AdminCopilotAgent  # 从 admin_copilot_agent 模块导入 AdminCopilotAgent 类
from workflows.inspection_agent import InspectionAgent  # 从 inspection_agent 模块导入 InspectionAgent 类
from workflows.router_agent import RouterAgent  # 从 router_agent 模块导入 RouterAgent 类
from workflows.retrieval_agent import RetrievalAgent, retrieval_agent  # 从 retrieval_agent 模块导入 RetrievalAgent 类和全局实例 retrieval_agent
from workflows.ops_agent import OpsAgent, ops_agent  # 从 ops_agent 模块导入 OpsAgent 类和全局实例 ops_agent

__all__ = [  # __all__ 列表定义了 from workflows import * 时会导出的符号（类似 Java 的公共 API 导出）
    "KnowledgeQAAgent",  # 知识问答 Agent 类
    "ChitChatAgent",  # 闲聊 Agent 类
    "AdminCopilotAgent",  # 管理助手 Agent 类
    "InspectionAgent",  # 知识巡检 Agent 类
    "RouterAgent",  # 路由 Agent 类
    "RetrievalAgent",  # 检索 Agent 类
    "retrieval_agent",  # 检索 Agent 的全局实例
    "OpsAgent",  # 运营分析 Agent 类
    "ops_agent"  # 运营分析 Agent 的全局实例
]