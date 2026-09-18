from dataclasses import dataclass, field  # 导入 dataclass（类装饰器，自动生成 __init__、__repr__ 等方法，类似 Java 的 Lombok @Data）和 field（字段定义函数，用于配置字段属性）
from typing import Dict, Any, Optional, List, Union  # 导入类型注解：Dict（字典类型）、Any（任意类型）、Optional（可选类型，类似 Java 的 @Nullable）、List（列表类型）、Union（联合类型）
from enum import Enum  # 导入 Enum（枚举基类，类似 Java 的 enum），用于定义一组命名常量
import uuid  # 导入 uuid 模块，用于生成唯一标识符（UUID），类似 Java 的 java.util.UUID
import time  # 导入 time 模块，用于获取时间戳和计时


class AgentStatus(Enum):  # 定义 AgentStatus 枚举类，继承自 Enum，表示 Agent 的运行状态，类似 Java 的 enum AgentStatus {...}
    """Agent 运行状态"""  # 类的文档字符串
    PENDING = "pending"  # 待执行状态，Agent 已创建但尚未开始运行
    RUNNING = "running"  # 运行中状态，Agent 正在执行任务
    COMPLETED = "completed"  # 已完成状态，Agent 成功执行完毕
    FAILED = "failed"  # 失败状态，Agent 执行过程中出错
    INTERRUPTED = "interrupted"  # 中断状态，Agent 被外部强制中断
    WAITING = "waiting"  # 等待状态，Agent 等待用户输入（如需要澄清）


class StepStatus(Enum):  # 定义 StepStatus 枚举类，继承自 Enum，表示步骤的执行状态
    """步骤状态"""  # 类的文档字符串
    PENDING = "pending"  # 待执行状态
    RUNNING = "running"  # 运行中状态
    COMPLETED = "completed"  # 已完成状态
    FAILED = "failed"  # 失败状态
    SKIPPED = "skipped"  # 跳过状态


class StepType(Enum):  # 定义 StepType 枚举类，继承自 Enum，表示步骤的类型
    """步骤类型"""  # 类的文档字符串
    INTENT_RECOGNITION = "intent_recognition"  # 意图识别步骤，识别用户输入的意图
    QUESTION_CLASSIFICATION = "question_classification"  # 问题分类步骤，对问题进行分类
    CLARIFICATION = "clarification"  # 澄清步骤，判断是否需要向用户提问以澄清意图
    QUESTION_REWRITE = "question_rewrite"  # 问题改写步骤，优化用户问题以提升检索效果
    KNOWLEDGE_SEARCH = "knowledge_search"  # 知识检索步骤，从向量数据库中检索相关文档
    RESULT_EVALUATION = "result_evaluation"  # 结果评估步骤，评估检索结果的充分性
    ANSWER_GENERATION = "answer_generation"  # 答案生成步骤，基于检索结果生成最终回答
    MEMORY_READ = "memory_read"  # 记忆读取步骤，加载会话历史和用户画像
    MEMORY_WRITE = "memory_write"  # 记忆写入步骤，保存对话到记忆系统
    MEMORY_COMPRESS = "memory_compress"  # 记忆压缩步骤，对过长的对话历史进行压缩
    TOOL_CALL = "tool_call"  # 工具调用步骤，调用外部工具执行操作


