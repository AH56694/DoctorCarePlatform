from typing import Dict, Any, Optional, List  # 导入类型注解：Dict（字典类型）、Any（任意类型）、Optional（可选类型）、List（列表类型）
from agent.state import AgentState, AgentStatus, TerminationCondition  # 从 agent.state 导入：AgentState（状态对象）、AgentStatus（运行状态枚举）、TerminationCondition（终止条件判断器）
from intent.classifier import IntentType  # 从意图分类器模块导入 IntentType（意图类型枚举）
import logging  # 导入 logging 模块，用于日志记录

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器


class RetryPolicy:  # 重试策略类，定义重试次数和延迟计算逻辑
    """重试策略"""  # 类的文档字符串

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):  # 构造函数，self 类似 Java 的 this
        self.max_retries = max_retries  # 最大重试次数，默认 3 次
        self.base_delay = base_delay  # 基础延迟时间（秒），默认 1 秒
        self.max_delay = max_delay  # 最大延迟时间（秒），默认 60 秒

    def should_retry(self, attempt: int, error: Exception) -> bool:  # 判断是否应该重试
        """判断是否应该重试"""  # 方法文档字符串
        if attempt >= self.max_retries:  # 如果已达到最大重试次数
            return False  # 不再重试

        retryable_errors = [  # 可重试的错误关键词列表
            "timeout",  # 超时错误
            "connection",  # 连接错误
            "network",  # 网络错误
            "rate_limit"  # 限流错误
        ]

        error_str = str(error).lower()  # 将错误对象转为小写字符串，用于关键词匹配
        return any(e in error_str for e in retryable_errors)  # any() 判断错误信息中是否包含任一可重试关键词，类似 Java Stream 的 anyMatch()

    def get_delay(self, attempt: int) -> float:  # 计算重试延迟时间（指数退避策略）
        """计算重试延迟（指数退避）"""  # 方法文档字符串
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)  # 指数退避：delay = base_delay * 2^attempt，但不超过 max_delay。min() 取较小值
        return delay  # 返回延迟时间


class FallbackPolicy:  # 降级策略类，当正常处理失败时提供备选响应
    """降级策略"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.fallback_responses = {  # 降级响应字典，键为意图类型，值为降级回复文本
            IntentType.CHITCHAT: "抱歉，我现在无法回应您的问题，让我们换个话题吧。",  # 闲聊的降级响应
            IntentType.KNOWLEDGE_QA: "抱歉，我暂时无法找到相关的知识来回答您的问题。",  # 知识问答的降级响应
            IntentType.UNKNOWN: "抱歉，我无法理解您的问题，请尝试重新描述。"  # 未知意图的降级响应
        }

    def get_fallback(self, intent: str) -> str:  # 根据意图类型获取降级响应
        """获取降级响应"""  # 方法文档字符串
        return self.fallback_responses.get(intent, "抱歉，服务暂时不可用，请稍后再试。")  # dict.get(key, default) 安全获取值，键不存在时返回默认值


class GuardrailsPolicy:  # 安全守卫策略类，检查输入输出的安全性
    """安全守卫策略"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.dangerous_keywords = [  # 危险关键词列表
            "hack", "exploit", "病毒", "木马",  # 黑客攻击相关
            "攻击", "入侵", "破解", "作弊"  # 恶意行为相关
        ]

        self.sensitive_topics = [  # 敏感话题列表
            "政治", "宗教", "色情", "暴力",  # 敏感话题类别
            "赌博", "毒品", "犯罪"  # 违法话题
        ]

        self.output_dangerous_keywords = [  # 输出中可能包含的危险关键词列表
            "密码", "密钥", "隐私", "个人信息",  # 个人隐私信息
            "银行卡", "信用卡", "sensitive", "secret"  # 敏感信息
        ]

        self.output_sensitive_topics = [  # 输出中可能包含的敏感话题列表
            "政治", "宗教", "色情", "暴力",  # 敏感话题类别
            "赌博", "毒品", "犯罪"  # 违法话题
        ]

    def check_input(self, text: str) -> tuple[bool, Optional[str]]:  # 检查输入文本是否安全，返回元组：(是否安全, 错误信息)
        """检查输入是否安全"""  # 方法文档字符串
        if not text:  # 如果文本为空或 None
            return True, None  # 空文本视为安全

        lower_text = text.lower()  # 转为小写，便于不区分大小写匹配

        for keyword in self.dangerous_keywords:  # 遍历危险关键词
            if keyword in lower_text:  # 如果文本包含危险关键词
                return False, f"输入包含敏感关键词: {keyword}"  # f-string 格式化，返回不安全标志和原因

        for topic in self.sensitive_topics:  # 遍历敏感话题
            if topic in text:  # 如果文本包含敏感话题（中文不需要转小写）
                return False, f"输入涉及敏感话题: {topic}"  # 返回不安全标志和原因

        return True, None  # 通过所有检查，返回安全标志

    def check_output(self, text: str) -> tuple[bool, Optional[str]]:  # 检查输出文本是否安全
        """检查输出是否安全"""  # 方法文档字符串
        if not text:  # 如果文本为空或 None
            return True, None  # 空文本视为安全

        lower_text = text.lower()  # 转为小写，便于不区分大小写匹配

        for keyword in self.output_dangerous_keywords:  # 遍历危险关键词
            if keyword in lower_text:  # 如果文本包含危险关键词
                return False, f"让我们换个话题吧"

        for topic in self.output_sensitive_topics:  # 遍历敏感话题
            if topic in text:  # 如果文本包含敏感话题（中文不需要转小写）
                return False, f"让我们换个话题吧"

        return True, None  # 目前不对输出做限制，直接返回安全


