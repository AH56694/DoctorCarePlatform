from typing import Dict, Any, Optional  # 导入类型注解：Dict=字典，Any=任意类型，Optional=可选类型
import time  # 导入时间模块，用于计时和生成 ID
import logging  # 导入日志模块
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError  # 导入线程池和超时异常（ThreadPoolExecutor 类似 Java 的 ExecutorService）
from tools.base import Tool  # 导入工具抽象基类
from tools.execution import tool_execution_tracker  # 导入全局工具执行跟踪器

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器（日志会显示 tools.registry，方便定位来源）


class ToolRegistry:  # 工具注册器类（模块级单例，通过文件底部 tool_registry = ToolRegistry() 实例化）
    """工具注册器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_tools"):
            self._tools = {}  # 工具字典，{工具名: Tool实例}

    def register_tool(self, tool: Tool):  # 注册工具到注册器
        """注册工具"""
        self._tools[tool.name] = tool  # 以工具名称为 key 存入字典（类似 Java 的 map.put(tool.getName(), tool)）
        logger.info(f"Tool registered: {tool.name}")  # 记录注册成功日志

    def get_tool(self, name: str) -> Optional[Tool]:  # 根据名称获取工具，返回 Optional 表示可能为 None
        """获取工具"""
        return self._tools.get(name)  # 字典的 get 方法，key 不存在时返回 None（类似 Java 的 map.getOrDefault(name, null)）

    def get_all_tools(self) -> Dict[str, Tool]:  # 获取所有已注册的工具
        """获取所有工具"""
        return self._tools  # 返回工具字典的引用

    def has_tool(self, name: str) -> bool:  # 检查工具是否存在
        """检查工具是否存在"""
        return name in self._tools  # in 运算符检查字典中是否存在该 key（类似 Java 的 map.containsKey(name)）

    def invoke_tool(self, tool_name: str, parameters: Dict[str, Any], run_id: Optional[str] = None) -> Dict[str, Any]:  # 调用工具的核心方法
        """调用工具"""
        tool = self.get_tool(tool_name)  # 根据名称获取工具实例
        if not tool:  # 如果工具不存在
            raise ValueError(f"Tool not found: {tool_name}")  # 抛出 ValueError（类似 Java 的 throw new IllegalArgumentException()）

        # 验证输入参数
        if not tool.validate_input(parameters):  # 调用工具的输入验证方法
            raise ValueError(f"Invalid input parameters for tool: {tool_name}")  # 参数验证失败则抛异常

        # 生成 run_id 如果没有提供
        if run_id is None:  # 如果没有传入 run_id
            run_id = str(time.time())  # 使用当前时间戳作为 run_id

        # 开始工具调用跟踪
        tool_call_id = tool_execution_tracker.start_tool_call(run_id, tool_name, parameters)  # 记录调用开始

        # 执行工具（带超时和重试）
        retries = 0  # 当前重试次数
        max_retries = tool.metadata.max_retries  # 最大重试次数
        timeout_ms = tool.metadata.timeout_ms  # 超时时间（毫秒）

        timeout_sec = timeout_ms / 1000.0  # 将毫秒转换为秒

        while retries <= max_retries:  # 重试循环（类似 Java 的 while 循环）
            start_time = time.time()  # 记录开始时间（time.time() 返回当前时间戳，单位秒）
            try:  # 尝试执行工具
                # 使用线程池执行工具，强制超时控制
                with ThreadPoolExecutor(max_workers=1) as executor:  # 创建单线程的线程池（with 类似 Java 的 try-with-resources，自动关闭资源）
                    future = executor.submit(tool.execute, parameters)  # 提交任务到线程池（类似 Java 的 executor.submit(() -> tool.execute(parameters))）
                    try:
                        result = future.result(timeout=timeout_sec)  # 等待结果，设置超时（类似 Java 的 future.get(timeout, TimeUnit.SECONDS)）
                    except FutureTimeoutError:  # 捕获超时异常
                        future.cancel()  # 取消正在执行的任务
                        raise TimeoutError(f"Tool {tool_name} timed out after {timeout_ms}ms")  # 抛出超时错误

                execution_time = (time.time() - start_time) * 1000  # 计算执行时间（秒转毫秒）
                logger.info(f"Tool {tool_name} executed in {execution_time:.2f}ms")  # 记录执行耗时日志

                # 完成工具调用跟踪
                tool_execution_tracker.complete_tool_call(tool_call_id, result, execution_time)  # 记录调用完成

                return result  # 返回执行结果

            except Exception as e:  # 捕获执行异常
                execution_time = (time.time() - start_time) * 1000  # 计算已用时间
                retries += 1  # 重试次数加1
                if retries > max_retries:  # 超过最大重试次数
                    logger.error(f"Tool {tool_name} failed after {max_retries} retries: {e}")  # 记录错误日志
                    tool_execution_tracker.fail_tool_call(tool_call_id, str(e), execution_time)  # 记录调用失败
                    raise  # 重新抛出异常（类似 Java 的 throw，不带参数表示重新抛出当前异常）
                logger.warning(f"Tool {tool_name} failed (attempt {retries}/{max_retries}): {e}")  # 记录重试警告
                time.sleep(0.5)  # 等待 0.5 秒后重试（类似 Java 的 Thread.sleep(500)）

    def get_tool_info(self, tool_name: str) -> Dict[str, Any]:  # 获取工具的详细信息
        """获取工具信息"""
        tool = self.get_tool(tool_name)  # 根据名称获取工具
        if not tool:  # 工具不存在
            return None  # 返回 None

        return {  # 返回工具信息的字典（类似 Java 的 Map 结构）
            "name": tool.name,  # 工具名称
            "description": tool.description,  # 工具描述
            "input_schema": {  # 输入 Schema 信息
                "type": tool.input_schema.type,  # Schema 类型
                "properties": {k: {  # 字典推导式（类似 Java 的 stream().collect()），遍历所有属性
                    "type": v.type,  # 属性类型
                    "description": v.description,  # 属性描述
                    "required": v.required  # 是否必填
                } for k, v in tool.input_schema.properties.items()}  # k=key, v=value 遍历字典
            },
            "output_schema": {  # 输出 Schema 信息
                "type": tool.output_schema.type,  # Schema 类型
                "properties": {k: {  # 遍历输出属性
                    "type": v.type,  # 属性类型
                    "description": v.description,  # 属性描述
                    "required": v.required  # 是否必填
                } for k, v in tool.output_schema.properties.items()}  # 字典推导式
            },
            "metadata": {  # 元数据信息
                "timeout_ms": tool.metadata.timeout_ms,  # 超时时间
                "max_retries": tool.metadata.max_retries,  # 最大重试次数
                "permission": tool.metadata.permission  # 权限级别
            }
        }

    def get_tool_calls_by_run_id(self, run_id: str) -> list:  # 按 run_id 查询工具调用轨迹
        """按 runId 查询工具调用轨迹"""
        tool_calls = tool_execution_tracker.get_tool_calls_by_run_id(run_id)  # 从跟踪器获取调用记录
        return [{  # 列表推导式（类似 Java 的 stream().map().collect()），将记录转为字典列表
            "tool_call_id": call.tool_call_id,  # 调用 ID
            "tool_name": call.tool_name,  # 工具名称
            "input_params": call.input_params,  # 输入参数
            "output": call.output,  # 输出结果
            "status": call.status,  # 调用状态
            "duration_ms": call.duration_ms,  # 执行耗时
            "error_message": call.error_message,  # 错误信息
            "timestamp": call.timestamp  # 时间戳
        } for call in tool_calls]  # 遍历所有调用记录


# 全局工具注册器实例
tool_registry = ToolRegistry()  # 创建全局单例实例（类似 Java 的 public static final ToolRegistry toolRegistry = new ToolRegistry()）
