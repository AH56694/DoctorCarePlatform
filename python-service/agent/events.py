from typing import Dict, Any, Optional, Callable, List  # 导入类型注解：Dict（字典类型）、Any（任意类型）、Optional（可选类型）、Callable（可调用对象类型，类似 Java 的 Function<T,R>）、List（列表类型）
from dataclasses import dataclass, field  # 导入 dataclass（自动生成 __init__ 等方法的类装饰器）和 field（字段配置函数）
from datetime import datetime  # 导入 datetime 类，用于处理日期和时间
import logging  # 导入 logging 模块，用于日志记录

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器，__name__ 是模块名称


class EventType:  # 定义事件类型常量类，类似 Java 的常量接口或 final String 常量
    """事件类型枚举"""  # 类的文档字符串
    RUN_STARTED = "run_started"  # 运行开始事件
    RUN_COMPLETED = "run_completed"  # 运行完成事件
    RUN_FAILED = "run_failed"  # 运行失败事件
    RUN_INTERRUPTED = "run_interrupted"  # 运行中断事件
    RUN_TIMEOUT = "run_timeout"  # 运行超时事件
    STEP_STARTED = "step_started"  # 步骤开始事件
    STEP_COMPLETED = "step_completed"  # 步骤完成事件
    STEP_FAILED = "step_failed"  # 步骤失败事件
    STEP_SKIPPED = "step_skipped"  # 步骤跳过事件
    TOOL_CALL_STARTED = "tool_call_started"  # 工具调用开始事件
    TOOL_CALL_COMPLETED = "tool_call_completed"  # 工具调用完成事件
    TOOL_CALL_FAILED = "tool_call_failed"  # 工具调用失败事件
    INTENT_RECOGNIZED = "intent_recognized"  # 意图识别完成事件
    QUESTION_CLASSIFIED = "question_classified"  # 问题分类完成事件
    CLARIFICATION_NEEDED = "clarification_needed"  # 需要澄清事件
    QUESTION_REWRITTEN = "question_rewritten"  # 问题改写完成事件
    RETRIEVAL_COMPLETED = "retrieval_completed"  # 检索完成事件
    SUFFICIENCY_EVALUATED = "sufficiency_evaluated"  # 充分性评估完成事件
    ANSWER_GENERATED = "answer_generated"  # 答案生成完成事件
    MEMORY_WRITTEN = "memory_written"  # 记忆写入完成事件
    STATE_UPDATED = "state_updated"  # 状态更新事件


@dataclass  # @dataclass 装饰器，自动生成 __init__、__repr__ 等方法
class Event:  # 定义事件基类，所有事件都继承此类
    """事件基类"""  # 类的文档字符串
    event_type: str  # 事件类型字符串
    run_id: str  # 关联的运行 ID
    timestamp: datetime = field(default_factory=datetime.now)  # 事件时间戳，field(default_factory=datetime.now) 表示默认使用当前时间。注意：default_factory 接受一个工厂函数，每次创建实例时调用
    data: Dict[str, Any] = field(default_factory=dict)  # 事件的附加数据，默认为空字典

    def to_dict(self) -> Dict[str, Any]:  # 将事件序列化为字典，方便转为 JSON
        return {  # 返回包含事件信息的字典
            "event_type": self.event_type,  # 事件类型
            "run_id": self.run_id,  # 运行 ID
            "timestamp": self.timestamp.isoformat(),  # .isoformat() 将 datetime 转为 ISO 8601 格式字符串
            "data": self.data  # 附加数据
        }


@dataclass  # @dataclass 装饰器
class RunStartedEvent(Event):  # 运行开始事件，继承自 Event 基类，类似 Java 的 class RunStartedEvent extends Event
    """运行开始事件"""  # 类的文档字符串
    def __init__(self, run_id: str, goal: str, input_data: str, **kwargs):  # 构造函数，**kwargs 接收额外的关键字参数（类似 Java 的可变参数），用于忽略父类不需要的参数
        super().__init__(  # super().__init__() 调用父类的构造函数，类似 Java 的 super()
            event_type=EventType.RUN_STARTED,  # 事件类型固定为 RUN_STARTED
            run_id=run_id,  # 运行 ID
            data={"goal": goal, "input": input_data}  # 附加数据包含目标和输入
        )


@dataclass  # @dataclass 装饰器
class RunCompletedEvent(Event):  # 运行完成事件
    """运行完成事件"""  # 类的文档字符串
    def __init__(self, run_id: str, output: Dict[str, Any], **kwargs):  # 构造函数
        super().__init__(  # 调用父类构造函数
            event_type=EventType.RUN_COMPLETED,  # 事件类型为 RUN_COMPLETED
            run_id=run_id,  # 运行 ID
            data={"output": output}  # 附加数据包含输出结果
        )


