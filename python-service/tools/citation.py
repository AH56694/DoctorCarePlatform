from typing import Dict, Any, List, Optional, Tuple  # 导入类型注解：Dict=字典，Any=任意类型，List=列表，Optional=可选类型，Tuple=元组类型（类似 Java 的泛型 Tuple）
from dataclasses import dataclass  # 导入数据类装饰器（@dataclass 类似 Java 的 Lombok @Data）
from core.config import config  # 导入全局配置单例


@dataclass  # 数据类装饰器，自动生成 __init__、__repr__、__eq__ 等方法
class Citation:  # 引用信息数据类，记录一条文档引用的完整信息
    """引用信息"""
    document_id: str  # 文档 ID
    chunk_id: Optional[int]  # 文档分块 ID，Optional[int] 表示可以是 int 或 None（类似 Java 的 Integer，可为 null）
    content: str  # 引用的文档内容
    score: float  # 相关性分数
    doc_title: Optional[str] = None  # 文档标题，默认 None（类似 Java 的 String field = null）
    doc_category: Optional[str] = None  # 文档分类，默认 None
    position: int = 0  # 引用在文档列表中的位置，默认0


class CitationIntegrator:  # 引用整合器，负责将检索结果与生成的答案进行引用关联
    """引用整合器 - 负责整合检索结果与生成答案的引用"""

    def __init__(self):  # 构造函数
        self.min_citation_score = 0.3  # 最小引用分数阈值，低于此分数的文档不作为引用
        self.max_citations = 5  # 最大引用数量

    def integrate(  # 整合答案与引用的主方法
        self,
        answer: str,  # 生成的回答文本
        documents: List[Dict[str, Any]],  # 检索到的文档列表
        scores: Optional[List[float]] = None,  # 各文档的相关性分数，可选
        query: str = ""  # 原始查询文本，默认空字符串
    ) -> Dict[str, Any]:  # 返回包含答案和引用信息的字典
        """
        整合答案与引用

        Args:
            answer: 生成的回答
            documents: 检索到的文档列表
            scores: 各文档的相关性分数
            query: 原始查询（用于引用匹配）

        Returns:
            包含答案和引用信息的字典
        """
        if not documents:  # 如果文档列表为空（空列表是 falsy 值）
            return {  # 返回无引用的结果
                "answer": answer,  # 原始答案
                "sources": [],  # 空引用来源列表
                "has_sources": False,  # 无引用来源
                "citation_count": 0  # 引用数量为0
            }

        citations = self._extract_citations(documents, scores, query)  # 从文档中提取引用信息
        formatted_sources = self._format_sources(citations)  # 格式化引用来源

        return {  # 返回整合结果
            "answer": answer,  # 原始答案
            "sources": formatted_sources,  # 格式化后的引用来源列表
            "has_sources": len(citations) > 0,  # 是否有引用来源
            "citation_count": len(citations)  # 引用数量
        }

    def _extract_citations(  # 私有方法，从文档列表中提取符合条件的引用信息
        self,
        documents: List[Dict[str, Any]],  # 文档列表
        scores: Optional[List[float]],  # 分数列表，可选
        query: str  # 查询文本
    ) -> List[Citation]:  # 返回 Citation 对象列表
        """从文档中提取引用信息"""
        citations = []  # 初始化引用列表
        seen_contents = set()  # 已见内容的哈希集合，用于去重（set 类似 Java 的 HashSet）

        for i, doc in enumerate(documents):  # enumerate 同时获取索引和元素（类似 Java 的 for 循环带索引）
            if i < len(documents):  # 防止索引越界
                doc_data = documents[i] if isinstance(documents[i], dict) else {"content": getattr(documents[i], "page_content", str(documents[i])), "metadata": getattr(documents[i], "metadata", {})}  # 如果是字典直接使用，否则从对象属性中提取（getattr 类似 Java 的反射获取属性）

                content = doc_data.get("content", "")  # 获取文档内容，默认空字符串
                if not content:  # 内容为空则跳过
                    continue  # 跳过当前循环迭代（类似 Java 的 continue）

                content_hash = hash(content[:100])  # 取前100个字符计算哈希值（hash 类似 Java 的 Object.hashCode()）
                if content_hash in seen_contents and len(seen_contents) > 0:  # 如果哈希值已存在（内容重复）
                    continue  # 跳过重复内容
                seen_contents.add(content_hash)  # 将哈希值加入已见集合

                score = scores[i] if scores and i < len(scores) else doc_data.get("score", 0.5)  # 优先使用传入的分数，否则取文档自带的分数，默认0.5

                if score < self.min_citation_score:  # 分数低于阈值则跳过
                    continue  # 跳过

                metadata = doc_data.get("metadata", {})  # 获取文档元数据
                citation = Citation(  # 创建 Citation 引用对象
                    document_id=metadata.get("doc_id", metadata.get("doc_id", f"doc_{i}")),  # 获取文档 ID，带多级默认值
                    chunk_id=metadata.get("chunk_id"),  # 获取分块 ID
                    content=self._truncate_content(content),  # 截断过长的内容
                    score=score,  # 相关性分数
                    doc_title=metadata.get("doc_title", metadata.get("title")),  # 获取文档标题
                    doc_category=metadata.get("category"),  # 获取文档分类
                    position=i  # 文档位置索引
                )
                citations.append(citation)  # 添加到引用列表

            if len(citations) >= self.max_citations:  # 已达到最大引用数量
                break  # 跳出循环（类似 Java 的 break）

        return citations  # 返回引用列表

    def _truncate_content(self, content: str, max_length: int = 200) -> str:  # 截断过长的内容
        """截断内容"""
        if len(content) <= max_length:  # 如果内容不超过最大长度
            return content  # 原样返回
        return content[:max_length] + "..."  # 截断并添加省略号（[:n] 切片类似 Java 的 substring(0, n)）

    def _format_sources(self, citations: List[Citation]) -> List[Dict[str, Any]]:  # 格式化引用来源为字典列表
        """格式化引用来源"""
        sources = []  # 初始化来源列表
        for i, citation in enumerate(citations):  # 遍历引用列表，enumerate 同时获取索引
            source = {  # 构建引用来源字典
                "index": i + 1,  # 引用序号（从1开始）
                "document_id": citation.document_id,  # 文档 ID
                "chunk_id": citation.chunk_id,  # 分块 ID
                "content": citation.content,  # 引用内容
                "score": round(citation.score, 4),  # 分数保留4位小数（round 类似 Java 的 Math.round 精确版）
                "title": citation.doc_title or f"文档{citation.document_id}",  # or 运算符提供默认值（类似 Java 的 Optional.orElse()）
                "category": citation.doc_category or "未分类"  # 分类为空时默认"未分类"
            }
            sources.append(source)  # 添加到来源列表
        return sources  # 返回格式化后的来源列表

    def extract_citations_from_text(  # 从文本中提取被引用的内容片段
        self,
        text: str,  # 生成的回答文本
        documents: List[Dict[str, Any]]  # 检索到的文档列表
    ) -> List[Dict[str, Any]]:  # 返回被引用的文档列表
        """
        从文本中提取被引用的内容片段

        Args:
            text: 生成的回答文本
            documents: 检索到的文档列表

        Returns:
            被引用的文档列表
        """
        cited_docs = []  # 初始化被引用文档列表

        for doc in documents:  # 遍历所有文档
            doc_content = doc.get("content", "")  # 获取文档内容
            if not doc_content:  # 内容为空则跳过
                continue  # 跳过

            if doc_content[:50] in text or any(sent in text for sent in self._split_sentences(doc_content)[:3]):  # 检查文档前50字符是否在回答中，或前3句话是否有匹配（any 类似 Java 的 stream().anyMatch()）
                cited_docs.append({  # 添加到被引用文档列表
                    "document_id": doc.get("metadata", {}).get("doc_id", "unknown"),  # 获取文档 ID
                    "content": doc_content,  # 文档内容
                    "metadata": doc.get("metadata", {})  # 文档元数据
                })

        return cited_docs  # 返回被引用文档列表

    def _split_sentences(self, text: str) -> List[str]:  # 简单的中文分句方法
        """简单分句"""
        import re  # 延迟导入正则表达式模块（仅在需要时导入）
        sentences = re.split(r'[。！？\n]', text)  # 按中文句号、感叹号、问号和换行符分割文本
        return [s.strip() for s in sentences if s.strip()]  # 列表推导式：去除空白并过滤空字符串

    def create_citation_reference(  # 创建完整的引用参考
        self,
        question: str,  # 用户问题
        answer: str,  # 生成的回答
        documents: List[Dict[str, Any]],  # 检索到的文档列表
        scores: Optional[List[float]] = None  # 相关性分数，可选
    ) -> Dict[str, Any]:  # 返回完整的引用参考字典
        """
        创建完整的引用参考

        Args:
            question: 用户问题
            answer: 生成的回答
            documents: 检索到的文档
            scores: 相关性分数

        Returns:
            包含问题和答案的完整引用信息
        """
        result = self.integrate(answer, documents, scores, question)  # 调用 integrate 方法获取基础引用结果

        result["question"] = question  # 添加问题字段
        result["retrieved_docs_count"] = len(documents)  # 添加检索到的文档总数
        result["cited_docs_count"] = len(result["sources"])  # 添加被引用的文档数量

        return result  # 返回完整的引用参考