@dataclass  # @dataclass 装饰器，自动生成 __init__、__repr__、__eq__ 等方法，类似 Java Lombok 的 @Data 注解
class AgentStep:  # 定义 AgentStep 数据类，表示 Agent 执行流程中的一个步骤
    """Agent 步骤"""  # 类的文档字符串
    step_id: str  # 步骤唯一标识符，UUID 格式
    step_type: StepType  # 步骤类型，使用上面定义的 StepType 枚举
    step_name: str  # 步骤名称，用于标识步骤的字符串
    status: StepStatus = StepStatus.PENDING  # 步骤状态，默认为 PENDING（待执行）
    input_data: Dict[str, Any] = field(default_factory=dict)  # 输入数据，field(default_factory=dict) 表示默认值为空字典（注意不能直接写 ={}，因为可变默认参数会被所有实例共享）
    output_data: Dict[str, Any] = field(default_factory=dict)  # 输出数据，默认值为空字典
    error_message: Optional[str] = None  # 错误信息，Optional[str] 表示可以是 str 或 None，类似 Java 的 @Nullable String
    start_time: Optional[float] = None  # 步骤开始时间（时间戳），None 表示尚未开始
    end_time: Optional[float] = None  # 步骤结束时间（时间戳），None 表示尚未结束
    tool_call_id: Optional[str] = None  # 工具调用的唯一标识符，用于追踪工具调用

    def start(self):  # 定义 start 方法，将步骤状态设为运行中并记录开始时间
        """开始执行步骤"""  # 方法文档字符串
        self.status = StepStatus.RUNNING  # self 类似 Java 的 this，将状态设为 RUNNING
        self.start_time = time.time()  # time.time() 返回当前时间的浮点秒数（Unix 时间戳）

    def complete(self, output_data: Dict[str, Any]):  # 定义 complete 方法，标记步骤完成并保存输出数据
        """完成步骤"""  # 方法文档字符串
        self.status = StepStatus.COMPLETED  # 将状态设为 COMPLETED
        self.output_data = output_data  # 保存输出数据
        self.end_time = time.time()  # 记录结束时间

    def fail(self, error_message: str):  # 定义 fail 方法，标记步骤失败并记录错误信息
        """步骤失败"""  # 方法文档字符串
        self.status = StepStatus.FAILED  # 将状态设为 FAILED
        self.error_message = error_message  # 保存错误信息
        self.end_time = time.time()  # 记录结束时间

    def skip(self):  # 定义 skip 方法，跳过当前步骤
        """跳过步骤"""  # 方法文档字符串
        self.status = StepStatus.SKIPPED  # 将状态设为 SKIPPED
        self.end_time = time.time()  # 记录结束时间

    @property  # @property 装饰器将方法变成属性访问，调用时不需要括号，类似 Java 的 getter 方法。用法：step.duration_ms 而不是 step.duration_ms()
    def duration_ms(self) -> Optional[float]:  # 定义计算步骤执行时长（毫秒）的属性方法
        """获取步骤执行时长（毫秒）"""  # 方法文档字符串
        if self.start_time and self.end_time:  # 如果开始时间和结束时间都存在
            return (self.end_time - self.start_time) * 1000  # 计算时间差并转换为毫秒
        return None  # 如果缺少时间信息，返回 None


@dataclass  # @dataclass 装饰器，自动生成构造函数等方法
class IntermediateConclusion:  # 定义中间结论数据类，用于保存步骤执行过程中产生的中间判断结果
    """中间结论"""  # 类的文档字符串
    step_id: str  # 产生此结论的步骤 ID
    conclusion_type: str  # 结论类型，如 "intent"（意图）、"retrieval"（检索）等
    content: Any  # 结论内容，可以是任意类型（字符串、字典等）
    confidence: float = 0.0  # 置信度，0.0 到 1.0 之间的浮点数，默认 0.0
    sources: List[Dict[str, Any]] = field(default_factory=list)  # 引用来源列表，默认为空列表


@dataclass  # @dataclass 装饰器
class ToolCallRecord:  # 定义工具调用记录数据类，记录一次工具调用的完整信息
    """工具调用记录"""  # 类的文档字符串
    tool_call_id: str  # 工具调用的唯一标识符
    tool_name: str  # 工具名称
    input_params: Dict[str, Any]  # 输入参数字典
    output: Dict[str, Any]  # 输出结果字典
    status: str  # 调用状态字符串
    duration_ms: float  # 调用耗时（毫秒）
    error_message: Optional[str] = None  # 错误信息，如果没有错误则为 None
    timestamp: float = field(default_factory=lambda: time.time())  # 调用时间戳，lambda 创建匿名函数作为工厂，每次创建实例时调用 time.time() 获取当前时间