@dataclass  # @dataclass 装饰器
class RunFailedEvent(Event):  # 运行失败事件
    """运行失败事件"""  # 类的文档字符串
    def __init__(self, run_id: str, error: str, error_code: Optional[str] = None, **kwargs):  # 构造函数
        super().__init__(  # 调用父类构造函数
            event_type=EventType.RUN_FAILED,  # 事件类型为 RUN_FAILED
            run_id=run_id,  # 运行 ID
            data={"error": error, "error_code": error_code}  # 附加数据包含错误信息和错误码
        )


@dataclass  # @dataclass 装饰器
class StepEvent(Event):  # 步骤事件基类，继承自 Event，为步骤相关事件提供通用字段
    """步骤事件基类"""  # 类的文档字符串
    step_id: str = ""  # 步骤 ID，默认为空字符串
    step_name: str = ""  # 步骤名称，默认为空字符串
    step_type: str = ""  # 步骤类型，默认为空字符串

    def to_dict(self) -> Dict[str, Any]:  # 将步骤事件序列化为字典
        result = super().to_dict()  # 先调用父类的 to_dict 获取基础事件数据
        result["data"]["step_id"] = self.step_id  # 在 data 中添加步骤 ID
        result["data"]["step_name"] = self.step_name  # 在 data 中添加步骤名称
        result["data"]["step_type"] = self.step_type  # 在 data 中添加步骤类型
        return result  # 返回完整的字典


@dataclass  # @dataclass 装饰器
class StepStartedEvent(StepEvent):  # 步骤开始事件，继承自 StepEvent
    """步骤开始事件"""  # 类的文档字符串
    def __init__(self, run_id: str, step_id: str, step_name: str, step_type: str, **kwargs):  # 构造函数
        super().__init__(  # 调用父类构造函数
            event_type=EventType.STEP_STARTED,  # 事件类型为 STEP_STARTED
            run_id=run_id,  # 运行 ID
            step_id=step_id,  # 步骤 ID
            step_name=step_name,  # 步骤名称
            step_type=step_type  # 步骤类型
        )


@dataclass  # @dataclass 装饰器
class StepCompletedEvent(StepEvent):  # 步骤完成事件
    """步骤完成事件"""  # 类的文档字符串
    def __init__(self, run_id: str, step_id: str, step_name: str, step_type: str,  # 构造函数
                 output: Dict[str, Any], duration_ms: float, **kwargs):  # 额外参数：输出结果和耗时
        super().__init__(  # 调用父类构造函数
            event_type=EventType.STEP_COMPLETED,  # 事件类型为 STEP_COMPLETED
            run_id=run_id,  # 运行 ID
            step_id=step_id,  # 步骤 ID
            step_name=step_name,  # 步骤名称
            step_type=step_type,  # 步骤类型
            data={"output": output, "duration_ms": duration_ms}  # 附加数据包含输出和耗时
        )


@dataclass  # @dataclass 装饰器
class StepFailedEvent(StepEvent):  # 步骤失败事件
    """步骤失败事件"""  # 类的文档字符串
    def __init__(self, run_id: str, step_id: str, step_name: str, step_type: str,  # 构造函数
                 error: str, **kwargs):  # 额外参数：错误信息
        super().__init__(  # 调用父类构造函数
            event_type=EventType.STEP_FAILED,  # 事件类型为 STEP_FAILED
            run_id=run_id,  # 运行 ID
            step_id=step_id,  # 步骤 ID
            step_name=step_name,  # 步骤名称
            step_type=step_type,  # 步骤类型
            data={"error": error}  # 附加数据包含错误信息
        )


@dataclass  # @dataclass 装饰器
class ToolCallEvent(Event):  # 工具调用事件基类，继承自 Event
    """工具调用事件"""  # 类的文档字符串
    tool_call_id: str = ""  # 工具调用 ID，默认为空字符串
    tool_name: str = ""  # 工具名称，默认为空字符串

    def to_dict(self) -> Dict[str, Any]:  # 将工具调用事件序列化为字典
        result = super().to_dict()  # 调用父类的 to_dict 获取基础数据
        result["data"]["tool_call_id"] = self.tool_call_id  # 在 data 中添加工具调用 ID
        result["data"]["tool_name"] = self.tool_name  # 在 data 中添加工具名称
        return result  # 返回完整的字典


@dataclass  # @dataclass 装饰器
class ToolCallCompletedEvent(ToolCallEvent):  # 工具调用完成事件
    """工具调用完成事件"""  # 类的文档字符串
    def __init__(self, run_id: str, tool_call_id: str, tool_name: str,  # 构造函数
                 output: Dict[str, Any], duration_ms: float, **kwargs):  # 额外参数：输出和耗时
        super().__init__(  # 调用父类构造函数
            event_type=EventType.TOOL_CALL_COMPLETED,  # 事件类型为 TOOL_CALL_COMPLETED
            run_id=run_id,  # 运行 ID
            tool_call_id=tool_call_id,  # 工具调用 ID
            tool_name=tool_name,  # 工具名称
            data={"output": output, "duration_ms": duration_ms}  # 附加数据包含输出和耗时
        )