class TimeoutPolicy:  # 超时策略类，判断步骤和总执行是否超时
    """超时策略"""  # 类的文档字符串

    def __init__(self, step_timeout: int = 30, total_timeout: int = 300):  # 构造函数
        self.step_timeout = step_timeout  # 单个步骤的超时时间（秒），默认 30 秒
        self.total_timeout = total_timeout  # 总执行超时时间（秒），默认 300 秒（5 分钟）

    def should_timeout_step(self, state: AgentState, step_index: int) -> bool:  # 判断单个步骤是否超时
        """判断步骤是否超时"""  # 方法文档字符串
        step = state.steps[step_index] if step_index < len(state.steps) else None  # 三元表达式：安全获取步骤对象，防止索引越界
        if step and step.start_time:  # 如果步骤存在且已记录开始时间
            import time  # 在方法内部导入 time 模块（延迟导入）
            elapsed = time.time() - step.start_time  # 计算步骤已执行时间
            return elapsed > self.step_timeout  # 判断是否超过步骤超时阈值
        return False  # 步骤不存在或未开始，不算超时

    def should_timeout_total(self, state: AgentState) -> bool:  # 判断总执行是否超时
        """判断总执行是否超时"""  # 方法文档字符串
        return state.elapsed_time > self.total_timeout  # elapsed_time 是 @property，直接当属性访问