@dataclass  # @dataclass 装饰器
class AgentState:  # 定义 Agent 状态数据类，保存 Agent 执行过程中的所有状态信息
    """Agent 状态"""  # 类的文档字符串

    # 核心标识
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # 运行 ID，每次创建实例时自动生成一个 UUID 字符串，类似 Java 的 UUID.randomUUID().toString()
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))  # 链路追踪 ID，用于分布式追踪
    conversation_id: Optional[str] = None  # 会话 ID，关联到具体的对话会话
    user_id: Optional[str] = None  # 用户 ID，标识当前用户

    # 当前状态
    status: AgentStatus = AgentStatus.PENDING  # Agent 当前状态，默认为 PENDING

    # 目标与输入
    goal: Optional[str] = None  # Agent 的执行目标描述
    original_input: Optional[str] = None  # 用户的原始输入文本
    context: str = ""  # 上下文信息，如对话历史等

    patient: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    searched_queries: List[str] = field(default_factory=list)
    decision_count: int = 0
    task_type: str = "unknown"
    stop_reason: Optional[str] = None
    pending_answer: Optional[Dict[str, Any]] = field(default=None, repr=False)

    # 步骤管理
    current_step_index: int = 0  # 当前执行的步骤索引，类似 Java 数组的下标
    steps: List[AgentStep] = field(default_factory=list)  # 已执行的步骤列表
    planned_steps: List[str] = field(default_factory=list)  # 计划执行的步骤名称列表

    # 中间结论
    intermediate_conclusions: List[IntermediateConclusion] = field(default_factory=list)  # 中间结论列表

    # 工具调用记录
    tool_calls: List[ToolCallRecord] = field(default_factory=list)  # 工具调用记录列表

    # 最终输出
    final_output: Optional[Dict[str, Any]] = None  # Agent 的最终输出结果

    # 错误信息
    error_message: Optional[str] = None  # 错误信息文本
    error_code: Optional[str] = None  # 错误码

    # 时间戳
    start_time: Optional[float] = None  # Agent 开始执行的时间戳
    end_time: Optional[float] = None  # Agent 结束执行的时间戳

    # 配置参数
    max_steps: int = 20  # 最大允许步骤数，防止无限循环
    timeout_seconds: int = 300  # 超时时间（秒），默认 5 分钟

    @property  # @property 装饰器，将方法变为属性访问，用法：state.current_step 而不是 state.current_step()
    def current_step(self) -> Optional[AgentStep]:  # 定义获取当前执行步骤的属性
        """获取当前步骤"""  # 方法文档字符串
        if 0 <= self.current_step_index < len(self.steps):  # 检查索引是否在有效范围内
            return self.steps[self.current_step_index]  # 返回当前步骤对象
        return None  # 索引越界则返回 None

    @property  # @property 装饰器
    def elapsed_time(self) -> float:  # 定义获取已执行时间的属性，单位为秒
        """获取已执行时间（秒）"""  # 方法文档字符串
        if self.start_time:  # 如果已经开始计时
            return (self.end_time or time.time()) - self.start_time
        return 0.0  # 尚未开始则返回 0.0

    @property  # @property 装饰器
    def is_timeout(self) -> bool:  # 定义判断是否超时的属性
        """检查是否超时"""  # 方法文档字符串
        return self.elapsed_time > self.timeout_seconds  # 已用时间超过超时阈值则返回 True

    @property  # @property 装饰器
    def is_max_steps_reached(self) -> bool:  # 定义判断是否达到最大步骤数的属性
        """检查是否达到最大步骤数"""  # 方法文档字符串
        return len([s for s in self.steps if s.status in [StepStatus.COMPLETED, StepStatus.FAILED]]) >= self.max_steps  # 列表推导式（类似 Java Stream 的 filter+count）：筛选已完成或失败的步骤，检查数量是否达到上限

    def add_step(self, step_type: StepType, step_name: str, input_data: Optional[Dict[str, Any]] = None) -> AgentStep:  # 添加新步骤到步骤列表
        """添加新步骤"""  # 方法文档字符串
        step = AgentStep(  # 创建新的 AgentStep 实例
            step_id=str(uuid.uuid4()),  # 生成唯一的步骤 ID
            step_type=step_type,  # 设置步骤类型
            step_name=step_name,  # 设置步骤名称
            input_data=input_data or {}  # 如果 input_data 为 None 则使用空字典，Python 的 or 短路特性
        )
        self.steps.append(step)
        self.current_step_index = len(self.steps) - 1
        return step  # 返回新创建的步骤对象

    def advance_step(self) -> bool:  # 推进步骤索引到下一步
        """推进到下一步"""  # 方法文档字符串
        if self.current_step_index < len(self.steps) - 1:  # 如果当前索引还未到达最后一步
            self.current_step_index += 1  # 索引加 1，移到下一步
            return True  # 推进成功
        return False  # 已经是最后一步，无法推进

    def add_intermediate_conclusion(self, step_id: str, conclusion_type: str, content: Any,  # 添加中间结论
                                   confidence: float = 0.0, sources: Optional[List[Dict[str, Any]]] = None):  # 参数：步骤ID、结论类型、内容、置信度、来源列表
        """添加中间结论"""  # 方法文档字符串
        conclusion = IntermediateConclusion(  # 创建中间结论实例
            step_id=step_id,  # 关联的步骤 ID
            conclusion_type=conclusion_type,  # 结论类型
            content=content,  # 结论内容
            confidence=confidence,  # 置信度
            sources=sources or []  # 来源列表，如果为 None 则使用空列表
        )
        self.intermediate_conclusions.append(conclusion)  # 将结论添加到中间结论列表

    def add_tool_call(self, tool_call_id: str, tool_name: str, input_params: Dict[str, Any],  # 添加工具调用记录
                      output: Dict[str, Any], status: str, duration_ms: float, error_message: Optional[str] = None):  # 参数包括调用ID、名称、输入、输出、状态、耗时、错误信息
        """添加工具调用记录"""  # 方法文档字符串
        record = ToolCallRecord(  # 创建工具调用记录实例
            tool_call_id=tool_call_id,  # 调用 ID
            tool_name=tool_name,  # 工具名称
            input_params=input_params,  # 输入参数
            output=output,  # 输出结果
            status=status,  # 调用状态
            duration_ms=duration_ms,  # 耗时
            error_message=error_message  # 错误信息
        )
        self.tool_calls.append(record)  # 将记录添加到工具调用记录列表

    def start(self):  # 开始执行 Agent
        """开始执行"""  # 方法文档字符串
        self.status = AgentStatus.RUNNING  # 将状态设为运行中
        self.start_time = time.time()  # 记录开始时间

    def complete(self, final_output: Dict[str, Any]):  # 完成 Agent 执行
        """完成执行"""  # 方法文档字符串
        self.status = AgentStatus.COMPLETED  # 将状态设为已完成
        self.final_output = final_output  # 保存最终输出
        self.end_time = time.time()  # 记录结束时间

    def fail(self, error_message: str, error_code: Optional[str] = None):  # 标记 Agent 执行失败
        """执行失败"""  # 方法文档字符串
        self.status = AgentStatus.FAILED  # 将状态设为失败
        self.error_message = error_message  # 保存错误信息
        self.error_code = error_code  # 保存错误码
        self.end_time = time.time()  # 记录结束时间

    def interrupt(self):  # 中断 Agent 执行
        """中断执行"""  # 方法文档字符串
        self.status = AgentStatus.INTERRUPTED  # 将状态设为中断
        self.end_time = time.time()  # 记录结束时间

    def wait(self):  # 将 Agent 设为等待状态
        """等待状态"""  # 方法文档字符串
        self.status = AgentStatus.WAITING  # 将状态设为等待（等待用户输入）

    def to_dict(self) -> Dict[str, Any]:  # 将 Agent 状态序列化为字典，方便转为 JSON
        """转换为字典"""  # 方法文档字符串
        return {  # 返回包含所有状态信息的字典
            "run_id": self.run_id,  # 运行 ID
            "trace_id": self.trace_id,  # 链路追踪 ID
            "conversation_id": self.conversation_id,  # 会话 ID
            "user_id": self.user_id,  # 用户 ID
            "status": self.status.value,  # .value 获取枚举的原始字符串值，如 AgentStatus.PENDING.value == "pending"
            "goal": self.goal,  # 执行目标
            "original_input": self.original_input,  # 原始输入
            "context": self.context,  # 上下文
            "patient": self.patient,
            "evidence": self.evidence,
            "searched_queries": self.searched_queries,
            "decision_count": self.decision_count,
            "task_type": self.task_type,
            "stop_reason": self.stop_reason,
            "current_step_index": self.current_step_index,  # 当前步骤索引
            "steps": [  # 步骤列表，使用列表推导式（类似 Java Stream 的 map）将每个步骤转为字典
                {
                    "step_id": step.step_id,  # 步骤 ID
                    "step_type": step.step_type.value,  # 步骤类型的字符串值
                    "step_name": step.step_name,  # 步骤名称
                    "status": step.status.value,  # 步骤状态的字符串值
                    "input_data": step.input_data,  # 输入数据
                    "output_data": step.output_data,  # 输出数据
                    "error_message": step.error_message,  # 错误信息
                    "duration_ms": step.duration_ms,  # 耗时（毫秒）
                    "tool_call_id": step.tool_call_id  # 工具调用 ID
                }
                for step in self.steps  # 遍历所有步骤
            ],
            "planned_steps": self.planned_steps,  # 计划执行的步骤名称列表
            "intermediate_conclusions": [  # 中间结论列表
                {
                    "step_id": c.step_id,  # 关联的步骤 ID
                    "conclusion_type": c.conclusion_type,  # 结论类型
                    "content": c.content,  # 结论内容
                    "confidence": c.confidence,  # 置信度
                    "sources": c.sources  # 引用来源
                }
                for c in self.intermediate_conclusions  # 遍历所有中间结论
            ],
            "tool_calls": [  # 工具调用记录列表
                {
                    "tool_call_id": tc.tool_call_id,  # 调用 ID
                    "tool_name": tc.tool_name,  # 工具名称
                    "input_params": tc.input_params,  # 输入参数
                    "output": tc.output,  # 输出结果
                    "status": tc.status,  # 调用状态
                    "duration_ms": tc.duration_ms,  # 耗时
                    "error_message": tc.error_message,  # 错误信息
                    "timestamp": tc.timestamp  # 调用时间戳
                }
                for tc in self.tool_calls  # 遍历所有工具调用记录
            ],
            "final_output": self.final_output,  # 最终输出
            "error_message": self.error_message,  # 错误信息
            "error_code": self.error_code,  # 错误码
            "start_time": self.start_time,  # 开始时间
            "end_time": self.end_time,  # 结束时间
            "elapsed_time": self.elapsed_time,  # 已用时间
            "max_steps": self.max_steps,  # 最大步骤数
            "timeout_seconds": self.timeout_seconds  # 超时时间
        }