@dataclass  # @dataclass 装饰器
class ToolCallFailedEvent(ToolCallEvent):  # 工具调用失败事件
    """工具调用失败事件"""  # 类的文档字符串
    def __init__(self, run_id: str, tool_call_id: str, tool_name: str,  # 构造函数
                 error: str, **kwargs):  # 额外参数：错误信息
        super().__init__(  # 调用父类构造函数
            event_type=EventType.TOOL_CALL_FAILED,  # 事件类型为 TOOL_CALL_FAILED
            run_id=run_id,  # 运行 ID
            tool_call_id=tool_call_id,  # 工具调用 ID
            tool_name=tool_name,  # 工具名称
            data={"error": error}  # 附加数据包含错误信息
        )


@dataclass  # @dataclass 装饰器
class AnswerGeneratedEvent(Event):  # 答案生成完成事件
    """答案生成事件"""  # 类的文档字符串
    def __init__(self, run_id: str, answer: str, sources: List[Dict[str, Any]], **kwargs):  # 构造函数
        super().__init__(  # 调用父类构造函数
            event_type=EventType.ANSWER_GENERATED,  # 事件类型为 ANSWER_GENERATED
            run_id=run_id,  # 运行 ID
            data={"answer": answer, "sources": sources}  # 附加数据包含答案和引用来源
        )


class EventBus:  # 事件总线类，实现发布-订阅模式（Publish-Subscribe Pattern），类似 Java 的 EventBus（Guava）
    """事件总线 - 负责事件的发布和订阅"""  # 类的文档字符串

    _instance = None  # 类变量，保存单例实例，类似 Java 的 private static EventBus _instance

    def __new__(cls):  # __new__ 是类级别的方法，控制实例的创建过程，用于实现单例模式。类似 Java 中重写 new（但 Java 不支持）
        if cls._instance is None:  # 第一次调用时，_instance 是 None
            cls._instance = super().__new__(cls)  # super().__new__(cls) 调用父类 object 的 __new__ 创建实例
            cls._instance._handlers = {}  # 初始化事件处理器字典，键为事件类型，值为处理器函数列表
            cls._instance._global_handlers = []  # 初始化全局处理器列表，订阅所有事件
        return cls._instance  # 返回单例实例

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):  # 订阅指定类型的事件
        """订阅事件"""  # 方法文档字符串
        if event_type not in self._handlers:  # 如果该事件类型还没有处理器列表
            self._handlers[event_type] = []  # 创建空列表
        self._handlers[event_type].append(handler)  # 将处理器函数添加到列表中
        logger.debug(f"Subscribed handler for event type: {event_type}")  # 记录调试日志

    def subscribe_global(self, handler: Callable[[Event], None]):  # 订阅所有事件，类似 Java 的 @Subscribe 注解
        """订阅所有事件"""  # 方法文档字符串
        self._global_handlers.append(handler)  # 将处理器添加到全局处理器列表
        logger.debug("Subscribed global event handler")  # 记录调试日志

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]):  # 取消订阅指定类型的事件
        """取消订阅"""  # 方法文档字符串
        if event_type in self._handlers:  # 如果该事件类型有处理器列表
            self._handlers[event_type].remove(handler)  # 从列表中移除处理器函数

    def publish(self, event: Event):  # 发布事件，通知所有订阅者
        """发布事件"""  # 方法文档字符串
        logger.debug(f"Publishing event: {event.event_type} for run: {event.run_id}")  # 记录调试日志

        if event.event_type in self._handlers:  # 如果有订阅该事件类型的处理器
            for handler in self._handlers[event.event_type]:  # 遍历所有处理器
                try:  # try-except 异常处理，类似 Java 的 try-catch
                    handler(event)  # 调用处理器函数，传入事件对象
                except Exception as e:  # 捕获处理器中的异常，防止一个处理器出错影响其他处理器
                    logger.error(f"Error handling event {event.event_type}: {e}")  # 记录错误日志

        for handler in self._global_handlers:  # 遍历所有全局处理器
            try:  # try-except 异常处理
                handler(event)  # 调用全局处理器
            except Exception as e:  # 捕获异常
                logger.error(f"Error in global event handler: {e}")  # 记录错误日志

    def clear(self):  # 清空所有订阅
        """清空所有订阅"""  # 方法文档字符串
        self._handlers.clear()  # 清空事件处理器字典
        self._global_handlers.clear()  # 清空全局处理器列表


event_bus = EventBus()  # 创建 EventBus 单例实例，模块级别的全局对象
