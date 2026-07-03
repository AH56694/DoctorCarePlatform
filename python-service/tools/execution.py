from typing import Dict, Any, List, Optional  # 导入类型注解：Dict=字典，Any=任意类型，List=列表，Optional=可选类型
from dataclasses import dataclass  # 导入数据类装饰器（@dataclass 类似 Java 的 Lombok @Data）
import time  # 导入时间模块
import uuid  # 导入 UUID 模块，用于生成唯一标识符（类似 Java 的 java.util.UUID）
import logging  # 导入日志模块，用于记录程序运行时的事件和错误信息

logger = logging.getLogger(__name__)

@dataclass  # 数据类装饰器，自动生成 __init__、__repr__、__eq__ 等方法（类似 Java 的 Lombok @Data）
class ToolCallRecord:  # 工具调用记录数据类，用于记录每次工具调用的信息
    """工具调用记录"""
    tool_call_id: str  # 工具调用的唯一 ID（类似 Java 的 String 字段）
    run_id: str  # 关联的运行 ID，标识属于哪次请求
    tool_name: str  # 工具名称
    input_params: Dict[str, Any]  # 输入参数字典（类似 Java 的 Map<String, Object>）
    output: Optional[Dict[str, Any]]  # 输出结果，Optional 表示可能为 None（类似 Java 的 @Nullable Map<String, Object>）
    status: str  # 调用状态：success, failed, pending
    duration_ms: float  # 执行耗时（毫秒）
    error_message: Optional[str]  # 错误信息，调用成功时为 None
    timestamp: str  # 调用时间戳字符串


class ToolExecutionTracker:  # 工具执行跟踪器类，记录和追踪所有工具调用
    """工具执行跟踪器"""

    def __init__(self):  # 构造函数
        self._tool_calls = {}  # 存储所有工具调用记录的字典，key 是 tool_call_id（下划线前缀表示内部属性，类似 Java 的 private）
        self._run_tool_calls = {}  # 按 run_id 分组的工具调用 ID 列表，key 是 run_id，value 是 tool_call_id 列表

    def start_tool_call(self, run_id: str, tool_name: str, input_params: Dict[str, Any]) -> str:  # 开始跟踪一次工具调用，返回调用 ID
        """开始工具调用"""
        tool_call_id = str(uuid.uuid4())  # 生成唯一的工具调用 ID（类似 Java 的 UUID.randomUUID().toString()）
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')  # 格式化当前时间为字符串（类似 Java 的 SimpleDateFormat）

        record = ToolCallRecord(  # 创建工具调用记录实例（@dataclass 自动生成了构造函数）
            tool_call_id=tool_call_id,  # 调用 ID
            run_id=run_id,  # 运行 ID
            tool_name=tool_name,  # 工具名称
            input_params=input_params,  # 输入参数
            output=None,  # 输出暂未生成
            status="pending",  # 初始状态为 pending
            duration_ms=0,  # 耗时初始为0
            error_message=None,  # 无错误信息
            timestamp=timestamp  # 时间戳
        )

        self._tool_calls[tool_call_id] = record  # 存入调用记录字典

        # 按 run_id 分组
        if run_id not in self._run_tool_calls:  # 如果该 run_id 还没有分组
            self._run_tool_calls[run_id] = []  # 创建新的空列表
        self._run_tool_calls[run_id].append(tool_call_id)  # 将调用 ID 添加到对应 run_id 的列表中

        logger.info(f"Tool call started: {tool_name}, run_id: {run_id}, tool_call_id: {tool_call_id}")  # 记录开始日志

        return tool_call_id  # 返回工具调用 ID

    def complete_tool_call(self, tool_call_id: str, output: Dict[str, Any], duration_ms: float):  # 标记工具调用完成
        """完成工具调用"""
        if tool_call_id in self._tool_calls:  # 如果该调用记录存在
            record = self._tool_calls[tool_call_id]  # 获取调用记录
            record.output = output  # 设置输出结果
            record.status = "success"  # 更新状态为成功
            record.duration_ms = duration_ms  # 设置执行耗时

            logger.info(f"Tool call completed: {record.tool_name}, duration: {duration_ms:.2f}ms")  # 记录完成日志（:.2f 保留2位小数）

    def fail_tool_call(self, tool_call_id: str, error_message: str, duration_ms: float):  # 标记工具调用失败
        """工具调用失败"""
        if tool_call_id in self._tool_calls:  # 如果该调用记录存在
            record = self._tool_calls[tool_call_id]  # 获取调用记录
            record.status = "failed"  # 更新状态为失败
            record.error_message = error_message  # 设置错误信息
            record.duration_ms = duration_ms  # 设置执行耗时

            logger.error(f"Tool call failed: {record.tool_name}, error: {error_message}")  # 记录错误日志

    def get_tool_call(self, tool_call_id: str) -> Optional[ToolCallRecord]:  # 根据调用 ID 获取记录
        """获取工具调用记录"""
        return self._tool_calls.get(tool_call_id)  # 返回记录，不存在时返回 None

    def get_tool_calls_by_run_id(self, run_id: str) -> List[ToolCallRecord]:  # 根据运行 ID 获取所有调用记录
        """按 run_id 获取工具调用记录"""
        tool_call_ids = self._run_tool_calls.get(run_id, [])  # 获取该 run_id 下的所有调用 ID 列表
        return [self._tool_calls[call_id] for call_id in tool_call_ids if call_id in self._tool_calls]  # 列表推导式，过滤已删除的记录

    def get_all_tool_calls(self) -> List[ToolCallRecord]:  # 获取所有工具调用记录
        """获取所有工具调用记录"""
        return list(self._tool_calls.values())  # 返回字典所有值的列表（values() 类似 Java 的 map.values()）

    def clear_run_calls(self, run_id: str):  # 清理指定 run_id 的所有调用记录
        """清理指定 run_id 的工具调用记录"""
        if run_id in self._run_tool_calls:  # 如果该 run_id 存在
            tool_call_ids = self._run_tool_calls[run_id]  # 获取该 run_id 下的所有调用 ID
            for call_id in tool_call_ids:  # 遍历所有调用 ID
                if call_id in self._tool_calls:  # 如果调用记录存在
                    del self._tool_calls[call_id]  # 删除调用记录（del 类似 Java 的 map.remove(key)）
            del self._run_tool_calls[run_id]  # 删除 run_id 分组
            logger.info(f"Cleared tool calls for run_id: {run_id}")  # 记录清理日志


# 全局工具执行跟踪器
tool_execution_tracker = ToolExecutionTracker()  # 创建全局单例实例（类似 Java 的 public static final 变量）
