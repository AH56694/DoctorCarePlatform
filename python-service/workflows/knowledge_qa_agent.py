from typing import Dict, Any, Optional, Generator  # 导入类型提示（Dict 字典类型，Any 任意类型，Optional 可为 None，Generator 生成器类型）
from agent.orchestrator import Orchestrator  # 从 agent.orchestrator 模块导入编排器类（协调多 Agent 协作）
from agent.state import AgentState  # 从 agent.state 模块导入 Agent 状态枚举
from agent.events import EventBus, event_bus  # 从 agent.events 模块导入事件总线和全局事件总线实例（类似 Java 的 EventBus / 观察者模式）
from workflows.retrieval_agent import RetrievalAgent  # 从 retrieval_agent 模块导入检索 Agent 类
from core.vector_store import vector_store  # 从 core.vector_store 模块导入全局向量存储实例（用于语义检索）
from core.llm import LLMService  # 从 core.llm 模块导入 LLM 服务类
from core.config import config
from tools.registry import tool_registry  # 从 tools.registry 模块导入工具注册表实例
import logging  # 导入日志模块
import json  # 导入 JSON 序列化模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class KnowledgeQAAgent:  # 定义知识问答 Agent 类
    """知识问答Agent - 三级链路：L1简化/L2标准/L3推理"""

    def __init__(self):  # 构造函数
        self.orchestrator = Orchestrator()  # 初始化编排器实例（用于回退方案）
        self.event_bus = event_bus  # 引用全局事件总线实例
        self.retrieval_agent = RetrievalAgent()  # 初始化检索 Agent 实例
        self.vector_store = vector_store  # 引用全局向量存储实例
        self.llm_service = LLMService()  # 初始化 LLM 服务实例
        self.strict_rag = config.RAG_STRICT_MODE
        self.similarity_threshold = config.RAG_SIMILARITY_THRESHOLD
        self.top_k = config.RAG_TOP_K
        self.use_rerank = config.RAG_USE_RERANK
        self.min_source_count = config.RAG_MIN_SOURCE_COUNT
        self._router = None  # 路由 Agent 延迟加载占位符（避免循环导入）
        self._reasoning_agent = None  # 推理 Agent 延迟加载占位符

    @property  # @property 装饰器：将方法变为属性（类似 Java 的懒加载 getter）
    def router(self):
        """延迟加载 RouterAgent（避免循环导入）"""
        if self._router is None:  # 如果路由 Agent 尚未初始化
            from workflows.router_agent import RouterAgent  # 延迟导入避免循环依赖
            self._router = RouterAgent()  # 创建路由 Agent 实例
        return self._router  # 返回已缓存的路由 Agent

    @property
    def reasoning_agent(self):
        """延迟加载 ReasoningAgent"""
        if self._reasoning_agent is None:  # 如果推理 Agent 尚未初始化
            from workflows.reasoning_agent import ReasoningAgent  # 延迟导入
            self._reasoning_agent = ReasoningAgent()  # 创建推理 Agent 实例
        return self._reasoning_agent  # 返回已缓存的推理 Agent

    def ask(self, question: str, conversation_id: Optional[str] = None,  # ask 方法：处理知识问答请求
            user_id: Optional[str] = None, context: str = "",
            **kwargs) -> Dict[str, Any]:
        """
        处理知识问答 - 三级链路

        L1 简单：直接检索+生成（80%请求，~2-3s）
        L2 标准：问题改写+检索+重排序+生成（15%请求，~5-8s）
        L3 推理：分解+逐个推理+汇总（5%请求，~10-15s，由 RouterAgent 处理）
        """
        logger.info(f"[KnowledgeQAAgent] Processing question: {question[:50]}...")  # 记录处理日志，截取前50字符

        try:
            # 1. 读取会话记忆作为上下文

            conversation_history = ""  # 初始化对话历史为空
            if conversation_id and tool_registry.has_tool("conversation_memory_read"):  # 如果有会话ID且存在记忆读取工具
                try:
                    history = tool_registry.invoke_tool(  # 调用记忆读取工具
                        "conversation_memory_read",
                        {"conversation_id": conversation_id, "limit": 10}  # 读取最近10条消息
                    )
                    messages = history.get("messages", [])  # 获取消息列表
                    if messages:  # 如果有消息
                        conversation_history = self._format_history(messages)  # 格式化为字符串
                        logger.info(f"[KnowledgeQAAgent] Loaded {len(messages)} messages from memory"
                                    f" (compressed: {history.get('compressed', False)})")  # 记录是否为压缩后的历史
                except Exception as e:
                    logger.warning(f"[KnowledgeQAAgent] Failed to read conversation memory: {e}")

            # 合并上下文
            full_context = context  # 使用传入的上下文作为基础
            if conversation_history:  # 如果有对话历史
                full_context = f"{context}\n\n{conversation_history}" if context else conversation_history  # 三元表达式（类似 Java 的 condition ? a : b），合并上下文

            # 2. 判断复杂度，选择链路
            complexity = self.router.classify_complexity(question)  # 通过路由 Agent 判断问题复杂度
            logger.info(f"[KnowledgeQAAgent] Complexity: {complexity}")  # 记录复杂度判断结果

            if complexity == "complex":  # 复杂问题：分解子问题+逐个推理+汇总（L3推理链路）
                return self._ask_l3(question, conversation_id, full_context)
            elif complexity == "medium":  # 中等问题：问题改写+检索+重排序+生成（L2标准链路）
                return self._ask_l2(question, conversation_id, full_context)
            else:  # 简单问题：直接检索+生成（L1简化链路）
                return self._ask_l1(question, conversation_id, full_context)

        except Exception as e:
            logger.error(f"[KnowledgeQAAgent] QA failed: {e}", exc_info=True)  # exc_info=True 记录完整的异常堆栈信息
            return {  # 返回错误响应
                "answer": "抱歉，处理您的问题时遇到了错误，请稍后再试。",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_qa",
                "error": True
            }

    def _ask_l1(self, question: str, conversation_id: Optional[str],
                full_context: str) -> Dict[str, Any]:
        """L1 简化链路：直接检索+生成"""
        # 直接向量检索
        docs = self.vector_store.search(  # 调用向量存储的语义检索方法
            query=question,
            k=self.top_k,
            similarity_threshold=self.similarity_threshold,
            use_rerank=self.use_rerank,
        )
        logger.info(f"[KnowledgeQAAgent] L1 retrieved {len(docs)} documents")  # 记录检索到的文档数

        if not docs:  # 如果没有检索到相关文档
            answer = self._insufficient_evidence_answer(question)
            self._save_to_memory(conversation_id, question, answer)  # 保存对话到记忆
            return {"answer": answer, "sources": [], "has_sources": False, "task_type": "knowledge_qa"}  # 返回结果字典

        sources = self._build_sources(docs)  # 构建引用来源列表
        if not self._sources_are_sufficient(sources):
            answer = self._insufficient_evidence_answer(question)
            self._save_to_memory(conversation_id, question, answer)
            return {"answer": answer, "sources": sources, "has_sources": False, "task_type": "knowledge_qa"}

        answer = self.llm_service.get_answer(question, docs, full_context)  # 基于检索到的文档和上下文生成回答
        self._save_to_memory(conversation_id, question, answer)  # 保存对话到记忆

        return {
            "answer": answer, "sources": sources,  # 回答和引用来源
            "has_sources": len(sources) > 0, "task_type": "knowledge_qa"  # len(sources) > 0 判断是否有来源
        }

    def _ask_l2(self, question: str, conversation_id: Optional[str],
                full_context: str) -> Dict[str, Any]:
        """L2 标准链路：问题改写+检索+重排序+生成"""
        retrieval_result = self.retrieval_agent.retrieve(  # 调用检索 Agent 执行完整检索流程
            query=question,  # 用户问题
            conversation_context=full_context,  # 对话上下文
            use_rewrite=True,  # 启用问题改写
            use_rerank=self.use_rerank,  # 启用重排序
            top_k=self.top_k,  # 返回前N个结果
            similarity_threshold=self.similarity_threshold,
        )

        docs = retrieval_result.reranked_documents  # 获取重排序后的文档列表
        logger.info(f"[KnowledgeQAAgent] L2 retrieved {len(docs)} documents "
                     f"(rewritten: '{retrieval_result.rewritten_query[:30]}...')")  # 记录改写后的查询

        if not docs:  # 如果没有检索到文档
            answer = self._insufficient_evidence_answer(question)
            self._save_to_memory(conversation_id, question, answer)
            return {"answer": answer, "sources": [], "has_sources": False, "task_type": "knowledge_qa"}

        citation_sources = retrieval_result.citations.get("sources", []) if retrieval_result.citations else []  # 获取引用来源（带条件判断）
        sources = citation_sources if citation_sources else self._build_sources(docs)  # 优先使用引用来源，否则手动构建
        if not self._sources_are_sufficient(sources):
            answer = self._insufficient_evidence_answer(question)
            self._save_to_memory(conversation_id, question, answer)
            return {"answer": answer, "sources": sources, "has_sources": False, "task_type": "knowledge_qa"}

        # 将检索结果转为 LLM 可用的文档格式
        llm_docs = []  # 初始化 LLM 文档列表
        for doc in docs:  # 遍历每个文档
            if hasattr(doc, 'page_content'):  # hasattr() 检查对象是否有指定属性（类似 Java 的反射检查字段是否存在）
                llm_docs.append(doc)  # 如果是 LangChain Document 对象，直接使用
            elif isinstance(doc, dict):  # isinstance() 检查对象是否为指定类型（类似 Java 的 instanceof）
                from langchain_core.documents import Document  # 导入 LangChain 的 Document 类
                llm_docs.append(Document(  # 将字典转换为 LangChain Document 对象
                    page_content=doc.get('content', ''),  # 文档内容
                    metadata=doc.get('metadata', {})  # 文档元数据
                ))

        answer = self.llm_service.get_answer(question, llm_docs, full_context)  # 基于文档和上下文生成回答
        self._save_to_memory(conversation_id, question, answer)  # 保存到记忆

        return {
            "answer": answer, "sources": sources,
            "has_sources": len(sources) > 0, "task_type": "knowledge_qa"
        }

    def _ask_l3(self, question: str, conversation_id: Optional[str],
                full_context: str) -> Dict[str, Any]:
        """L3 推理链路：分解子问题+逐个检索推理+汇总"""
        logger.info(f"[KnowledgeQAAgent] L3 reasoning for: {question[:50]}...")

        try:
            # 委托给 ReasoningAgent 执行分解→检索→推理→汇总
            result = self.reasoning_agent.reason(
                question, full_context, conversation_id
            )
            sources = result.get("sources", [])
            if not self._sources_are_sufficient(sources):
                answer = self._insufficient_evidence_answer(question)
                self._save_to_memory(conversation_id, question, answer)
                return {
                    "answer": answer,
                    "sources": sources,
                    "has_sources": False,
                    "task_type": "knowledge_qa"
                }
            self._save_to_memory(conversation_id, question, result.get("answer", ""))
            return {
                "answer": result.get("answer", ""),
                "sources": sources,
                "has_sources": len(sources) > 0,
                "task_type": "knowledge_qa"
            }
        except Exception as e:
            logger.error(f"[KnowledgeQAAgent] L3 reasoning failed, fallback to L2: {e}")
            return self._ask_l2(question, conversation_id, full_context)

    def _build_sources(self, docs: list) -> list:  # 构建引用来源列表
        """构建引用来源（按 doc_id 去重）"""
        seen_doc_ids = set()  # 创建已见文档ID集合（set 不允许重复元素，类似 Java 的 HashSet）
        sources = []  # 初始化来源列表
        for doc in docs:  # 遍历每个文档
            metadata = getattr(doc, 'metadata', {}) if hasattr(doc, 'metadata') else (  # getattr() 获取对象属性，第三个参数是默认值（类似 Java 的反射获取字段）
                doc.get('metadata', {}) if isinstance(doc, dict) else {}  # 如果是字典则用 .get() 取值，否则返回空字典
            )
            doc_id = metadata.get("doc_id")  # 获取文档ID
            source_label = (
                metadata.get("source")
                or metadata.get("file_name")
                or metadata.get("filename")
                or metadata.get("title")
            )
            if not (doc_id or source_label or metadata.get("page") is not None or metadata.get("chunk_index") is not None):
                continue
            if doc_id and doc_id in seen_doc_ids:  # 如果文档ID已存在，跳过（去重）
                continue  # continue 跳过当前循环迭代（类似 Java 的 continue）
            if doc_id:  # 如果有文档ID
                seen_doc_ids.add(doc_id)  # 将文档ID添加到已见集合
            sources.append({  # 添加来源信息
                "doc_id": doc_id,  # 文档ID
                "doc": source_label or "未知文档",  # 文档来源（默认为"未知文档"）
                "page": metadata.get("page"),  # 页码（可能为 None）
                "chunk_index": metadata.get("chunk_index"),  # 片段索引
                "score": metadata.get("score", getattr(doc, "score", 0))  # 相似度得分（默认为0）
            })
        return sources  # 返回去重后的来源列表

    def _sources_are_sufficient(self, sources: list) -> bool:
        if not self.strict_rag:
            return True
        meaningful_sources = [
            source for source in (sources or [])
            if any(source.get(key) for key in ("doc_id", "doc", "source", "title", "document_id", "content", "snippet"))
        ]
        return len(meaningful_sources) >= self.min_source_count

    def _insufficient_evidence_answer(self, question: str) -> str:
        return (
            "当前知识库中没有检索到足够可靠的资料来支持明确回答。"
            "为了降低误导风险，我不能基于猜测给出诊断、用药或治疗结论。\n\n"
            "建议补充：主要症状、持续时间、年龄、既往病史、正在使用的药物、检查结果和症状变化。"
            "如果出现胸痛、呼吸困难、意识改变、明显出血、高热不退或症状快速加重，请及时联系医生或就近就医。"
        )

    def _save_to_memory(self, conversation_id: str, question: str, answer: str):
        """保存对话到会话记忆"""
        if not conversation_id or not tool_registry.has_tool("conversation_memory_write"):  # 检查前提条件
            return  # 不满足则直接返回
        try:
            tool_registry.invoke_tool(  # 保存用户消息
                "conversation_memory_write",
                {"conversation_id": conversation_id, "role": "user", "content": question}
            )
            tool_registry.invoke_tool(  # 保存 AI 回复
                "conversation_memory_write",
                {"conversation_id": conversation_id, "role": "assistant", "content": answer}
            )
            logger.info(f"[KnowledgeQAAgent] Saved conversation to memory")
        except Exception as e:
            logger.warning(f"[KnowledgeQAAgent] Failed to write conversation memory: {e}")

    def _format_history(self, messages: list) -> str:
        """格式化对话历史为上下文字符串"""
        if not messages:  # 如果消息列表为空
            return ""  # 返回空字符串

        formatted = []  # 初始化格式化后的消息列表
        for msg in messages:  # 遍历每条消息
            role = msg.get("role", "unknown")  # 获取角色
            content = msg.get("content", "")  # 获取内容
            if role == "system":  # 系统消息
                formatted.append(content)
            elif role == "user":  # 用户消息
                formatted.append(f"用户: {content}")
            elif role == "assistant":  # AI 消息
                formatted.append(f"AI: {content}")

        return "\n".join(formatted)  # 用换行符连接成字符串

    def ask_stream(self, question: str, conversation_id: Optional[str] = None,
                   user_id: Optional[str] = None, context: str = "",
                   **kwargs) -> Generator[str, None, None]:  # 返回生成器
        """
        流式处理知识问答 - 精简RAG链路

        直接走：向量检索 → LLM流式生成 → 返回
        """
        logger.info(f"[KnowledgeQAAgent] Stream processing question: {question[:50]}...")

        try:
            # 1. 直接向量检索
            docs = self.vector_store.search(  # 执行向量检索
                query=question,
                k=self.top_k,
                similarity_threshold=self.similarity_threshold,
                use_rerank=self.use_rerank,
            )

            logger.info(f"[KnowledgeQAAgent] Retrieved {len(docs)} documents")

            # 2. 构建引用来源（按 doc_id 去重）
            sources = self._build_sources(docs)
            if not self._sources_are_sufficient(sources):
                answer = self._insufficient_evidence_answer(question)
                self._save_to_memory(conversation_id, question, answer)
                yield json.dumps({"type": "start", "content": ""}, ensure_ascii=False)
                yield json.dumps({"type": "token", "content": answer}, ensure_ascii=False)
                yield json.dumps({"type": "sources", "sources": sources, "task_type": "knowledge_qa"}, ensure_ascii=False)
                yield json.dumps({"type": "end", "content": answer, "task_type": "knowledge_qa"}, ensure_ascii=False)
                return

            # 3. 流式 LLM 生成
            for chunk in self.llm_service.get_answer_stream(  # 遍历 LLM 流式生成的每个文本块
                question=question,
                context_docs=docs,
                conversation_context=context
            ):
                yield chunk  # 逐个产出 LLM 生成的文本块

            # 4. 发送来源信息
            yield json.dumps({  # 产出来源信息事件
                "type": "sources",  # 事件类型：来源
                "sources": sources,  # 引用来源列表
                "task_type": "knowledge_qa"  # 任务类型
            })

        except Exception as e:
            logger.error(f"[KnowledgeQAAgent] Stream QA failed: {e}", exc_info=True)
            yield json.dumps({  # 产出错误事件
                "type": "error",
                "content": "处理问题时遇到错误，请稍后再试。"
            })

    def _ask_with_orchestrator(self, question: str, conversation_id: Optional[str] = None,
                               user_id: Optional[str] = None, context: str = "",
                               **kwargs) -> Dict[str, Any]:
        """
        使用原有的Orchestrator方式进行知识问答（回退方案）
        """
        logger.info(f"[KnowledgeQAAgent] Using orchestrator fallback...")  # 记录使用回退方案
        result = self.orchestrator.run(  # 调用编排器运行
            input_text=question,
            conversation_id=conversation_id,
            user_id=user_id,
            context=context,
            goal=f"回答知识问题: {question[:50]}...",  # 设置目标描述
            **kwargs
        )
        return result  # 返回编排器执行结果

    def _ask_stream_with_orchestrator(self, question: str, conversation_id: Optional[str] = None,
                                      user_id: Optional[str] = None, context: str = "",
                                      **kwargs) -> Generator[str, None, None]:
        """
        使用原有的Orchestrator方式进行流式知识问答（回退方案）
        """
        logger.info(f"[KnowledgeQAAgent] Using orchestrator stream fallback...")
        for event in self.orchestrator.run_stream(  # 遍历编排器的流式输出
            input_text=question,
            conversation_id=conversation_id,
            user_id=user_id,
            context=context,
            goal=f"流式回答知识问题: {question[:50]}...",
            **kwargs
        ):
            yield event  # 逐个产出事件

    def register_callback(self, event_type: str, callback):
        """注册事件回调"""  # 注册事件回调（类似 Java 的 addEventListener）
        self.event_bus.subscribe(event_type, callback)  # 订阅指定类型的事件

    def unregister_callback(self, event_type: str, callback):
        """取消事件回调"""  # 取消事件回调（类似 Java 的 removeEventListener）
        self.event_bus.unsubscribe(event_type, callback)  # 取消订阅指定类型的事件
