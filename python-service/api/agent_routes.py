from fastapi import APIRouter, HTTPException  # 导入 FastAPI 路由器和 HTTP 异常类
from fastapi.responses import StreamingResponse  # 导入流式响应类，用于 SSE（Server-Sent Events）
from pydantic import BaseModel  # 导入 Pydantic 基础模型类，用于请求/响应数据校验（类似 Java 的 DTO + @Valid）
from agent.orchestrator import Orchestrator  # 导入 Agent 编排器，负责协调规划和执行
from agent.state import AgentState, AgentStatus  # 导入 Agent 状态模型和状态枚举
from agent.events import event_bus, Event, EventType  # 导入事件总线和事件类型，实现发布-订阅模式
from tools.execution import tool_execution_tracker  # 导入工具执行跟踪器，记录工具调用链路
from workflows import RouterAgent  # 导入路由 Agent，保留用于管理员请求路由和统计
from typing import Optional, List, Dict, Any  # 导入类型注解
from collections import defaultdict  # 导入带默认值的字典
import time  # 导入时间模块
import logging  # 导入日志模块
import json  # 导入 JSON 处理模块
import uuid  # 导入 UUID 模块

logger = logging.getLogger(__name__)  # 创建当前模块的 Logger 实例

router = APIRouter()  # 创建 API 路由器实例

orchestrator = Orchestrator()  # 创建 Orchestrator 实例（Agent 编排器，类似 LangGraph 的 Graph Runner）
router_agent = RouterAgent()  # 保留 RouterAgent 实例，用于管理员请求路由和 get_task_stats()


# ==================== 请求/响应模型 ====================

class AgentRunRequest(BaseModel):  # Agent 运行请求模型（类似 Java DTO）
    """Agent运行请求"""
    input: str  # 用户输入文本（必填）
    conversation_id: Optional[str] = None  # 会话 ID，可选
    user_id: Optional[str] = None  # 用户 ID，可选
    context: Optional[str] = ""  # 上下文信息，可选
    goal: Optional[str] = None  # 目标描述，可选
    run_id: Optional[str] = None  # 运行 ID，可选（用于追踪一次 Agent 执行）
    trace_id: Optional[str] = None  # 链路追踪 ID，可选
    stream: bool = False  # 是否使用流式响应，默认 False
    is_admin: bool = False  # 是否管理员，默认 False


class AgentRunResponse(BaseModel):  # Agent 运行响应模型
    """Agent运行响应"""
    run_id: str  # 运行 ID
    trace_id: str  # 链路追踪 ID
    status: str  # 执行状态
    answer: str  # Agent 生成的回答
    sources: List[Dict[str, Any]]  # 文档引用来源列表
    steps: List[Dict[str, Any]]  # 执行步骤列表
    tool_calls: List[Dict[str, Any]]  # 工具调用记录列表
    intermediate_conclusions: List[Dict[str, Any]]  # 中间结论列表


class StepEventModel(BaseModel):  # 步骤事件模型
    """步骤事件"""
    run_id: str
    step_id: str
    step_name: str
    step_type: str
    status: str


class ToolCallEventModel(BaseModel):  # 工具调用事件模型
    """工具调用事件"""
    run_id: str
    tool_call_id: str
    tool_name: str
    status: str
    duration_ms: Optional[float] = None


# ==================== 状态存储与统计 ====================

stored_states: Dict[str, AgentState] = {}  # 运行状态字典，key=run_id，value=AgentState（Orchestrator 和事件处理器都会写入）
MAX_STORED_STATES = 1000  # 最大存储状态数，超过时清理最旧的（防止内存泄漏）

task_stats = defaultdict(lambda: {  # 任务统计字典，按 task_type 分类（defaultdict 自动创建默认值）
    "total": 0,
    "success": 0,
    "failed": 0,
    "total_duration_ms": 0
})


# ==================== 事件处理器 ====================
# 通过订阅 Orchestrator 发布的事件，实时同步 stored_states