class TerminationCondition:  # 终止条件判断器，提供静态方法判断 Agent 是否应该终止
    """终止条件判断器"""  # 类的文档字符串

    @staticmethod  # @staticmethod 装饰器，声明静态方法，不需要 self 或 cls 参数，类似 Java 的 static 方法
    def should_terminate(state: AgentState) -> bool:  # 判断 Agent 是否应该终止
        """判断是否应该终止"""  # 方法文档字符串
        return any([  # any() 函数：只要列表中有一个为 True 就返回 True，类似 Java 的 Stream.anyMatch()
            state.status in [AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.INTERRUPTED],  # 状态已是终态（完成/失败/中断）
            state.is_timeout,  # 执行超时
            state.is_max_steps_reached  # 达到最大步骤数
        ])

    @staticmethod  # 静态方法
    def should_fail(state: AgentState) -> bool:  # 判断 Agent 是否应该标记为失败
        """判断是否应该标记为失败"""  # 方法文档字符串
        # 检查是否有失败的步骤
        failed_steps = [s for s in state.steps if s.status == StepStatus.FAILED]  # 列表推导式：筛选所有失败的步骤
        return len(failed_steps) > 0  # 如果有失败的步骤则返回 True

    @staticmethod  # 静态方法
    def get_termination_reason(state: AgentState) -> str:  # 获取终止原因的描述字符串
        """获取终止原因"""  # 方法文档字符串
        if state.status == AgentStatus.COMPLETED:  # 如果状态是已完成
            return "任务已完成"  # 返回完成原因
        elif state.status == AgentStatus.FAILED:  # 如果状态是失败
            return f"任务失败: {state.error_message or '未知原因'}"  # f-string 格式化字符串，类似 Java 的 String.format()
        elif state.status == AgentStatus.INTERRUPTED:  # 如果状态是中断
            return "任务已中断"  # 返回中断原因
        elif state.is_timeout:  # 如果执行超时
            return f"任务超时（超过 {state.timeout_seconds} 秒）"  # 返回超时原因
        elif state.is_max_steps_reached:  # 如果达到最大步骤数
            return f"达到最大步骤数（{state.max_steps} 步）"  # 返回步骤数限制原因
        return "正常运行中"  # 默认返回正常运行