class CitationTracker:  # 引用追踪器类，追踪答案中引用的来源链路
    """引用追踪器 - 追踪答案中引用的来源"""

    def __init__(self):  # 构造函数
        self.tracked_citations: List[Dict[str, Any]] = []  # 已追踪的引用记录列表（类型注解标注为 List<Dict<String, Object>>）

    def track(  # 追踪完整的检索和引用链路
        self,
        query: str,  # 原始问题
        rewritten_query: str,  # 改写后的问题
        retrieved_docs: List[Dict[str, Any]],  # 检索到的文档
        reranked_docs: List[Dict[str, Any]],  # 重排后的文档
        final_answer: str  # 最终答案
    ) -> Dict[str, Any]:  # 返回追踪信息字典
        """
        追踪完整的检索和引用链路

        Args:
            query: 原始问题
            rewritten_query: 改写后的问题
            retrieved_docs: 检索到的文档
            reranked_docs: 重排后的文档
            final_answer: 最终答案

        Returns:
            追踪信息
        """
        integrator = CitationIntegrator()  # 创建引用整合器实例

        return {  # 返回追踪信息字典
            "query": {  # 查询信息
                "original": query,  # 原始问题
                "rewritten": rewritten_query  # 改写后的问题
            },
            "retrieval": {  # 检索信息
                "initial_count": len(retrieved_docs),  # 初始检索文档数
                "reranked_count": len(reranked_docs),  # 重排后文档数
                "top_scores": [doc.get("score", 0) for doc in reranked_docs[:3]] if reranked_docs else []  # 取重排后前3个文档的分数
            },
            "citation": integrator.create_citation_reference(  # 引用参考信息
                question=query,  # 原始问题
                answer=final_answer,  # 最终答案
                documents=reranked_docs  # 使用重排后的文档
            ),
            "answer_length": len(final_answer)  # 答案长度
        }

    def get_citation_stats(self) -> Dict[str, Any]:  # 获取引用统计信息
        """获取引用统计信息"""
        if not self.tracked_citations:  # 如果没有追踪记录（空列表是 falsy 值）
            return {  # 返回零值统计
                "total_queries": 0,  # 总查询数为0
                "avg_citations": 0,  # 平均引用数为0
                "avg_answer_length": 0  # 平均答案长度为0
            }

        total_citations = sum(c.get("citation_count", 0) for c in self.tracked_citations)  # 计算总引用数（sum + 生成器表达式，类似 Java 的 stream().mapToInt().sum()）
        total_length = sum(c.get("answer_length", 0) for c in self.tracked_citations)  # 计算总答案长度

        return {  # 返回统计信息字典
            "total_queries": len(self.tracked_citations),  # 总查询数
            "total_citations": total_citations,  # 总引用数
            "avg_citations": round(total_citations / len(self.tracked_citations), 2),  # 平均引用数，保留2位小数
            "avg_answer_length": round(total_length / len(self.tracked_citations), 2)  # 平均答案长度，保留2位小数
        }