def _sync_state_from_orchestrator(run_id: str):  # 从 Orchestrator 同步最新状态到 stored_states
    """从 Orchestrator 同步最新状态到 stored_states（内部辅助方法）"""
    state = orchestrator.get_state(run_id)  # 从 Orchestrator 内部获取 AgentState
    if state:  # 如果状态存在
        stored_states[run_id] = state  # 同步到外部 stored_states 字典


def on_run_started(event: Event):  # 运行开始事件处理器
    """处理运行开始事件：同步状态并记录日志"""
    _sync_state_from_orchestrator(event.run_id)  # 同步状态
    logger.info(f"[Event] Run {event.run_id} started, goal: {event.data.get('goal', 'N/A')}")  # 记录日志


def on_step_completed(event: Event):  # 步骤完成事件处理器
    """处理步骤完成事件：同步状态"""
    _sync_state_from_orchestrator(event.run_id)  # 每个步骤完成后同步状态（客户端可实时查询进度）
    step_name = event.data.get("step_name", "unknown")  # 从事件数据中获取步骤名称
    logger.info(f"[Event] Step '{step_name}' completed for run {event.run_id}")  # 记录日志


def on_step_failed(event: Event):  # 步骤失败事件处理器
    """处理步骤失败事件：同步状态并记录错误"""
    _sync_state_from_orchestrator(event.run_id)  # 同步状态（包含失败信息）
    step_name = event.data.get("step_name", "unknown")  # 获取步骤名称
    error = event.data.get("error", "Unknown error")  # 获取错误信息
    logger.error(f"[Event] Step '{step_name}' failed for run {event.run_id}: {error}")  # 记录错误日志


def on_run_completed(event: Event):  # 运行完成事件处理器
    """处理运行完成事件：同步最终状态"""
    _sync_state_from_orchestrator(event.run_id)  # 同步最终状态到 stored_states
    logger.info(f"[Event] Run {event.run_id} completed")  # 记录完成日志


def on_run_failed(event: Event):  # 运行失败事件处理器
    """处理运行失败事件：同步失败状态"""
    _sync_state_from_orchestrator(event.run_id)  # 同步失败状态
    error = event.data.get("error", "Unknown error")  # 获取错误信息
    logger.error(f"[Event] Run {event.run_id} failed: {error}")  # 记录错误日志


# 订阅事件（类似 Java 的 eventBus.register() 或 @Subscribe 注解）
event_bus.subscribe(EventType.RUN_STARTED, on_run_started)  # 订阅运行开始事件
event_bus.subscribe(EventType.STEP_COMPLETED, on_step_completed)  # 订阅步骤完成事件
event_bus.subscribe(EventType.STEP_FAILED, on_step_failed)  # 订阅步骤失败事件
event_bus.subscribe(EventType.RUN_COMPLETED, on_run_completed)  # 订阅运行完成事件
event_bus.subscribe(EventType.RUN_FAILED, on_run_failed)  # 订阅运行失败事件


# ==================== 辅助函数 ====================

def _derive_task_type(state: Optional[AgentState]) -> str:  # 从 AgentState 推导任务类型
    """从 AgentState 的 planned_steps 推导任务类型"""
    if not state or not state.planned_steps:  # 如果状态为空或没有计划步骤
        return "unknown"  # 返回未知类型

    planned = state.planned_steps  # 获取计划执行的步骤名称列表
    if "admin_operation" in planned:  # 管理员操作
        return "admin"
    if "knowledge_search" in planned:  # 知识检索（说明是知识问答）
        return "knowledge_qa"
    if "identity_answer" in planned:  # 身份查询
        return "identity"
    # 只有 answer_generation 和 memory 相关步骤的，归为闲聊
    return "chitchat"


def _extract_steps(state: Optional[AgentState]) -> List[Dict[str, Any]]:  # 提取步骤摘要信息
    """从 AgentState 提取步骤信息列表"""
    if not state:  # 如果状态为空
        return []  # 返回空列表
    return [  # 列表推导式（类似 Java Stream 的 map + collect）
        {
            "step_id": s.step_id,  # 步骤 ID
            "step_name": s.step_name,  # 步骤名称
            "step_type": s.step_type.value,  # 步骤类型（枚举值转字符串）
            "status": s.status.value,  # 步骤状态（枚举值转字符串）
            "duration_ms": s.duration_ms,  # 步骤耗时（毫秒）
            "error_message": s.error_message  # 错误信息（可能为 None）
        }
        for s in state.steps  # 遍历所有步骤
    ]


