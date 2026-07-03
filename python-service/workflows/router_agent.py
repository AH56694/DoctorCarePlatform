from typing import Dict, Any, Optional, Generator  # 导入类型提示（类似 Java 的泛型，Dict 是字典类型，Any 是任意类型，Optional 表示可为 None，Generator 是生成器类型）
from enum import Enum  # 导入枚举基类（类似 Java 的 enum）
from workflows.knowledge_qa_agent import KnowledgeQAAgent  # 从 knowledge_qa_agent 模块导入知识问答 Agent 类
from workflows.chitchat_agent import ChitChatAgent  # 从 chitchat_agent 模块导入闲聊 Agent 类
from workflows.admin_copilot_agent import AdminCopilotAgent  # 从 admin_copilot_agent 模块导入管理助手 Agent 类
from workflows.inspection_agent import InspectionAgent  # 从 inspection_agent 模块导入知识巡检 Agent 类
from workflows.retrieval_agent import RetrievalAgent  # 从 retrieval_agent 模块导入检索 Agent 类
from intent.classifier import IntentClassifier, IntentType  # 从 intent.classifier 模块导入意图分类器和意图类型枚举
import logging  # 导入日志模块（类似 Java 的 log4j/SLF4J）
import json  # 导入 JSON 序列化/反序列化模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器（__name__ 是当前模块名，类似 Java 的 LoggerFactory.getLogger(clazz））


class TaskType(Enum):  # 定义任务类型枚举类，继承自 Enum（类似 Java 的 enum TaskType {...}）
    """任务类型枚举"""
    CHITCHAT = "chitchat"  # 闲聊任务
    KNOWLEDGE_QA = "knowledge_qa"  # 知识问答任务
    ADMIN_COPILOT = "admin_copilot"  # 管理助手任务
    KNOWLEDGE_INSPECTION = "knowledge_inspection"  # 知识巡检任务
    REASONING = "reasoning"  # 复杂推理任务
    UNKNOWN = "unknown"  # 未知任务类型