class ResponsePolicy:  # 响应策略类，负责格式化最终输出和去重
    """响应策略"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.max_answer_length = 2000  # 答案最大长度（字符数）
        self.max_sources = 5  # 引用来源最大数量

    def format_response(self, answer: str, sources: List[Dict[str, Any]],  # 格式化响应
                        include_sources: bool = True, task_type: str = "knowledge_qa") -> Dict[str, Any]:  # 参数：答案、来源列表、是否包含来源、任务类型
        """格式化响应"""  # 方法文档字符串
        truncated_answer = answer[:self.max_answer_length] if len(answer) > self.max_answer_length else answer  # 如果答案过长则截断，切片语法 answer[:n] 取前 n 个字符

        formatted_sources = self._deduplicate_sources(sources)[:self.max_sources] if sources else []  # 先去重再限制数量，[:self.max_sources] 切片取前 N 个

        return {  # 返回格式化的响应字典
            "answer": truncated_answer,  # 截断后的答案
            "sources": formatted_sources if include_sources else [],  # 如果需要包含来源则返回去重后的列表，否则返回空列表
            "has_sources": len(formatted_sources) > 0 if include_sources else False,  # 是否有引用来源
            "task_type": task_type  # 任务类型
        }

    def _deduplicate_sources(self, sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:  # 对引用源进行去重，下划线前缀表示这是内部方法，类似 Java 的 private
        """对引用源进行去重"""  # 方法文档字符串
        if not sources:  # 如果来源列表为空
            return []  # 返回空列表

        seen_ids = set()  # 创建空集合（Set），用于记录已见过的 ID，Python 的 set 类似 Java 的 HashSet
        unique_sources = []  # 去重后的来源列表

        for source in sources:  # 遍历每个来源
            source_id = None  # 初始化来源 ID
            # 尝试多种可能的ID字段
            if "docId" in source:  # 如果包含 docId 字段（驼峰命名）
                source_id = source["docId"]  # 使用 docId 作为去重依据
            elif "doc_id" in source:  # 如果包含 doc_id 字段（下划线命名）
                source_id = source["doc_id"]  # 使用 doc_id
            elif "id" in source:  # 如果包含 id 字段
                source_id = source["id"]  # 使用 id
            elif "docName" in source:  # 如果包含 docName 字段
                source_id = source["docName"]  # 使用 docName
            elif "doc_name" in source:  # 如果包含 doc_name 字段
                source_id = source["doc_name"]  # 使用 doc_name
            elif "name" in source:  # 如果包含 name 字段
                source_id = source["name"]  # 使用 name
            elif "doc" in source:  # 如果包含 doc 字段
                source_id = source["doc"]  # 使用 doc
            # 如果有content，也可以作为去重依据
            elif "content" in source:  # 如果包含 content 字段
                source_id = str(hash(source["content"]))  # hash() 计算内容的哈希值，str() 转为字符串作为 ID

            if source_id:  # 如果找到了可用的 ID
                if source_id not in seen_ids:  # 如果这个 ID 之前没出现过
                    seen_ids.add(source_id)  # 添加到已见集合中
                    unique_sources.append(source)  # 添加到去重列表
            else:  # 如果没有任何 ID 字段
                # 如果没有ID，直接保留
                unique_sources.append(source)  # 直接添加（不去重）

        return unique_sources  # 返回去重后的来源列表


class AgentPolicies:  # Agent 策略管理器，聚合所有策略，提供统一的策略调用接口（外观模式）
    """Agent策略管理器"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.retry_policy = RetryPolicy()  # 创建重试策略实例
        self.fallback_policy = FallbackPolicy()  # 创建降级策略实例
        self.guardrails_policy = GuardrailsPolicy()  # 创建安全守卫策略实例
        self.timeout_policy = TimeoutPolicy()  # 创建超时策略实例
        self.response_policy = ResponsePolicy()  # 创建响应策略实例

    def validate_input(self, text: str) -> tuple[bool, Optional[str]]:  # 验证输入安全性
        """验证输入"""  # 方法文档字符串
        return self.guardrails_policy.check_input(text)  # 委托给安全守卫策略检查

    def validate_output(self, text: str) -> tuple[bool, Optional[str]]:  # 验证输出安全性
        """验证输出"""  # 方法文档字符串
        return self.guardrails_policy.check_output(text)  # 委托给安全守卫策略检查

    def get_fallback(self, intent: str) -> str:  # 获取降级响应
        """获取降级响应"""  # 方法文档字符串
        return self.fallback_policy.get_fallback(intent)  # 委托给降级策略

    def should_retry(self, attempt: int, error: Exception) -> bool:  # 判断是否应该重试
        """判断是否应该重试"""  # 方法文档字符串
        return self.retry_policy.should_retry(attempt, error)  # 委托给重试策略

    def get_retry_delay(self, attempt: int) -> float:  # 获取重试延迟
        """获取重试延迟"""  # 方法文档字符串
        return self.retry_policy.get_delay(attempt)  # 委托给重试策略

    def format_response(self, answer: str, sources: List[Dict[str, Any]],  # 格式化响应
                       include_sources: bool = True, task_type: str = "knowledge_qa") -> Dict[str, Any]:  # 参数同 ResponsePolicy.format_response
        """格式化响应"""  # 方法文档字符串
        return self.response_policy.format_response(answer, sources, include_sources, task_type)  # 委托给响应策略


policies = AgentPolicies()  # 创建 AgentPolicies 单例实例，模块级全局对象，供其他模块直接 import 使用