def _extract_tool_calls(run_id: str, state: Optional[AgentState]) -> List[Dict[str, Any]]:  # 提取工具调用记录
    """提取工具调用记录（优先从 AgentState，fallback 到 tool_execution_tracker）"""
    # 第一优先级：从 AgentState.tool_calls 获取（Orchestrator 路径产生的）
    if state and state.tool_calls:  # 如果状态中有工具调用记录
        return [  # 列表推导式
            {
                "tool_call_id": tc.tool_call_id,  # 调用 ID
                "tool_name": tc.tool_name,  # 工具名称
                "input_params": tc.input_params,  # 输入参数
                "output": tc.output,  # 输出结果
                "status": tc.status,  # 调用状态
                "duration_ms": tc.duration_ms,  # 耗时
                "error_message": tc.error_message  # 错误信息
            }
            for tc in state.tool_calls  # 遍历所有工具调用
        ]

    # 第二优先级：从 tool_execution_tracker 获取（通过 tool_registry.invoke_tool() 产生的）
    tracker_calls = tool_execution_tracker.get_tool_calls_by_run_id(run_id)  # 按运行 ID 查询
    return [  # 列表推导式
        {
            "tool_call_id": call.tool_call_id,  # 调用 ID
            "tool_name": call.tool_name,  # 工具名称
            "input_params": call.input_params,  # 输入参数
            "output": call.output,  # 输出结果
            "status": call.status,  # 调用状态
            "duration_ms": call.duration_ms,  # 耗时
            "error_message": call.error_message,  # 错误信息
            "timestamp": call.timestamp  # 调用时间戳
        }
        for call in tracker_calls  # 遍历所有调用记录
    ]


def _extract_conclusions(state: Optional[AgentState]) -> List[Dict[str, Any]]:  # 提取中间结论
    """从 AgentState 提取中间结论列表"""
    if not state:  # 如果状态为空
        return []  # 返回空列表
    return [  # 列表推导式
        {
            "step_id": c.step_id,  # 关联步骤 ID
            "conclusion_type": c.conclusion_type,  # 结论类型（intent/retrieval/sufficiency 等）
            "content": c.content,  # 结论内容
            "confidence": c.confidence,  # 置信度
            "sources": c.sources  # 引用来源
        }
        for c in state.intermediate_conclusions  # 遍历所有中间结论
    ]


def _cleanup_old_states():  # 清理过多的状态记录，防止内存泄漏
    """清理过多的状态记录（超过 MAX_STORED_STATES 时，删除最旧的 20%）"""
    if len(stored_states) <= MAX_STORED_STATES:  # 未超过上限
        return  # 无需清理

    # 按开始时间排序，找到最旧的记录
    sorted_keys = sorted(  # sorted() 排序函数，类似 Java 的 Stream.sorted()
        stored_states.keys(),  # 所有 run_id
        key=lambda k: stored_states[k].start_time or 0  # 排序键为开始时间，lambda 是匿名函数
    )
    # 保留最新的 80%
    keep_count = int(MAX_STORED_STATES * 0.8)  # 计算保留数量
    remove_count = len(sorted_keys) - keep_count  # 计算需要删除的数量
    for key in sorted_keys[:remove_count]:  # 遍历最旧的记录
        del stored_states[key]  # 从 stored_states 中删除
        orchestrator.clear_state(key)  # 从 Orchestrator 内部也清理
    logger.info(f"[Agent API] Cleaned up {remove_count} old states")  # 记录清理日志


# ==================== API 接口 ====================

