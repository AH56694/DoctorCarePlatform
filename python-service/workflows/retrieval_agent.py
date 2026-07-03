from typing import Dict, Any, Optional, Generator, List  # 导入类型提示：Dict 字典，Any 任意类型，Optional 可为 None，Generator 生成器，List 列表
from tools.question_rewrite import QuestionRewriteTool  # 导入问题改写工具
from tools.registry import tool_registry  # 导入全局工具注册表（通过 invoke_tool 调用才有完整的追踪、超时、重试能力）
from tools.knowledge_search import KnowledgeSearchTool  # 导入知识搜索工具（仅用于类型引用）
from tools.rerank import RerankTool  # 导入重排序工具
from tools.citation import CitationIntegrator, CitationTracker  # 导入引用整合器和引用追踪器
from core.vector_store import vector_store  # 导入全局向量存储实例
from core.config import config  # 导入全局配置实例
import logging  # 导入日志模块
import json  # 导入 JSON 模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class RetrievalResult:  # 定义检索结果封装类（类似 Java 的 POJO/DTO）
    """检索结果封装"""

    def __init__(  # 构造函数
        self,
        original_query: str,  # 原始查询字符串
        rewritten_query: Optional[str] = None,  # 改写后的查询（可选，默认 None）
        retrieved_documents: Optional[List] = None,  # 检索到的文档列表（可选）
        reranked_documents: Optional[List] = None,  # 重排序后的文档列表（可选）
        scores: Optional[List[float]] = None,  # 文档得分列表（可选）
        citations: Optional[Dict[str, Any]] = None,  # 引用信息字典（可选）
        success: bool = True,  # 是否成功（默认 True）
        error: Optional[str] = None  # 错误信息（可选）
    ):
        self.original_query = original_query  # 保存原始查询
        self.rewritten_query = rewritten_query or original_query  # or 运算符：左侧为 None/空时使用右侧值（类似 Java 的 Optional.orElse()）
        self.retrieved_documents = retrieved_documents or []  # 检索文档列表，为 None 时使用空列表
        self.reranked_documents = reranked_documents or []  # 重排序文档列表
        self.scores = scores or []  # 得分列表
        self.citations = citations or {}  # 引用信息字典
        self.success = success  # 成功标志
        self.error = error  # 错误信息

    def to_dict(self) -> Dict[str, Any]:  # 将对象转为字典（类似 Java 的 toMap() 方法）
        return {  # 返回包含所有字段的字典
            "original_query": self.original_query,  # 原始查询
            "rewritten_query": self.rewritten_query,  # 改写查询
            "retrieved_documents": self.retrieved_documents,  # 检索文档
            "reranked_documents": self.reranked_documents,  # 重排序文档
            "scores": self.scores,  # 得分
            "citations": self.citations,  # 引用
            "success": self.success,  # 成功标志
            "error": self.error  # 错误信息
        }


