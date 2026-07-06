from typing import Dict, Any, Optional, List  # 导入类型注解：Dict（字典类型）、Any（任意类型）、Optional（可选类型）、List（列表类型）
from agent.state import AgentState, AgentStep, StepType, StepStatus  # 从 agent.state 导入状态相关类
from agent.planner import Planner, QuestionClassification, RewriteResult, SufficiencyResult  # 从规划器导入相关数据类
from intent.classifier import IntentResult  # 从意图分类器导入意图识别结果类
from tools.registry import tool_registry  # 从工具注册表模块导入工具注册表单例
from core.llm import LLMService  # 从 LLM 核心模块导入 LLM 服务类
from core.vector_store import vector_store  # 从向量存储模块导入向量存储单例
from core.config import config
import ast  # 导入 ast 模块，用于安全解析字符串化的字典
import time  # 导入 time 模块
import logging  # 导入 logging 模块
import json  # 导入 json 模块
import os  # 导入 os 模块，用于文件路径操作

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器


class Executor:  # 步骤执行器类，负责执行各个步骤
    """步骤执行器 - 负责执行各个步骤"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.planner = Planner()  # 创建规划器实例
        self.llm_service = LLMService()  # 创建 LLM 服务实例
        self.vector_store = vector_store  # 引用全局向量存储实例
        self._memory_agent = None  # 记忆 Agent 的延迟加载缓存，初始为 None

    @property  # @property 装饰器，将方法变为属性访问，用法：self.memory_agent 而不是 self.memory_agent()
    def memory_agent(self):  # 延迟加载 MemoryAgent，第一次访问时才创建实例
        """延迟加载 MemoryAgent"""  # 方法文档字符串
        if self._memory_agent is None:  # 如果尚未创建实例
            from agent.memory_agent import MemoryAgent  # 延迟导入，避免循环依赖
            self._memory_agent = MemoryAgent()  # 创建 MemoryAgent 实例并缓存
        return self._memory_agent  # 返回缓存的实例

    def execute_step(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行单个步骤
        """执行单个步骤"""  # 方法文档字符串
        step.start()  # 调用步骤的 start 方法，设置状态为 RUNNING 并记录开始时间
        logger.info(f"[{state.run_id}] Executing step: {step.step_name} (type: {step.step_type.value})")  # 记录执行日志

        try:  # try-except 异常处理
            if step.step_type == StepType.INTENT_RECOGNITION:  # 意图识别步骤
                return self._execute_intent_recognition(state, step)  # 执行意图识别
            elif step.step_type == StepType.QUESTION_CLASSIFICATION:  # 问题分类步骤
                return self._execute_question_classification(state, step)  # 执行问题分类
            elif step.step_type == StepType.CLARIFICATION:  # 澄清步骤
                return self._execute_clarification(state, step)  # 执行澄清判断
            elif step.step_type == StepType.QUESTION_REWRITE:  # 问题改写步骤
                return self._execute_question_rewrite(state, step)  # 执行问题改写
            elif step.step_type == StepType.KNOWLEDGE_SEARCH:  # 知识检索步骤
                return self._execute_knowledge_search(state, step)  # 执行知识检索
            elif step.step_type == StepType.RESULT_EVALUATION:  # 结果评估步骤
                return self._execute_result_evaluation(state, step)  # 执行结果评估
            elif step.step_type == StepType.ANSWER_GENERATION:  # 答案生成步骤
                return self._execute_answer_generation(state, step)  # 执行答案生成
            elif step.step_type == StepType.MEMORY_READ:  # 记忆读取步骤
                return self._execute_memory_read(state, step)  # 执行记忆读取
            elif step.step_type == StepType.MEMORY_WRITE:  # 记忆写入步骤
                return self._execute_memory_write(state, step)  # 执行记忆写入
            elif step.step_type == StepType.MEMORY_COMPRESS:  # 记忆压缩步骤
                return self._execute_memory_compress(state, step)  # 执行记忆压缩
            elif step.step_type == StepType.TOOL_CALL:  # 工具调用步骤
                return self._execute_tool_call(state, step)  # 执行工具调用
            else:  # 未知步骤类型
                raise ValueError(f"Unknown step type: {step.step_type}")  # 抛出值错误异常
        except Exception as e:  # 捕获步骤执行过程中的所有异常
            logger.error(f"[{state.run_id}] Step {step.step_name} failed: {str(e)}")  # 记录错误日志
            step.fail(str(e))  # 将步骤标记为失败
            raise  # raise 不带参数重新抛出当前异常，让上层处理

    def _execute_intent_recognition(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行意图识别
        """执行意图识别"""  # 方法文档字符串
        intent_result = self.planner.recognize_intent(state)  # 调用规划器进行意图识别

        state.add_intermediate_conclusion(  # 将意图识别结果添加到中间结论
            step_id=step.step_id,  # 关联的步骤 ID
            conclusion_type="intent",  # 结论类型为意图
            content=intent_result.intent.value,  # 意图类型的字符串值
            confidence=intent_result.confidence  # 置信度
        )

        step.complete({  # 标记步骤完成，保存输出数据
            "intent": intent_result.intent.value,  # 意图类型字符串
            "confidence": intent_result.confidence,  # 置信度
            "reasoning": intent_result.reasoning,  # 判断理由
            "requires_clarification": intent_result.requires_clarification  # 是否需要澄清
        })

        return step.output_data  # 返回步骤的输出数据

    def _execute_question_classification(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行问题分类
        """执行问题分类"""  # 方法文档字符串
        question = state.original_input or ""  # 获取原始输入
        classification = self.planner.classify_question(question)  # 调用规划器进行问题分类

        state.add_intermediate_conclusion(  # 将分类结果添加到中间结论
            step_id=step.step_id,  # 步骤 ID
            conclusion_type="question_type",  # 结论类型为问题类型
            content=classification.question_type,  # 问题类型
            confidence=classification.confidence,  # 置信度
            sources=[{"keyword": kw} for kw in classification.keywords]  # 匹配到的关键词转为来源列表
        )

        step.complete({  # 标记步骤完成
            "question_type": classification.question_type,  # 问题类型
            "confidence": classification.confidence,  # 置信度
            "keywords": classification.keywords,  # 关键词列表
            "should_return_sources": classification.should_return_sources  # 是否返回来源
        })

        return step.output_data  # 返回输出数据

    def _execute_clarification(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行澄清判断
        """执行澄清判断"""  # 方法文档字符串
        intent = self.planner.recognize_intent(state)  # 重新进行意图识别
        needs_clarification, prompt = self.planner.check_clarification_needed(state, intent)  # 检查是否需要澄清，返回元组解构赋值，类似 Java 的 Pair<A, B>

        step.complete({  # 标记步骤完成
            "needs_clarification": needs_clarification,  # 是否需要澄清
            "prompt": prompt  # 澄清提示语
        })

        if needs_clarification:  # 如果需要澄清
            state.wait()  # 将 Agent 状态设为 WAITING，等待用户输入

        return step.output_data  # 返回输出数据

    def _execute_question_rewrite(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行问题改写
        """执行问题改写"""  # 方法文档字符串
        question = state.original_input or ""  # 获取原始输入
        rewrite_result = self.planner.rewrite_question(question, conversation_context=state.context or "")  # 调用规划器改写问题

        state.add_intermediate_conclusion(  # 将改写结果添加到中间结论
            step_id=step.step_id,  # 步骤 ID
            conclusion_type="rewritten_question",  # 结论类型为改写问题
            content=rewrite_result.rewritten_question,  # 改写后的问题
            confidence=rewrite_result.confidence  # 置信度
        )

        step.complete({  # 标记步骤完成
            "original_question": rewrite_result.original_question,  # 原始问题
            "rewritten_question": rewrite_result.rewritten_question,  # 改写后的问题
            "rewrite_type": rewrite_result.rewrite_type  # 改写类型
        })

        return step.output_data  # 返回输出数据

    def _execute_knowledge_search(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行知识检索
        """执行知识检索"""  # 方法文档字符串
        query = state.original_input or ""  # 获取原始输入作为检索查询

        rewritten_question = None  # 初始化改写后的问题为 None
        for conclusion in state.intermediate_conclusions:  # 遍历中间结论
            if conclusion.conclusion_type == "rewritten_question":  # 找到改写问题的结论
                rewritten_question = conclusion.content  # 获取改写后的问题
                break  # 找到后跳出循环

        search_query = rewritten_question if rewritten_question else query  # 优先使用改写后的问题，如果没有则使用原始问题

        tool_call_id = None  # 初始化工具调用 ID
        if tool_registry.has_tool("knowledge_search"):  # 如果知识检索工具已注册
            try:  # try-except 异常处理
                result = tool_registry.invoke_tool(  # 调用知识检索工具
                    "knowledge_search",  # 工具名称
                    {
                        "query": search_query,
                        "top_k": config.RAG_TOP_K,
                        "similarity_threshold": config.RAG_SIMILARITY_THRESHOLD,
                        "use_rerank": config.RAG_USE_RERANK,
                    },
                    run_id=state.run_id  # 运行 ID
                )
                chunks = result.get("chunks", [])  # 获取检索到的文档片段
                scores = result.get("scores", [])  # 获取相似度分数
                tool_call_id = result.get("tool_call_id")  # 获取工具调用 ID
            except Exception as e:  # 工具调用失败
                logger.warning(f"[{state.run_id}] knowledge_search tool failed: {e}")  # 记录警告
                chunks = self.vector_store.search(
                    search_query,
                    k=config.RAG_TOP_K,
                    similarity_threshold=config.RAG_SIMILARITY_THRESHOLD,
                    use_rerank=config.RAG_USE_RERANK,
                )
                scores = [getattr(doc, 'score', 0.5) for doc in chunks]  # getattr() 安全获取对象的属性，如果属性不存在则返回默认值 0.5
        else:  # 如果工具未注册
            chunks = self.vector_store.search(
                search_query,
                k=config.RAG_TOP_K,
                similarity_threshold=config.RAG_SIMILARITY_THRESHOLD,
                use_rerank=config.RAG_USE_RERANK,
            )
            scores = [getattr(doc, 'score', 0.5) for doc in chunks]  # 获取分数

        chunks = [self._normalize_chunk(chunk, scores[index] if index < len(scores) else None) for index, chunk in enumerate(chunks)]  # 统一工具结果和向量检索结果
        scores = [chunk.get("score", 0.5) for chunk in chunks]  # 使用规范化后的分数

        sufficiency = self.planner.evaluate_retrieval_sufficiency(chunks, query, scores)  # 评估检索结果充分性

        sources = []  # 初始化来源列表
        seen_sources = set()  # 来源去重集合
        for doc in chunks:  # 遍历每个文档片段
            source_info = self._source_from_chunk(doc)  # 构建来源信息字典
            source_key = (
                source_info.get("doc_id"),
                source_info.get("source"),
                source_info.get("page"),
                source_info.get("chunk_index")
            )
            if source_info and source_key not in seen_sources:  # 如果有有效来源且未出现过
                seen_sources.add(source_key)  # 记录来源
                sources.append(source_info)  # 添加到来源列表

        state.add_intermediate_conclusion(  # 将检索结论添加到中间结论
            step_id=step.step_id,  # 步骤 ID
            conclusion_type="retrieval",  # 结论类型为检索
            content={  # 结论内容
                "chunk_count": len(chunks),  # 检索到的片段数量
                "avg_score": sum(scores) / len(scores) if scores else 0,  # 平均相似度分数
                "is_sufficient": sufficiency.is_sufficient  # 是否充分
            },
            confidence=sufficiency.confidence,  # 置信度
            sources=sources  # 来源列表
        )

        step.tool_call_id = tool_call_id  # 记录工具调用 ID
        step.complete({  # 标记步骤完成
            "chunks": chunks,  # 已规范化的片段，包含 content、metadata 和 score
            "scores": scores,  # 所有分数
            "sources": sources,  # 来源列表
            "is_sufficient": sufficiency.is_sufficient,  # 是否充分
            "reasoning": sufficiency.reasoning  # 判断理由
        })

        return step.output_data  # 返回输出数据

    def _execute_result_evaluation(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行结果充分性判断
        """执行结果充分性判断"""  # 方法文档字符串
        chunks = None  # 初始化检索结果为 None
        for s in state.steps:  # 遍历所有步骤
            if s.step_type == StepType.KNOWLEDGE_SEARCH and s.output_data:  # 找到知识检索步骤且有输出
                chunks = s.output_data.get("chunks", [])  # 获取检索到的片段
                break  # 找到后跳出循环

        if chunks is None:  # 如果没有找到检索结果
            step.complete({  # 标记步骤完成（但不充分）
                "is_sufficient": False,  # 不充分
                "reasoning": "未找到检索结果"  # 原因
            })
            return step.output_data  # 返回输出数据

        sufficiency = self.planner.evaluate_retrieval_sufficiency(  # 评估检索充分性
            [type('obj', (object,), {'page_content': c.get('content', '')}) for c in chunks],  # type('obj', (object,), {...}) 动态创建匿名类，类似 Java 的匿名内部类
            state.original_input or ""  # 原始输入
        )

        state.add_intermediate_conclusion(  # 添加充分性结论
            step_id=step.step_id,  # 步骤 ID
            conclusion_type="sufficiency",  # 结论类型为充分性
            content={  # 结论内容
                "is_sufficient": sufficiency.is_sufficient,  # 是否充分
                "reasoning": sufficiency.reasoning  # 理由
            },
            confidence=sufficiency.confidence  # 置信度
        )

        step.complete({  # 标记步骤完成
            "is_sufficient": sufficiency.is_sufficient,  # 是否充分
            "confidence": sufficiency.confidence,  # 置信度
            "reasoning": sufficiency.reasoning,  # 理由
            "missing_aspects": sufficiency.missing_aspects,  # 缺失的方面
            "suggestions": sufficiency.suggestions  # 改进建议
        })

        return step.output_data  # 返回输出数据

    def _execute_answer_generation(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行答案生成
        """执行答案生成（使用 Memory Agent 加载记忆）"""  # 方法文档字符串
        question = state.original_input or ""  # 获取原始问题
        context = state.context or ""  # 获取上下文

        # 使用 Memory Agent 加载记忆
        memory_context = self.memory_agent.load_memory(state)  # 通过 @property 属性访问 MemoryAgent 并加载记忆
        full_context = context  # 初始化完整上下文
        if memory_context:  # 如果有记忆上下文
            full_context = f"{context}\n\n{memory_context}" if context else memory_context  # 拼接上下文和记忆

        chunks = None  # 初始化检索片段
        sources = []  # 初始化来源列表
        retrieval_sufficient = True
        saw_knowledge_search = False
        for s in state.steps:  # 遍历所有步骤
            if s.step_type == StepType.KNOWLEDGE_SEARCH and s.output_data:  # 找到知识检索步骤
                saw_knowledge_search = True
                chunks = s.output_data.get("chunks", [])  # 获取片段
                sources = s.output_data.get("sources", [])  # 获取来源
                retrieval_sufficient = s.output_data.get("is_sufficient", False)
                break  # 找到后跳出

        should_return_sources = True  # 默认返回来源
        for s in state.steps:  # 遍历所有步骤
            if s.step_type == StepType.QUESTION_CLASSIFICATION and s.output_data:  # 找到问题分类步骤
                should_return_sources = s.output_data.get("should_return_sources", True)  # 获取是否应返回来源
                break  # 找到后跳出

        if (
            config.RAG_STRICT_MODE
            and saw_knowledge_search
            and (
                not chunks
                or not retrieval_sufficient
                or len(sources or []) < config.RAG_MIN_SOURCE_COUNT
            )
        ):
            answer = self._insufficient_evidence_answer()
            step.complete({
                "answer": answer,
                "sources": sources if should_return_sources else [],
                "has_sources": False,
                "evidence_sufficient": False,
            })
            return step.output_data

        docs = []  # 初始化文档对象列表
        if chunks:  # 如果有检索片段
            for chunk in chunks:  # 遍历每个片段
                normalized_chunk = self._normalize_chunk(chunk)  # 兼容旧缓存和直接工具结果
                doc = type('Doc', (), {  # type() 动态创建匿名类（类似 Java 匿名内部类），三个参数：类名、基类元组、属性字典
                    'page_content': normalized_chunk.get('content', ''),  # 页面内容
                    'metadata': normalized_chunk.get('metadata', {})  # 元数据
                })()  # 注意末尾的 () 表示立即实例化该类
                docs.append(doc)  # 添加到文档列表

        # 如果有文档且应该返回来源，传入文档；否则传空列表
        answer = self.llm_service.get_answer(  # 调用 LLM 服务生成答案
            question, docs if (docs and should_return_sources) else [], full_context  # 参数：问题、文档列表（可能为空）、完整上下文
        )

        # 2. 写入会话记忆
        if state.conversation_id and tool_registry.has_tool("conversation_memory_write"):  # 如果有会话且写入工具可用
            try:  # try-except 异常处理
                # 写入用户问题
                tool_registry.invoke_tool(  # 调用记忆写入工具
                    "conversation_memory_write",  # 工具名称
                    {  # 参数
                        "conversation_id": state.conversation_id,  # 会话 ID
                        "role": "user",  # 角色：用户
                        "content": question  # 用户问题
                    },
                    run_id=state.run_id  # 运行 ID
                )
                # 写入AI回答
                tool_registry.invoke_tool(  # 调用记忆写入工具
                    "conversation_memory_write",  # 工具名称
                    {  # 参数
                        "conversation_id": state.conversation_id,  # 会话 ID
                        "role": "assistant",  # 角色：AI 助手
                        "content": answer  # AI 回答
                    },
                    run_id=state.run_id  # 运行 ID
                )
                logger.info(f"[{state.run_id}] Saved conversation to memory")  # 记录信息日志
            except Exception as e:  # 捕获异常
                logger.warning(f"[{state.run_id}] Failed to write conversation memory: {e}")  # 记录警告

        step.complete({  # 标记步骤完成
            "answer": answer,  # 生成的答案
            "sources": sources if should_return_sources else [],  # 来源列表（根据分类结果决定是否包含）
            "has_sources": len(sources) > 0 if should_return_sources else False  # 是否有来源
        })

        return step.output_data  # 返回输出数据

    def _normalize_chunk(self, chunk: Any, score: Optional[float] = None) -> Dict[str, Any]:
        """把检索结果统一成可序列化、带 metadata 的片段字典。"""
        metadata = {}
        content = ""
        chunk_score = score

        if isinstance(chunk, dict):
            metadata = chunk.get("metadata") or {}
            content = chunk.get("content") or chunk.get("page_content") or chunk.get("text") or ""
            chunk_score = chunk.get("score", chunk_score)
        else:
            metadata = getattr(chunk, "metadata", {}) or {}
            content = getattr(chunk, "page_content", str(chunk))
            chunk_score = getattr(chunk, "score", chunk_score)

        if isinstance(content, str):
            parsed = self._parse_serialized_chunk(content)
            if parsed:
                content = parsed.get("content") or content
                parsed_metadata = parsed.get("metadata") or {}
                metadata = {**parsed_metadata, **metadata}

        return {
            "content": content,
            "metadata": metadata,
            "score": chunk_score if chunk_score is not None else 0.5,
        }

    def _parse_serialized_chunk(self, value: str) -> Optional[Dict[str, Any]]:
        text = value.strip()
        if not (text.startswith("{") and text.endswith("}")):
            return None

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return None

        return parsed if isinstance(parsed, dict) else None

    def _source_from_chunk(self, chunk: Dict[str, Any]) -> Dict[str, Any]:
        metadata = chunk.get("metadata") or {}
        source = (
            metadata.get("source")
            or metadata.get("file_name")
            or metadata.get("filename")
            or metadata.get("title")
            or ""
        )
        doc_id = metadata.get("doc_id") or metadata.get("platform_knowledge_id") or ""
        page = metadata.get("page_label") or (metadata.get("page") if metadata.get("page") is not None else "")
        chunk_index = metadata.get("chunk_index") if metadata.get("chunk_index") is not None else ""
        doc_name = os.path.basename(str(source)) if source else str(metadata.get("title") or "")

        if not (source or doc_id or doc_name):
            return {}

        return {
            "title": doc_name or str(source) or "知识库片段",
            "doc": doc_name or str(source),
            "source": source,
            "doc_id": doc_id,
            "page": page,
            "chunk_index": chunk_index,
            "snippet": self._short_snippet(chunk.get("content", "")),
        }

    def _short_snippet(self, content: str, limit: int = 180) -> str:
        snippet = " ".join(str(content or "").split())
        if len(snippet) > limit:
            snippet = snippet[:limit].rstrip("，,；;、 ") + "..."
        return snippet

    def _insufficient_evidence_answer(self) -> str:
        return (
            "当前知识库中没有检索到足够可靠的资料来支持明确回答。"
            "为了降低误导风险，我不能基于猜测给出诊断、用药或治疗结论。\n\n"
            "建议补充：主要症状、持续时间、年龄、既往病史、正在使用的药物、检查结果和症状变化。"
            "如果出现胸痛、呼吸困难、意识改变、明显出血、高热不退或症状快速加重，请及时联系医生或就近就医。"
        )

    def _format_history(self, messages: list) -> str:  # 格式化对话历史为文本
        """格式化对话历史为上下文字符串"""  # 方法文档字符串
        if not messages:  # 如果消息列表为空
            return ""  # 返回空字符串

        formatted = []  # 初始化格式化列表
        for msg in messages:  # 遍历每条消息
            role = msg.get("role", "unknown")  # 获取角色
            content = msg.get("content", "")  # 获取内容
            if role == "system":  # 系统消息
                formatted.append(content)  # 直接添加
            elif role == "user":  # 用户消息
                formatted.append(f"用户: {content}")  # 添加前缀
            elif role == "assistant":  # AI 消息
                formatted.append(f"AI: {content}")  # 添加前缀

        return "\n".join(formatted)  # 用换行拼接

    def _execute_memory_write(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行记忆写入
        """执行记忆写入（使用 Memory Agent）"""  # 方法文档字符串
        answer = None  # 初始化答案
        for s in reversed(state.steps):  # reversed() 反向遍历步骤列表，从最后一个步骤开始查找
            if s.step_type == StepType.ANSWER_GENERATION and s.output_data:  # 找到答案生成步骤
                answer = s.output_data.get("answer", "")  # 获取答案
                break  # 找到后跳出

        # 使用 Memory Agent 保存记忆
        self.memory_agent.save_memory(state, state.original_input, answer)  # 调用 MemoryAgent 保存记忆

        step.complete({  # 标记步骤完成
            "success": True,  # 成功
            "message": "记忆写入完成"  # 消息
        })

        return step.output_data  # 返回输出数据

    def _execute_memory_read(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行记忆读取
        """执行记忆读取（使用 Memory Agent）"""  # 方法文档字符串
        context = self.memory_agent.load_memory(state)  # 调用 MemoryAgent 加载记忆

        step.complete({  # 标记步骤完成
            "context": context,  # 记忆上下文内容
            "has_history": bool(context)  # 是否有历史记录，bool() 将非空字符串转为 True
        })

        # 将记忆上下文保存到 state，供后续步骤使用
        if context:  # 如果有记忆上下文
            state.context = f"{state.context}\n\n{context}" if state.context else context  # 拼接到现有上下文

        return step.output_data  # 返回输出数据

    def _execute_memory_compress(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行记忆压缩
        """执行记忆压缩"""  # 方法文档字符串
        # 压缩逻辑已在 conversation_memory_read 工具中实现
        # 此步骤主要用于标记和日志记录
        logger.info(f"[{state.run_id}] Memory compress step executed")  # 记录信息日志

        step.complete({  # 标记步骤完成
            "success": True,  # 成功
            "message": "记忆压缩检查完成"  # 消息
        })

        return step.output_data  # 返回输出数据

    def _execute_tool_call(self, state: AgentState, step: AgentStep) -> Dict[str, Any]:  # 执行通用工具调用
        """执行通用工具调用"""  # 方法文档字符串
        tool_name = step.input_data.get("tool_name")  # 从步骤输入中获取工具名称
        parameters = step.input_data.get("parameters", {})  # 从步骤输入中获取工具参数

        if not tool_registry.has_tool(tool_name):  # 如果工具不存在
            raise ValueError(f"Tool not found: {tool_name}")  # 抛出异常

        result = tool_registry.invoke_tool(tool_name, parameters, run_id=state.run_id)  # 调用工具

        step.complete({  # 标记步骤完成
            "result": result,  # 工具返回结果
            "tool_name": tool_name  # 工具名称
        })

        return step.output_data  # 返回输出数据