@router.post("/agent/run")  # POST /agent/run - 同步执行 Agent
async def run_agent(request: AgentRunRequest):
    """
    执行 Agent（同步模式）

    普通请求通过 Orchestrator 编排执行，自动记录状态和步骤；
    管理员请求通过 RouterAgent 路由执行（Orchestrator 的 admin 路径尚不完整）。

    Returns:
        Agent 执行结果，包含 answer、steps、tool_calls 等完整信息
    """
    run_id = request.run_id or str(uuid.uuid4())  # 获取或生成运行 ID
    trace_id = request.trace_id or str(uuid.uuid4())  # 获取或生成追踪 ID
    start_time = time.time()  # 记录请求开始时间

    try:
        logger.info(f"[Agent API] Received run request: {request.input[:50]}..., "
                     f"is_admin={request.is_admin}, run_id={run_id}")

        if request.is_admin:
            # === 管理员请求：走 RouterAgent（Orchestrator 的 admin 路径尚不完整） ===
            result = router_agent.route(  # 调用路由 Agent
                input_text=request.input,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                context=request.context or "",
                is_admin=True,
                goal=request.goal,
                run_id=run_id,
                trace_id=trace_id
            )
            task_type = result.get("task_type", "admin")  # 获取任务类型

            # 为 RouterAgent 路径手动构建 AgentState（保证 GET 接口也能查询）
            state = AgentState(  # 创建 AgentState 实例
                run_id=run_id,  # 运行 ID
                trace_id=trace_id,  # 追踪 ID
                conversation_id=request.conversation_id,  # 会话 ID
                user_id=request.user_id,  # 用户 ID
                goal=request.goal or f"管理员操作: {request.input[:50]}...",  # 目标
                original_input=request.input,  # 原始输入
                context=request.context or "",  # 上下文
                status=AgentStatus.COMPLETED,  # 直接标记为完成
                final_output=result  # 最终输出
            )
            state.start_time = start_time  # 记录开始时间
            state.end_time = time.time()  # 记录结束时间
            stored_states[run_id] = state  # 存入状态字典
        else:
            # === 普通请求：走 Orchestrator 编排执行 ===
            result = orchestrator.run(  # 调用 Orchestrator 同步执行
                input_text=request.input,
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                context=request.context or "",
                goal=request.goal,
                run_id=run_id,
                trace_id=trace_id
            )

            # 从 Orchestrator 获取完整状态（包含所有步骤、中间结论、工具调用）
            state = orchestrator.get_state(run_id)  # 获取 AgentState
            if state:  # 如果状态存在
                stored_states[run_id] = state  # 同步到外部 stored_states

            task_type = _derive_task_type(state)  # 从状态推导任务类型

        # 更新任务统计
        task_stats[task_type]["total"] += 1  # 总数 +1
        task_stats[task_type]["success"] += 1  # 成功数 +1
        duration_ms = (time.time() - start_time) * 1000  # 计算耗时（毫秒）
        task_stats[task_type]["total_duration_ms"] += duration_ms  # 累加总耗时

        # 构建响应
        response = {  # 构建完整响应字典
            "run_id": run_id,  # 运行 ID
            "trace_id": trace_id,  # 追踪 ID
            "status": "completed",  # 执行状态
            "answer": result.get("answer", ""),  # 回答内容
            "sources": result.get("sources", []),  # 文档来源列表
            "task_type": task_type,  # 任务类型
            "steps": _extract_steps(state),  # 执行步骤详情
            "tool_calls": _extract_tool_calls(run_id, state),  # 工具调用记录
            "intermediate_conclusions": _extract_conclusions(state)  # 中间结论
        }

        _cleanup_old_states()  # 清理旧状态，防止内存泄漏

        process_time = time.time() - start_time  # 计算总处理耗时
        logger.info(json.dumps({  # 记录结构化日志
            "method": "POST",
            "path": "/api/agent/run",
            "status_code": 200,
            "process_time": round(process_time, 3),
            "run_id": run_id,
            "task_type": task_type
        }))

        return response  # 返回执行结果

    except Exception as e:  # 捕获所有异常
        process_time = time.time() - start_time  # 计算处理耗时
        task_type = "unknown"  # 异常时任务类型设为 "unknown"
        task_stats[task_type]["total"] += 1  # 总数 +1
        task_stats[task_type]["failed"] += 1  # 失败数 +1

        logger.error(f"[Agent API] Error running agent: {str(e)}")  # 记录错误日志
        logger.info(json.dumps({  # 记录请求日志
            "method": "POST",
            "path": "/api/agent/run",
            "status_code": 500,
            "process_time": round(process_time, 3)
        }))
        raise HTTPException(status_code=500, detail=f"Agent执行失败: {str(e)}")  # 返回 500 错误


