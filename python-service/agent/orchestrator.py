from typing import Dict, Any, Optional, Generator, Callable  # 导入类型注解：Dict（字典类型）、Any（任意类型）、Optional（可选类型）、Generator（生成器类型，用于 yield 关键字）、Callable（可调用对象类型）
from agent.state import AgentState, AgentStatus, StepType, TerminationCondition  # 从 agent.state 导入状态相关类
from agent.planner import Planner  # 从规划器模块导入 Planner
from intent.classifier import IntentType  # 从意图分类器导入意图类型枚举
from agent.executor import Executor  # 从执行器模块导入 Executor
from agent.events import EventBus, Event, RunStartedEvent, RunCompletedEvent, RunFailedEvent, StepStartedEvent, StepCompletedEvent, StepFailedEvent  # 从事件模块导入事件相关类
from agent.policies import policies  # 从策略模块导入策略管理器单例
import time  # 导入 time 模块
import logging  # 导入 logging 模块
import uuid  # 导入 uuid 模块
import json  # 导入 json 模块

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器


class Orchestrator:  # Agent 编排器类，负责协调规划和执行，管理整个 Agent 运行流程
    """Agent编排器 - 负责协调整个Agent执行流程"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.planner = Planner()  # 创建规划器实例
        self.executor = Executor()  # 创建执行器实例
        self.event_bus = EventBus()  # 创建事件总线实例（单例）
        self.policies = policies  # 引用全局策略管理器
        self._states: Dict[str, AgentState] = {}  # 状态存储字典，key 为 run_id，value 为 AgentState（类似 Java 的 ConcurrentHashMap）

    def create_state(self, input_text: str, conversation_id: Optional[str] = None,  # 创建 Agent 状态对象
                    user_id: Optional[str] = None, goal: Optional[str] = None,  # 参数：输入文本、会话ID、用户ID、目标
                    run_id: Optional[str] = None, trace_id: Optional[str] = None) -> AgentState:  # 运行ID、追踪ID
        """创建Agent状态"""  # 方法文档字符串
        state = AgentState(  # 创建 AgentState 实例
            run_id=run_id or str(uuid.uuid4()),  # 如果未提供运行 ID 则生成 UUID，or 短路特性
            trace_id=trace_id or str(uuid.uuid4()),  # 如果未提供追踪 ID 则生成 UUID
            conversation_id=conversation_id,  # 会话 ID
            user_id=user_id,  # 用户 ID
            goal=goal or f"回答用户问题: {input_text[:50]}...",  # 如果未提供目标则自动生成，input_text[:50] 取前50个字符
            original_input=input_text,  # 保存原始输入
            status=AgentStatus.PENDING  # 初始状态为待执行
        )
        return state  # 返回状态对象

    def run(self, input_text: str, conversation_id: Optional[str] = None,  # 同步执行 Agent 的入口方法
            user_id: Optional[str] = None, context: str = "",  # 参数：输入文本、会话ID、用户ID、上下文
            goal: Optional[str] = None, run_id: Optional[str] = None,  # 目标、运行ID
            trace_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:  # **kwargs 接收额外的关键字参数，返回结果字典
        """同步执行Agent"""  # 方法文档字符串
        state = self.create_state(input_text, conversation_id, user_id, goal, run_id, trace_id)  # 创建状态对象
        state.context = context  # 设置上下文
        self._states[state.run_id] = state  # 存储状态到内部字典，供 get_state() 查询（类似 Java 的 cache.put(key, value)）

        is_valid, error_msg = self.policies.validate_input(input_text)  # 验证输入安全性，元组解构赋值
        if not is_valid:  # 如果输入不合法
            state.fail(error_msg or "输入验证失败", "INPUT_VALIDATION_ERROR")  # 标记失败
            return self._build_error_response(state)  # 返回错误响应

        state.start()  # 开始执行，状态变为 RUNNING
        self.event_bus.publish(RunStartedEvent(  # 发布运行开始事件
            run_id=state.run_id,  # 运行 ID
            goal=state.goal,  # 目标
            input_data=input_text  # 输入数据
        ))

        try:  # try-except 包裹整个执行流程
            planned_steps = self.planner.plan_steps(state)  # 规划执行步骤
            state.planned_steps = planned_steps  # 保存计划步骤到状态

            for step_name in planned_steps:  # 按顺序执行每个步骤
                step_type = self._get_step_type(step_name)  # 获取步骤类型
                step = state.add_step(step_type, step_name, {"input": input_text})  # 添加步骤到状态

                self.event_bus.publish(StepStartedEvent(  # 发布步骤开始事件
                    run_id=state.run_id,  # 运行 ID
                    step_id=step.step_id,  # 步骤 ID
                    step_name=step_name,  # 步骤名称
                    step_type=step_type.value  # 步骤类型的字符串值
                ))

                retry_count = 0  # 重试计数器
                step_done = False  # 步骤是否完成标志

                while not step_done:  # 循环直到步骤完成
                    try:  # try-except 处理步骤执行异常
                        self.executor.execute_step(state, step)  # 执行步骤

                        self.event_bus.publish(StepCompletedEvent(  # 发布步骤完成事件
                            run_id=state.run_id,  # 运行 ID
                            step_id=step.step_id,  # 步骤 ID
                            step_name=step_name,  # 步骤名称
                            step_type=step_type.value,  # 步骤类型
                            output=step.output_data,  # 步骤输出数据
                            duration_ms=step.duration_ms or 0  # 步骤耗时（毫秒）
                        ))

                        step_done = True  # 标记步骤完成

                        if state.status == AgentStatus.WAITING:  # 如果 Agent 进入等待状态（需要澄清）
                            clarification_output = self._handle_clarification(state)  # 处理澄清请求
                            state.complete(clarification_output)  # 完成执行
                            break  # 跳出循环

                    except Exception as e:  # 步骤执行失败
                        logger.error(f"[{state.run_id}] Step {step_name} failed (attempt {retry_count + 1}): {str(e)}")  # 记录错误
                        self.event_bus.publish(StepFailedEvent(  # 发布步骤失败事件
                            run_id=state.run_id,  # 运行 ID
                            step_id=step.step_id,  # 步骤 ID
                            step_name=step_name,  # 步骤名称
                            step_type=step_type.value,  # 步骤类型
                            error=str(e)  # 错误信息
                        ))

                        if self.policies.should_retry(retry_count, e):  # 根据策略判断是否应该重试
                            retry_count += 1  # 增加重试计数
                        else:  # 不再重试
                            state.fail(str(e), "STEP_EXECUTION_ERROR")  # 标记失败
                            step_done = True  # 标记步骤完成（失败）
                            break  # 跳出循环

                should_terminate, reason = self.planner.should_terminate(state)  # 检查是否应该终止
                if should_terminate:  # 如果应该终止
                    logger.info(f"[{state.run_id}] Terminating: {reason}")  # 记录终止原因
                    if state.status == AgentStatus.PENDING:  # 如果还在待执行状态
                        state.complete(self._build_success_response(state))  # 构建响应并完成
                    break  # 跳出循环

            if state.status == AgentStatus.RUNNING:  # 如果所有步骤执行完但状态还是 RUNNING
                state.complete(self._build_success_response(state))  # 构建响应并完成

        except Exception as e:  # 捕获编排器级别的异常
            logger.error(f"[{state.run_id}] Orchestrator run failed: {str(e)}")  # 记录错误
            state.fail(str(e), "ORCHESTRATOR_ERROR")  # 标记失败
            self.event_bus.publish(RunFailedEvent(  # 发布运行失败事件
                run_id=state.run_id,  # 运行 ID
                error=str(e),  # 错误信息
                error_code="ORCHESTRATOR_ERROR"  # 错误码
            ))
            return self._build_error_response(state)  # 返回错误响应

        if state.status == AgentStatus.COMPLETED:  # 如果执行成功完成
            self.event_bus.publish(RunCompletedEvent(  # 发布运行完成事件
                run_id=state.run_id,  # 运行 ID
                output=state.final_output  # 最终输出
            ))
        elif state.status == AgentStatus.FAILED:  # 如果执行失败
            self.event_bus.publish(RunFailedEvent(  # 发布运行失败事件
                run_id=state.run_id,  # 运行 ID
                error=state.error_message,  # 错误信息
                error_code=state.error_code  # 错误码
            ))

        return state.final_output if state.final_output else self._build_error_response(state)  # 返回最终输出，如果为空则返回错误响应

    def run_stream(self, input_text: str, conversation_id: Optional[str] = None,  # 流式执行 Agent，使用 yield 返回生成器
                  user_id: Optional[str] = None, context: str = "",  # 参数同 run 方法
                  goal: Optional[str] = None, run_id: Optional[str] = None,
                  trace_id: Optional[str] = None, **kwargs) -> Generator[str, None, None]:  # Generator[YieldType, SendType, ReturnType] 生成器类型注解
        """流式执行Agent"""  # 方法文档字符串
        state = self.create_state(input_text, conversation_id, user_id, goal, run_id, trace_id)  # 创建状态
        state.context = context  # 设置上下文
        self._states[state.run_id] = state  # 存储状态到内部字典，流式执行期间也可查询实时状态

        is_valid, error_msg = self.policies.validate_input(input_text)  # 验证输入
        if not is_valid:  # 如果输入不合法
            state.fail(error_msg or "输入验证失败", "INPUT_VALIDATION_ERROR")  # 标记失败
            yield json.dumps({  # yield 关键字：暂停函数执行并返回一个值，下次调用时从暂停处继续。类似 Java 的 Stream 惰性求值
                "type": "error",  # 消息类型为错误
                "content": error_msg  # 错误内容
            })
            return  # 提前结束生成器

        state.start()  # 开始执行
        self.event_bus.publish(RunStartedEvent(  # 发布开始事件
            run_id=state.run_id,  # 运行 ID
            goal=state.goal,  # 目标
            input_data=input_text  # 输入
        ))

        try:  # try-except 包裹执行流程
            planned_steps = self.planner.plan_steps(state)  # 规划步骤
            state.planned_steps = planned_steps  # 保存计划

            for step_name in planned_steps:  # 遍历每个步骤
                step_type = self._get_step_type(step_name)  # 获取步骤类型
                step = state.add_step(step_type, step_name, {"input": input_text})  # 添加步骤

                yield json.dumps({  # yield 返回步骤开始消息
                    "type": "step_started",  # 消息类型
                    "step_name": step_name,  # 步骤名称
                    "step_type": step_type.value  # 步骤类型值
                })

                try:  # try-except 处理步骤异常
                    self.executor.execute_step(state, step)  # 执行步骤

                    yield json.dumps({  # yield 返回步骤完成消息
                        "type": "step_completed",  # 消息类型
                        "step_name": step_name,  # 步骤名称
                        "output": step.output_data  # 输出数据
                    })

                    if state.status == AgentStatus.WAITING:  # 如果需要澄清
                        clarification_output = self._handle_clarification(state)  # 处理澄清
                        state.complete(clarification_output)  # 完成
                        yield json.dumps({  # yield 返回澄清消息
                            "type": "clarification",  # 消息类型
                            "content": clarification_output  # 澄清内容
                        })
                        break  # 跳出循环

                    if step_type == StepType.ANSWER_GENERATION:  # 如果是答案生成步骤
                        answer = step.output_data.get("answer", "")  # 获取答案
                        sources = step.output_data.get("sources", [])  # 获取来源

                        yield json.dumps({  # yield 返回来源信息
                            "type": "sources",  # 消息类型
                            "content": sources  # 来源列表
                        })

                        for char in answer:  # 逐字符遍历答案
                            yield json.dumps({  # yield 逐个返回字符，实现打字机效果
                                "type": "token",  # 消息类型为 token
                                "content": char  # 单个字符
                            })

                        yield json.dumps({  # yield 返回结束消息
                            "type": "end",  # 消息类型为结束
                            "content": {  # 包含完整答案和来源
                                "answer": answer,  # 完整答案
                                "sources": sources  # 来源列表
                            }
                        })

                except Exception as e:  # 步骤执行失败
                    logger.error(f"[{state.run_id}] Step {step_name} failed: {str(e)}")  # 记录错误
                    yield json.dumps({  # yield 返回步骤失败消息
                        "type": "step_failed",  # 消息类型
                        "step_name": step_name,  # 步骤名称
                        "error": str(e)  # 错误信息
                    })
                    state.fail(str(e), "STEP_EXECUTION_ERROR")  # 标记失败
                    break  # 跳出循环

                should_terminate, reason = self.planner.should_terminate(state)  # 检查终止条件
                if should_terminate:  # 如果应该终止
                    break  # 跳出循环

            if state.status == AgentStatus.RUNNING:
                state.complete(self._build_success_response(state))

        except Exception as e:  # 编排器级别异常
            logger.error(f"[{state.run_id}] Orchestrator stream run failed: {str(e)}")  # 记录错误
            yield json.dumps({  # yield 返回错误消息
                "type": "error",  # 消息类型
                "content": str(e)  # 错误信息
            })
            state.fail(str(e), "ORCHESTRATOR_ERROR")  # 标记失败

    def _get_step_type(self, step_name: str) -> StepType:  # 将步骤名称映射为步骤类型枚举
        """获取步骤类型"""  # 方法文档字符串
        step_mapping = {  # 步骤名称到类型的映射字典
            "intent_recognition": StepType.INTENT_RECOGNITION,  # 意图识别
            "question_classification": StepType.QUESTION_CLASSIFICATION,  # 问题分类
            "clarification": StepType.CLARIFICATION,  # 澄清
            "question_rewrite": StepType.QUESTION_REWRITE,  # 问题改写
            "knowledge_search": StepType.KNOWLEDGE_SEARCH,  # 知识检索
            "result_evaluation": StepType.RESULT_EVALUATION,  # 结果评估
            "answer_generation": StepType.ANSWER_GENERATION,  # 答案生成
            "memory_read": StepType.MEMORY_READ,  # 记忆读取
            "memory_write": StepType.MEMORY_WRITE,  # 记忆写入
            "memory_compress": StepType.MEMORY_COMPRESS,  # 记忆压缩
            "identity_answer": StepType.ANSWER_GENERATION,  # 身份回答（复用答案生成步骤）
            "admin_operation": StepType.TOOL_CALL  # 管理操作（使用工具调用步骤）
        }
        return step_mapping.get(step_name, StepType.TOOL_CALL)  # dict.get(key, default) 安全获取，未知步骤默认为 TOOL_CALL

    def _handle_clarification(self, state: AgentState) -> Dict[str, Any]:  # 处理澄清请求
        """处理澄清请求"""  # 方法文档字符串
        clarification_step = None  # 初始化澄清步骤
        for step in reversed(state.steps):  # reversed() 反向遍历步骤列表
            if step.step_type == StepType.CLARIFICATION:  # 找到澄清步骤
                clarification_step = step  # 记录找到的步骤
                break  # 跳出循环

        if clarification_step and clarification_step.output_data.get("needs_clarification"):  # 如果需要澄清
            prompt = clarification_step.output_data.get("prompt", "请提供更多信息")  # 获取澄清提示语
            return {  # 返回澄清响应
                "type": "clarification",  # 类型
                "content": prompt,  # 提示语
                "requires_input": True  # 需要用户输入
            }

        return {  # 默认澄清响应
            "type": "clarification",  # 类型
            "content": "请详细描述您的问题",  # 默认提示语
            "requires_input": True  # 需要用户输入
        }

    def _build_success_response(self, state: AgentState) -> Dict[str, Any]:  # 构建成功响应
        """构建成功响应"""  # 方法文档字符串
        answer = None  # 初始化答案
        sources = []  # 初始化来源列表

        for step in reversed(state.steps):  # 反向遍历步骤
            if step.step_type == StepType.ANSWER_GENERATION and step.output_data:  # 找到答案生成步骤
                answer = step.output_data.get("answer", "")  # 获取答案
                sources = step.output_data.get("sources", [])  # 获取来源
                break  # 跳出循环

        if answer is None:  # 如果没有生成答案
            answer = "抱歉，我无法生成回答。"  # 使用默认提示

        return self.policies.format_response(answer, sources, True, "knowledge_qa")  # 使用策略格式化响应

    def _build_error_response(self, state: AgentState) -> Dict[str, Any]:  # 构建错误响应
        """构建错误响应"""  # 方法文档字符串
        return {  # 返回错误响应字典
            "answer": state.error_message or "服务暂时不可用，请稍后再试。",  # 错误信息或默认提示
            "sources": [],  # 无来源
            "has_sources": False,  # 没有来源
            "error": True,  # 标记为错误响应
            "error_code": state.error_code  # 错误码
        }

    def get_state(self, run_id: str) -> Optional[AgentState]:  # 获取 Agent 状态
        """获取Agent状态"""  # 方法文档字符串
        return self._states.get(run_id)  # 从内部字典获取状态，不存在时返回 None

    def get_all_states(self) -> Dict[str, AgentState]:  # 获取所有存储的状态
        """获取所有存储的Agent状态"""  # 方法文档字符串
        return dict(self._states)  # 返回副本，防止外部修改影响内部数据（类似 Java 的 new HashMap<>(map)）

    def clear_state(self, run_id: str) -> bool:  # 清理指定 run_id 的状态
        """清理指定运行的状态"""  # 方法文档字符串
        if run_id in self._states:  # 如果状态存在
            del self._states[run_id]  # 删除状态记录
            return True  # 返回删除成功
        return False  # 状态不存在，返回 False

    def interrupt(self, run_id: str) -> bool:  # 中断执行（预留接口）
        """中断执行"""  # 方法文档字符串
        if run_id in self._states:  # 如果状态存在
            state = self._states[run_id]  # 获取状态
            if state.status == AgentStatus.RUNNING:  # 如果正在运行
                state.interrupt()  # 标记为中断状态
                self.event_bus.publish(RunFailedEvent(  # 发布运行中断事件
                    run_id=run_id,  # 运行 ID
                    error="执行已被用户中断",  # 错误信息
                    error_code="INTERRUPTED"  # 错误码
                ))
                return True  # 中断成功
        return False  # 中断失败（状态不存在或非运行状态）