class RouterAgent:  # 定义路由 Agent 类（类似 Java 的 class RouterAgent）
    """路由Agent - 负责将用户请求路由到合适的工作流"""

    def __init__(self):  # 构造函数（类似 Java 的 constructor）
        self.knowledge_qa_agent = KnowledgeQAAgent()  # 初始化知识问答 Agent 实例（self 类似 Java 的 this）
        self.chitchat_agent = ChitChatAgent()  # 初始化闲聊 Agent 实例
        self.admin_copilot_agent = AdminCopilotAgent()  # 初始化管理助手 Agent 实例
        self.inspection_agent = InspectionAgent()  # 初始化知识巡检 Agent 实例
        self.retrieval_agent = RetrievalAgent()  # 初始化检索 Agent 实例
        self.classifier = IntentClassifier()  # 初始化意图分类器实例
        self._reasoning_agent = None  # 推理 Agent 的延迟加载占位符（_ 前缀表示私有属性，类似 Java 的 private）

    @property  # @property 装饰器：将方法变为属性访问（类似 Java 的 getter，可通过 obj.reasoning_agent 而非 obj.get_reasoning_agent() 访问）
    def reasoning_agent(self):
        """延迟加载 ReasoningAgent"""  # 延迟加载：只有首次访问时才创建实例，避免循环导入问题
        if self._reasoning_agent is None:  # 如果推理 Agent 尚未初始化
            from workflows.reasoning_agent import ReasoningAgent  # 在方法内部导入，避免模块级别的循环依赖（类似 Java 的懒加载）
            self._reasoning_agent = ReasoningAgent()  # 创建推理 Agent 实例
        return self._reasoning_agent  # 返回已缓存的推理 Agent 实例

    def route(self, input_text: str, conversation_id: Optional[str] = None,  # route 方法（: str 是参数类型提示，Optional[str] = None 表示参数可选，默认值为 None）
              user_id: Optional[str] = None, context: str = "",
              is_admin: bool = False, **kwargs) -> Dict[str, Any]:  # **kwargs 接收任意关键字参数（类似 Java 的 Map<String, Object>），-> Dict[str, Any] 是返回值类型提示
        """
        路由并执行任务

        Args:
            input_text: 用户输入
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            is_admin: 是否为管理员
            **kwargs: 其他参数

        Returns:
            执行结果
        """
        task_type = self.classify_task(input_text, is_admin)  # 调用分类方法，确定任务类型
        logger.info(f"[RouterAgent] Routing to: {task_type.value} for input: {input_text[:50]}...")  # f-string 格式化字符串（类似 Java 的 String.format），task_type.value 获取枚举值

        try:  # try-except 异常处理（类似 Java 的 try-catch）
            if task_type == TaskType.CHITCHAT:  # 判断任务类型是否为闲聊
                return self.chitchat_agent.chat(  # 调用闲聊 Agent 的 chat 方法处理
                    input_text, conversation_id, user_id, context, **kwargs  # **kwargs 将字典解包为关键字参数（类似 Java 的可变参数传递）
                )

            elif task_type == TaskType.KNOWLEDGE_QA:  # 判断任务类型是否为知识问答
                return self.knowledge_qa_agent.ask(  # 调用知识问答 Agent 的 ask 方法处理
                    input_text, conversation_id, user_id, context, **kwargs
                )

            elif task_type == TaskType.ADMIN_COPILOT:  # 判断任务类型是否为管理助手
                return self.admin_copilot_agent.handle(  # 调用管理助手 Agent 的 handle 方法处理
                    input_text, conversation_id, user_id, context, **kwargs
                )

            elif task_type == TaskType.KNOWLEDGE_INSPECTION:  # 判断任务类型是否为知识巡检
                # 从输入中解析巡检类型
                inspection_type = self._parse_inspection_type(input_text)  # 解析巡检的具体类型（重复、低质量等）
                return self.inspection_agent.inspect(  # 调用知识巡检 Agent 的 inspect 方法处理
                    inspection_type, conversation_id, user_id, context, **kwargs
                )

            elif task_type == TaskType.REASONING:  # 判断任务类型是否为复杂推理
                return self.reasoning_agent.reason(  # 调用推理 Agent 的 reason 方法（通过 @property 延迟加载）
                    input_text, context, conversation_id
                )

            else:  # 其他未知类型，默认走知识问答链路
                return self.knowledge_qa_agent.ask(
                    input_text, conversation_id, user_id, context, **kwargs
                )
        except Exception as e:  # 捕获所有异常（类似 Java 的 catch (Exception e)）
            logger.error(f"[RouterAgent] Route error: {str(e)}")  # 记录错误日志
            return {  # 返回错误响应字典（类似 Java 的 Map）
                "answer": "抱歉，服务暂时不可用，请稍后再试。",  # 错误提示答案
                "sources": [],  # 空的来源列表
                "has_sources": False,  # 无引用来源
                "task_type": task_type.value,  # 任务类型值
                "error": True,  # 标记为错误响应
                "error_message": str(e)  # 错误信息
            }

    def route_stream(self, input_text: str, conversation_id: Optional[str] = None,
                     user_id: Optional[str] = None, context: str = "",
                     is_admin: bool = False, **kwargs) -> Generator[str, None, None]:  # -> Generator[str, None, None] 表示返回生成器，产出 str 类型，无发送值，无返回值
        """
        流式路由并执行任务

        Args:
            input_text: 用户输入
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            is_admin: 是否为管理员
            **kwargs: 其他参数

        Yields:
            JSON格式的事件流
        """
        task_type = self.classify_task(input_text, is_admin)  # 分类任务类型
        logger.info(f"[RouterAgent] Streaming route to: {task_type.value}")  # 记录流式路由日志

        try:
            yield json.dumps({  # yield 关键字：生成器语法，产出值但不终止函数（类似 Java 的 Stream/Flux，每次 yield 返回一个值）
                "type": "routed",  # 事件类型：已路由
                "task_type": task_type.value  # 任务类型值
            })

            if task_type == TaskType.CHITCHAT:  # 闲聊类型的流式处理
                for event in self.chitchat_agent.chat_stream(  # 遍历闲聊 Agent 的流式结果
                    input_text, conversation_id, user_id, context, **kwargs
                ):
                    yield event  # 逐个产出事件（yield from 可简化此写法）

            elif task_type == TaskType.KNOWLEDGE_QA:  # 知识问答类型的流式处理
                for event in self.knowledge_qa_agent.ask_stream(  # 遍历知识问答 Agent 的流式结果
                    input_text, conversation_id, user_id, context, **kwargs
                ):
                    yield event

            elif task_type == TaskType.ADMIN_COPILOT:  # 管理助手类型的流式处理
                for event in self.admin_copilot_agent.handle_stream(  # 遍历管理助手 Agent 的流式结果
                    input_text, conversation_id, user_id, context, **kwargs
                ):
                    yield event

            elif task_type == TaskType.KNOWLEDGE_INSPECTION:  # 知识巡检类型的流式处理
                inspection_type = self._parse_inspection_type(input_text)  # 解析巡检类型
                for event in self.inspection_agent.inspect_stream(  # 遍历知识巡检 Agent 的流式结果
                    inspection_type, conversation_id, user_id, context, **kwargs
                ):
                    yield event

            elif task_type == TaskType.REASONING:  # 推理类型的流式处理（非真正流式，一次性返回结果）
                result = self.reasoning_agent.reason(  # 调用推理 Agent 获取完整结果
                    input_text, context, conversation_id
                )
                yield json.dumps({  # 将完整结果包装为 JSON 事件产出
                    "type": "answer",  # 事件类型：答案
                    "content": result.get("answer", ""),  # .get(key, default) 安全取值，key 不存在时返回默认值
                    "sources": result.get("sources", [])  # 引用来源列表
                })

            else:  # 其他未知类型，默认走知识问答流式链路
                for event in self.knowledge_qa_agent.ask_stream(
                    input_text, conversation_id, user_id, context, **kwargs
                ):
                    yield event

        except Exception as e:
            logger.error(f"[RouterAgent] Stream route error: {str(e)}")  # 记录流式路由错误
            yield json.dumps({  # 产出错误事件
                "type": "error",  # 事件类型：错误
                "content": str(e)  # 错误信息
            })

    def classify_task(self, input_text: str, is_admin: bool = False) -> TaskType:  # -> TaskType 表示返回值类型为 TaskType 枚举
        """
        分类任务类型 - 委托给统一分类器

        Args:
            input_text: 用户输入
            is_admin: 是否为管理员

        Returns:
            任务类型
        """
        result = self.classifier.classify(input_text, is_admin)  # 调用意图分类器进行分类

        # 将IntentType映射到TaskType
        intent_to_task = {  # 字典映射（类似 Java 的 Map/EnumMap）
            IntentType.CHITCHAT: TaskType.CHITCHAT,  # 闲聊意图 -> 闲聊任务
            IntentType.KNOWLEDGE_QA: TaskType.KNOWLEDGE_QA,  # 知识问答意图 -> 知识问答任务
            IntentType.ADMIN_OPERATION: TaskType.ADMIN_COPILOT,  # 管理操作意图 -> 管理助手任务
            IntentType.KNOWLEDGE_INSPECTION: TaskType.KNOWLEDGE_INSPECTION,  # 知识巡检意图 -> 知识巡检任务
            IntentType.IDENTITY_QUERY: TaskType.CHITCHAT,  # 身份查询意图 -> 归类为闲聊任务
            IntentType.UNKNOWN: TaskType.KNOWLEDGE_QA,  # 未知意图 -> 默认走知识问答
        }

        task_type = intent_to_task.get(result.intent, TaskType.KNOWLEDGE_QA)  # 根据分类结果的意图类型查找对应任务类型，未匹配则默认为知识问答

        # KNOWLEDGE_QA 进一步判断复杂度，可能升级为 REASONING
        if task_type == TaskType.KNOWLEDGE_QA:  # 如果是知识问答类型
            complexity = self.classify_complexity(input_text)  # 进一步判断问题复杂度
            if complexity == "complex":  # 如果复杂度为"复杂"
                return TaskType.REASONING  # 升级为推理任务类型

        return task_type  # 返回最终的任务类型

    def classify_complexity(self, input_text: str) -> str:
        """
        判断问题复杂度，决定走哪条链路

        Returns:
            "simple"  — L1：直接检索+生成
            "medium" — L2：问题改写+检索+重排序+生成
            "complex" — L3：分解子问题+逐个推理+汇总
        """
        # L3：复杂问题指标（对比、分析、归纳类）
        l3_indicators = ["对比", "比较", "优缺点", "区别", "异同",  # 复杂问题的关键词列表
                         "分析", "总结", "归纳", "评估", "权衡"]
        if any(ind in input_text for ind in l3_indicators) and len(input_text) > 15:  # any() 只要有一个为 True 就返回 True（类似 Java 的 stream().anyMatch()）；ind in input_text 判断子字符串是否存在
            return "complex"  # 返回复杂级别

        # L2：需要改写/上下文的指标
        l2_indicators = ["它", "这个", "那个", "上面", "之前", "刚才"]  # 指代词列表，说明需要上下文理解
        has_pronoun = any(ind in input_text for ind in l2_indicators)  # 检查是否包含指代词

        if has_pronoun or len(input_text.strip()) < 10:  # .strip() 去除首尾空白字符；如果包含指代词或问题过短
            return "medium"  # 返回中等级别，需要问题改写

        # L1：简单问题
        return "simple"  # 返回简单级别

    def _parse_inspection_type(self, input_text: str) -> str:  # _ 前缀表示私有方法（类似 Java 的 private）
        """从输入中解析巡检类型"""
        lower_text = input_text.lower()  # .lower() 将字符串转为小写（类似 Java 的 toLowerCase()）

        if "重复" in lower_text:  # in 关键字判断子字符串是否存在（类似 Java 的 contains()）
            return "duplicate"  # 返回重复文档检测类型
        elif "低质量" in lower_text or "质量" in lower_text or "片段" in lower_text:  # or 是逻辑或（类似 Java 的 ||）
            return "low_quality"  # 返回低质量片段检测类型
        elif "过期" in lower_text or "陈旧" in lower_text:
            return "stale"  # 返回过期知识检测类型
        elif "无人访问" in lower_text or "没人看" in lower_text or "访问" in lower_text:
            return "unpopular"  # 返回无人访问文档检测类型
        else:
            return "full"  # 默认返回完整巡检类型

    def get_agent(self, task_type: TaskType):  # 根据 TaskType 枚举获取对应的 Agent 实例
        """获取对应的Agent"""
        agent_map = {  # 任务类型到 Agent 实例的映射字典
            TaskType.CHITCHAT: self.chitchat_agent,  # 闲聊 -> 闲聊 Agent
            TaskType.KNOWLEDGE_QA: self.knowledge_qa_agent,  # 知识问答 -> 知识问答 Agent
            TaskType.ADMIN_COPILOT: self.admin_copilot_agent,  # 管理助手 -> 管理助手 Agent
            TaskType.KNOWLEDGE_INSPECTION: self.inspection_agent,  # 知识巡检 -> 知识巡检 Agent
            TaskType.REASONING: self.reasoning_agent,  # 推理 -> 推理 Agent（通过 @property 延迟加载）
        }
        return agent_map.get(task_type, self.knowledge_qa_agent)  # 从映射中获取 Agent，未匹配则默认返回知识问答 Agent

    def get_task_stats(self) -> Dict[str, int]:  # -> Dict[str, int] 表示返回键为字符串、值为整数的字典
        """获取各类关键词数量统计（用于调试和分析）"""
        return self.classifier.get_keyword_stats()  # 委托给分类器获取关键词统计