from agent.state import AgentState, AgentStatus, StepStatus, StepType, AgentStep, TerminationCondition  # 从 agent.state 模块导入 Agent 状态相关的类：AgentState（状态对象）、AgentStatus（运行状态枚举）、StepStatus（步骤状态枚举）、StepType（步骤类型枚举）、AgentStep（步骤对象）、TerminationCondition（终止条件判断器）
from agent.planner import Planner, QuestionType  # 从 agent.planner 模块导入 Planner（任务规划器）和 QuestionType（问题类型常量类）
from agent.executor import Executor  # 从 agent.executor 模块导入 Executor（步骤执行器），负责执行各个步骤
from agent.orchestrator import Orchestrator  # 从 agent.orchestrator 模块导入 Orchestrator（编排器），负责协调整个执行流程
from agent.events import EventBus, Event, EventType  # 从 agent.events 模块导入 EventBus（事件总线）、Event（事件基类）、EventType（事件类型常量类）
from agent.policies import policies  # 从 agent.policies 模块导入 policies 单例（Agent 策略管理器实例）
from intent.classifier import IntentType  # 从 intent.classifier 模块导入 IntentType（意图类型枚举）

# MemoryAgent 使用延迟导入，避免循环依赖
def get_memory_agent():  # 定义获取 MemoryAgent 类的工厂函数，使用延迟导入避免 agent 模块内部的循环依赖问题
    from agent.memory_agent import MemoryAgent  # 在函数内部导入 MemoryAgent，只有在调用时才会加载模块
    return MemoryAgent  # 返回 MemoryAgent 类（注意返回的是类本身，不是实例，类似 Java 的 Supplier<Class>）

__all__ = [  # __all__ 列表定义了 from agent import * 时会导出的公开符号，类似 Java 模块的 public 导出声明
    "AgentState",  # Agent 状态对象
    "AgentStatus",  # Agent 运行状态枚举
    "StepStatus",  # 步骤状态枚举
    "StepType",  # 步骤类型枚举
    "AgentStep",  # Agent 步骤对象
    "TerminationCondition",  # 终止条件判断器
    "Planner",  # 任务规划器
    "IntentType",  # 意图类型枚举
    "QuestionType",  # 问题类型常量类
    "Executor",  # 步骤执行器
    "Orchestrator",  # 编排器
    "EventBus",  # 事件总线
    "Event",  # 事件基类
    "EventType",  # 事件类型常量类
    "policies",  # Agent 策略管理器实例
    "get_memory_agent"  # MemoryAgent 延迟加载工厂函数
]