class RetrievalAgent:  # 定义检索 Agent 类
    """Retrieval Agent - 负责检索全流程：query rewrite -> recall -> rerank -> citation integration"""

    def __init__(self):  # 构造函数
        self.question_rewrite_tool = QuestionRewriteTool()  # 初始化问题改写工具（直接调用，用于内部改写逻辑）
        self.rerank_tool = RerankTool()  # 初始化重排序工具
        self.citation_integrator = CitationIntegrator()  # 初始化引用整合器
        self.citation_tracker = CitationTracker()  # 初始化引用追踪器
        self.vector_store = vector_store  # 引用全局向量存储（作为工具调用的回退方案）

        self.config = {  # 检索配置字典
            "top_k": 5,  # 最终返回的文档数量
            "initial_k": 10,  # 初始检索的文档数量
            "similarity_threshold": 0.5,  # 余弦相似度阈值（0~1，越大越相似）
            "use_rerank": False,   # 默认关闭重排序，减少开销
            "use_rewrite": False,  # 默认关闭问题重写，减少LLM调用
            "max_citations": 5  # 最大引用数量
        }

    def retrieve(  # 检索主方法
        self,
        query: str,  # 用户查询
        conversation_context: str = "",  # 对话上下文
        use_rewrite: bool = False,  # 是否启用问题改写
        use_rerank: bool = False,  # 是否启用重排序
        top_k: int = 5,  # 返回结果数量
        similarity_threshold: float = 0.5,  # 余弦相似度阈值（0~1，越大越相似）
        **kwargs  # 其他关键字参数
    ) -> RetrievalResult:  # 返回检索结果对象
        """
        执行完整检索流程

        Args:
            query: 用户问题
            conversation_context: 对话上下文
            use_rewrite: 是否使用问题改写
            use_rerank: 是否使用重排序
            top_k: 返回结果数量
            similarity_threshold: 余弦相似度阈值（0~1，越大越相似）

        Returns:
            RetrievalResult: 检索结果
        """
        logger.info(f"[RetrievalAgent] Starting retrieval for: {query[:50]}...")

        original_query = query  # 保存原始查询
        rewritten_query = query  # 初始化改写查询为原始查询

        try:
            # 问题改写的提示词有问题 不能直接让大模型回答 会产生幻觉
            if use_rewrite:  # 如果启用问题改写
                # 调用问题改写工具
                rewrite_result = tool_registry.invoke_tool("question_rewrite_tool", {  # 调用问题改写工具
                    "question": query,  # 原始问题
                    "conversation_context": conversation_context  # 对话上下文
                })
                rewritten_query = rewrite_result.get("rewritten_question", query)  # 获取改写后的问题，失败则使用原问题
                logger.info(f"[RetrievalAgent] Query rewritten: '{query}' -> '{rewritten_query}'")  # 记录改写日志

            retrieved_docs = self._retrieve_documents(  # 调用内部文档检索方法
                rewritten_query,  # 使用改写后的查询
                k=top_k * 3 if use_rerank else top_k,  # 三元表达式：如果启用重排序则多检索一些（3倍），否则检索 top_k 个
                similarity_threshold=similarity_threshold
            )

            if use_rerank and retrieved_docs:  # 如果启用重排序且有检索结果
                reranked_result = self._rerank_documents(  # 调用重排序方法
                    rewritten_query,
                    retrieved_docs,
                    top_k=top_k
                )
                reranked_docs = reranked_result.get("reranked_documents", retrieved_docs)  # 获取重排序后的文档
                scores = reranked_result.get("scores", [])  # 获取排序得分
            else:  # 不使用重排序
                reranked_docs = retrieved_docs[:top_k]  # 列表切片：取前 top_k 个元素（类似 Java 的 list.subList(0, top_k)）
                scores = [0.5] * len(reranked_docs)  # [0.5] * n 将列表重复 n 次（如 [0.5] * 3 = [0.5, 0.5, 0.5]）

            citation_result = self.citation_integrator.integrate(  # 整合引用信息
                answer="",  # 暂无答案（先做引用分析）
                documents=reranked_docs,  # 重排序后的文档
                scores=scores,  # 得分
                query=query  # 原始查询
            )

            result = RetrievalResult(  # 创建检索结果对象
                original_query=original_query,
                rewritten_query=rewritten_query,
                retrieved_documents=retrieved_docs,
                reranked_documents=reranked_docs,
                scores=scores,
                citations=citation_result,
                success=True
            )

            logger.info(  # 记录检索完成日志
                f"[RetrievalAgent] Retrieval completed: "
                f"original='{original_query[:30]}...', "
                f"rewritten='{rewritten_query[:30]}...', "
                f"retrieved={len(retrieved_docs)}, "
                f"reranked={len(reranked_docs)}"
            )

            return result  # 返回检索结果

        except Exception as e:
            logger.error(f"[RetrievalAgent] Retrieval failed: {e}")
            return RetrievalResult(  # 返回失败的检索结果
                original_query=original_query,
                success=False,  # 标记失败
                error=str(e)  # 错误信息
            )

    def retrieve_stream(  # 流式检索方法
        self,
        query: str,
        conversation_context: str = "",
        use_rewrite: bool = False,
        use_rerank: bool = False,
        top_k: int = 5,
        similarity_threshold: float = 0.5,  # 余弦相似度阈值（0~1，越大越相似）
        **kwargs
    ) -> Generator[str, None, None]:  # 返回字符串生成器
        """
        流式执行检索流程

        Yields:
            JSON格式的事件流
        """
        logger.info(f"[RetrievalAgent] Stream retrieval for: {query[:50]}...")

        original_query = query  # 保存原始查询
        rewritten_query = query  # 初始化改写查询

        try:
            yield json.dumps({  # 产出检索开始事件
                "type": "retrieval_started",  # 事件类型
                "query": original_query
            })

            if use_rewrite:  # 如果启用问题改写
                yield json.dumps({  # 产出改写步骤开始事件
                    "type": "step",
                    "step_name": "question_rewrite",  # 步骤名称
                    "status": "started"  # 状态：已开始
                })

                rewrite_result = self.question_rewrite_tool.execute({  # 执行问题改写
                    "question": query,
                    "conversation_context": conversation_context
                })
                rewritten_query = rewrite_result.get("rewritten_question", query)  # 获取改写结果

                yield json.dumps({  # 产出改写步骤完成事件
                    "type": "step",
                    "step_name": "question_rewrite",
                    "status": "completed",
                    "output": {
                        "original_query": original_query,
                        "rewritten_query": rewritten_query
                    }
                })

            yield json.dumps({  # 产出知识搜索步骤开始事件
                "type": "step",
                "step_name": "knowledge_search",
                "status": "started"
            })

            retrieved_docs = self._retrieve_documents(  # 执行文档检索
                rewritten_query,
                k=top_k * 3 if use_rerank else top_k,
                similarity_threshold=similarity_threshold
            )

            yield json.dumps({  # 产出知识搜索步骤完成事件
                "type": "step",
                "step_name": "knowledge_search",
                "status": "completed",
                "output": {
                    "retrieved_count": len(retrieved_docs)
                }
            })

            if use_rerank and retrieved_docs:  # 如果启用重排序
                yield json.dumps({  # 产出重排序步骤开始事件
                    "type": "step",
                    "step_name": "rerank",
                    "status": "started"
                })

                reranked_result = self._rerank_documents(  # 执行重排序
                    rewritten_query,
                    retrieved_docs,
                    top_k=top_k
                )
                reranked_docs = reranked_result.get("reranked_documents", retrieved_docs)
                scores = reranked_result.get("scores", [])

                yield json.dumps({  # 产出重排序步骤完成事件
                    "type": "step",
                    "step_name": "rerank",
                    "status": "completed",
                    "output": {
                        "reranked_count": len(reranked_docs),
                        "top_scores": scores[:3] if scores else []  # 取前3个得分
                    }
                })
            else:  # 不使用重排序
                reranked_docs = retrieved_docs[:top_k]  # 截取前 top_k 个
                scores = [0.5] * len(reranked_docs)  # 默认得分

            yield json.dumps({  # 产出检索完成事件
                "type": "retrieval_completed",
                "output": {
                    "original_query": original_query,
                    "rewritten_query": rewritten_query,
                    "retrieved_count": len(retrieved_docs),
                    "final_count": len(reranked_docs),
                    "documents": reranked_docs,
                    "scores": scores
                }
            })

        except Exception as e:
            logger.error(f"[RetrievalAgent] Stream retrieval failed: {e}")
            yield json.dumps({  # 产出错误事件
                "type": "error",
                "error": str(e)
            })

    def _retrieve_documents(  # 内部文档检索方法
        self,
        query: str,
        k: int = 10,
        similarity_threshold: float = 0.5  # 余弦相似度阈值（0~1，越大越相似）
    ) -> List:  # 返回列表类型
        """执行文档检索"""
        try:
            if tool_registry.has_tool("knowledge_search"):  # 如果工具已注册
                result = tool_registry.invoke_tool(  # 通过工具注册表调用（有追踪、超时、重试）
                    "knowledge_search",  # 工具名称
                    {  # 调用参数
                        "query": query,
                        "top_k": k,
                        "similarity_threshold": similarity_threshold,
                        "use_rerank": False
                    }
                )
                return result.get("documents", [])  # 返回搜索结果中的文档列表
        except Exception as e:
            logger.warning(f"[RetrievalAgent] knowledge_search tool failed: {e}")

        # 回退方案：工具未注册或调用失败时，直接使用全局向量存储
        docs = self.vector_store.search(
            query=query,
            k=k,
            similarity_threshold=similarity_threshold,
            use_rerank=False
        )

        return [  # 列表推导式（类似 Java 的 stream().map().collect()）：遍历 docs 并对每个元素做转换
            {
                "content": getattr(doc, "page_content", str(doc)),  # getattr() 安全获取属性，不存在则转为字符串
                "metadata": getattr(doc, "metadata", {}),  # 获取元数据
                "score": getattr(doc, "score", 0.5)  # 获取得分
            }
            for doc in docs  # 遍历每个文档
        ]

    def _rerank_documents(  # 内部重排序方法
        self,
        query: str,
        documents: List,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """执行文档重排序"""
        try:
            return self.rerank_tool.execute({  # 调用重排序工具
                "query": query,
                "documents": documents,
                "top_k": top_k
            })
        except Exception as e:
            logger.warning(f"[RetrievalAgent] rerank failed: {e}")
            return {  # 重排序失败时返回原始文档的前 top_k 个
                "reranked_documents": documents[:top_k],  # 截取前 top_k 个
                "scores": [0.5] * min(top_k, len(documents)),  # min() 取较小值，避免列表越界
                "original_indices": list(range(min(top_k, len(documents)))),  # range() 生成整数序列，list() 转为列表
                "count": min(top_k, len(documents))
            }

    def integrate_citations(  # 整合引用到答案
        self,
        answer: str,
        documents: List[Dict[str, Any]],  # 文档列表（字典类型）
        scores: Optional[List[float]] = None,
        query: str = ""
    ) -> Dict[str, Any]:
        """整合引用到答案"""
        return self.citation_integrator.integrate(  # 委托给引用整合器
            answer=answer,
            documents=documents,
            scores=scores,
            query=query
        )

    def track_retrieval(  # 追踪检索链路
        self,
        query: str,
        rewritten_query: str,
        retrieved_docs: List[Dict[str, Any]],
        reranked_docs: List[Dict[str, Any]],
        final_answer: str
    ) -> Dict[str, Any]:
        """追踪检索链路"""
        return self.citation_tracker.track(  # 委托给引用追踪器
            query=query,
            rewritten_query=rewritten_query,
            retrieved_docs=retrieved_docs,
            reranked_docs=reranked_docs,
            final_answer=final_answer
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取检索统计信息"""
        return {
            "config": self.config,  # 当前配置
            "citation_stats": self.citation_tracker.get_citation_stats()  # 引用统计信息
        }


retrieval_agent = RetrievalAgent()  # 创建全局的检索 Agent 实例（模块级单例，类似 Java 的 static final 实例）