@router.post("/agent/run/stream")  # POST /agent/run/stream - 流式执行 Agent（SSE）
async def run_agent_stream(request: AgentRunRequest):
    """
    流式执行 Agent（SSE 模式）

    通过 Orchestrator 流式执行，实时推送步骤进度和 token 事件。
    客户端通过 EventSource 或 fetch + ReadableStream 接收 SSE 事件。
    """
    run_id = request.run_id or str(uuid.uuid4())  # 获取或生成运行 ID
    trace_id = request.trace_id or str(uuid.uuid4())  # 获取或生成追踪 ID

    async def event_generator():  # 异步生成器函数，逐步产出 SSE 事件
        start_time = time.time()  # 记录开始时间
        task_type = "unknown"  # 初始化任务类型

        try:
            logger.info(f"[Agent API] Stream request: {request.input[:50]}..., "
                         f"is_admin={request.is_admin}, run_id={run_id}")

            if request.is_admin:
                # === 管理员请求流式：走 RouterAgent ===
                for event_data in router_agent.route_stream(  # 遍历 RouterAgent 的流式输出
                    input_text=request.input,
                    conversation_id=request.conversation_id,
                    user_id=request.user_id,
                    context=request.context or "",
                    is_admin=True,
                    goal=request.goal,
                    run_id=run_id,
                    trace_id=trace_id
                ):
                    # 解析 SSE 数据获取 task_type
                    parsed_str = event_data.strip().replace("data: ", "").replace("\n\n", "")  # 清理 SSE 格式
                    try:
                        parsed = json.loads(parsed_str)  # 尝试解析 JSON
                        if parsed.get("type") == "routed":  # 如果是路由完成事件
                            task_type = parsed.get("task_type", "admin")  # 提取任务类型
                    except json.JSONDecodeError:  # JSON 解析失败
                        pass  # 忽略无法解析的数据

                    yield f"data: {event_data}\n\n"  # 以 SSE 格式转发事件
            else:
                # === 普通请求流式：走 Orchestrator ===
                for event_json in orchestrator.run_stream(  # 遍历 Orchestrator 的流式输出
                    input_text=request.input,
                    conversation_id=request.conversation_id,
                    user_id=request.user_id,
                    context=request.context or "",
                    goal=request.goal,
                    run_id=run_id,
                    trace_id=trace_id
                ):
                    yield f"data: {event_json}\n\n"  # 以 SSE 格式转发事件（Orchestrator 输出的是原始 JSON）

                # 流结束后同步最终状态
                state = orchestrator.get_state(run_id)  # 获取最终状态
                if state:  # 如果状态存在
                    stored_states[run_id] = state  # 同步到外部 stored_states
                    task_type = _derive_task_type(state)  # 推导任务类型

            # 更新统计
            duration_ms = (time.time() - start_time) * 1000  # 计算耗时
            task_stats[task_type]["total"] += 1  # 总数 +1
            task_stats[task_type]["success"] += 1  # 成功数 +1
            task_stats[task_type]["total_duration_ms"] += duration_ms  # 累加耗时

            yield f"data: {json.dumps({'type': 'complete', 'run_id': run_id})}\n\n"  # 发送完成事件

            _cleanup_old_states()  # 清理旧状态

        except Exception as e:  # 捕获异常
            duration_ms = (time.time() - start_time) * 1000  # 计算耗时
            task_stats[task_type]["total"] += 1  # 总数 +1
            task_stats[task_type]["failed"] += 1  # 失败数 +1
            task_stats[task_type]["total_duration_ms"] += duration_ms  # 累加耗时

            logger.error(f"[Agent API] Stream error: {str(e)}")  # 记录错误日志
            yield f"data: {json.dumps({'type': 'error', 'content': str(e), 'run_id': run_id})}\n\n"  # 发送错误事件

    return StreamingResponse(  # 返回流式响应
        event_generator(),  # 传入异步生成器
        media_type="text/event-stream",  # SSE 的 MIME 类型
        headers={  # 响应头
            "Cache-Control": "no-cache",  # 禁用缓存
            "Connection": "keep-alive",  # 保持长连接
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )


@router.get("/agent/run/{run_id}")  # GET /agent/run/{run_id} - 获取运行状态
async def get_run_status(run_id: str):
    """
    获取 Agent 运行状态

    通过 run_id 查询运行的状态、步骤进度和耗时。
    状态数据来源于 Orchestrator 事件处理器实时同步的 stored_states。
    """
    if run_id not in stored_states:  # 如果 run_id 不在存储中
        return {  # 返回未找到状态
            "run_id": run_id,
            "status": "not_found",
            "message": "Run not found or expired"
        }

    state = stored_states[run_id]  # 获取 AgentState 对象
    return {  # 返回完整运行状态
        "run_id": state.run_id,  # 运行 ID
        "trace_id": state.trace_id,  # 追踪 ID
        "status": state.status.value,  # 状态值（枚举转字符串）
        "goal": state.goal,  # 执行目标
        "original_input": state.original_input,  # 原始输入
        "current_step_index": state.current_step_index,  # 当前步骤索引
        "steps": [  # 步骤摘要列表
            {
                "step_id": s.step_id,  # 步骤 ID
                "step_name": s.step_name,  # 步骤名称
                "status": s.status.value,  # 步骤状态
                "duration_ms": s.duration_ms  # 步骤耗时
            }
            for s in state.steps  # 遍历所有步骤
        ],
        "intermediate_conclusions": [  # 中间结论摘要
            {
                "conclusion_type": c.conclusion_type,  # 结论类型
                "content": c.content,  # 结论内容
                "confidence": c.confidence  # 置信度
            }
            for c in state.intermediate_conclusions  # 遍历所有中间结论
        ],
        "elapsed_time": state.elapsed_time,  # 已消耗时间（秒）
        "start_time": state.start_time,  # 开始时间戳
        "end_time": state.end_time  # 结束时间戳
    }


@router.get("/agent/run/{run_id}/steps")  # GET /agent/run/{run_id}/steps - 获取步骤详情
async def get_run_steps(run_id: str):
    """
    获取 Agent 运行步骤详情

    返回每个步骤的完整信息：输入数据、输出数据、状态、耗时等。
    """
    if run_id not in stored_states:  # 检查 run_id 是否存在
        raise HTTPException(status_code=404, detail="Run not found")  # 不存在返回 404

    state = stored_states[run_id]  # 获取 Agent 状态
    return {  # 返回步骤详情
        "run_id": run_id,  # 运行 ID
        "status": state.status.value,  # 运行状态
        "steps": [  # 步骤详情列表
            {
                "step_id": s.step_id,  # 步骤 ID
                "step_type": s.step_type.value,  # 步骤类型（枚举值）
                "step_name": s.step_name,  # 步骤名称
                "status": s.status.value,  # 步骤状态（枚举值）
                "input_data": s.input_data,  # 步骤输入数据
                "output_data": s.output_data,  # 步骤输出数据
                "error_message": s.error_message,  # 错误消息
                "duration_ms": s.duration_ms,  # 步骤耗时（毫秒）
                "tool_call_id": s.tool_call_id,  # 关联的工具调用 ID
                "start_time": s.start_time,  # 开始时间
                "end_time": s.end_time  # 结束时间
            }
            for s in state.steps  # 遍历所有步骤
        ]
    }


@router.get("/agent/run/{run_id}/tool-calls")  # GET /agent/run/{run_id}/tool-calls - 获取工具调用
async def get_run_tool_calls(run_id: str):
    """
    获取 Agent 运行的工具调用记录

    优先从 AgentState.tool_calls 获取，如果没有则 fallback 到 tool_execution_tracker。
    """
    # 第一优先级：从 stored_states 获取（Orchestrator 路径产生的状态）
    if run_id in stored_states:  # 如果在存储中找到
        state = stored_states[run_id]  # 获取状态
        tool_calls = _extract_tool_calls(run_id, state)  # 提取工具调用记录
        return {  # 返回工具调用信息
            "run_id": run_id,
            "status": state.status.value,  # 运行状态
            "tool_calls": tool_calls  # 工具调用列表
        }

    # 第二优先级：从 tool_execution_tracker 获取（通过 tool_registry.invoke_tool() 产生的）
    tracker_calls = tool_execution_tracker.get_tool_calls_by_run_id(run_id)  # 按运行 ID 查询
    if tracker_calls:  # 如果有调用记录
        return {  # 返回工具调用信息
            "run_id": run_id,
            "status": "completed",  # 推测状态为完成
            "tool_calls": [  # 工具调用列表
                {
                    "tool_call_id": call.tool_call_id,  # 调用 ID
                    "tool_name": call.tool_name,  # 工具名称
                    "input_params": call.input_params,  # 输入参数
                    "output": call.output,  # 输出结果
                    "status": call.status,  # 调用状态
                    "duration_ms": call.duration_ms,  # 耗时
                    "error_message": call.error_message,  # 错误信息
                    "timestamp": call.timestamp  # 时间戳
                }
                for call in tracker_calls  # 遍历所有调用记录
            ]
        }

    raise HTTPException(status_code=404, detail="Run not found")  # 两个来源都没有，返回 404


@router.get("/agent/tools")  # GET /agent/tools - 列出所有可用工具
async def list_tools():
    """
    列出所有可用的 Agent 工具

    Returns:
        已注册工具的详细信息列表（名称、描述、输入/输出 Schema、元数据）
    """
    from tools.registry import tool_registry  # 延迟导入，避免循环依赖

    tools = tool_registry.get_all_tools()  # 获取所有已注册的工具
    return {  # 返回工具列表
        "tools": [  # 工具信息列表
            tool_registry.get_tool_info(name)  # 获取每个工具的详细信息
            for name in tools.keys()  # 遍历工具名称
        ]
    }


@router.get("/agent/stats")  # GET /agent/stats - 获取任务统计
async def get_agent_stats():
    """
    获取 Agent 任务统计信息

    Returns:
        各任务类型的统计（总数、成功率、平均耗时）和全局汇总
    """
    stats = []  # 统计结果列表
    total_all = 0  # 所有任务总数
    success_all = 0  # 所有任务成功数
    failed_all = 0  # 所有任务失败数

    for task_type, data in task_stats.items():  # 遍历每种任务类型的统计
        total = data["total"]  # 总数
        success = data["success"]  # 成功数
        failed = data["failed"]  # 失败数
        avg_duration = data["total_duration_ms"] / total if total > 0 else 0  # 平均耗时

        total_all += total  # 累加总数
        success_all += success  # 累加成功数
        failed_all += failed  # 累加失败数

        stats.append({  # 添加该类型的统计
            "task_type": task_type,  # 任务类型
            "total": total,  # 总数
            "success": success,  # 成功数
            "failed": failed,  # 失败数
            "success_rate": round(success / total * 100, 2) if total > 0 else 0,  # 成功率
            "avg_duration_ms": round(avg_duration, 2)  # 平均耗时
        })

    return {  # 返回汇总统计
        "task_stats": stats,  # 各任务类型的统计列表
        "summary": {  # 汇总信息
            "total": total_all,  # 总数
            "success": success_all,  # 成功数
            "failed": failed_all,  # 失败数
            "overall_success_rate": round(success_all / total_all * 100, 2) if total_all > 0 else 0  # 总成功率
        },
        "active_runs": len([s for s in stored_states.values()  # 统计正在运行的任务数
                            if s.status == AgentStatus.RUNNING]),
        "total_stored_states": len(stored_states),  # 存储的状态总数
        "keyword_stats": router_agent.get_task_stats()  # RouterAgent 的关键词统计
    }


@router.get("/health")  # GET /health - 健康检查
async def health_check():
    """
    健康检查

    Returns:
        服务健康状态和运行信息
    """
    return {  # 返回健康状态
        "status": "healthy",  # 状态为健康
        "service": "agent-service",  # 服务名称
        "timestamp": time.time(),  # 当前时间戳
        "stored_states_count": len(stored_states)  # 存储的状态数量
    }
