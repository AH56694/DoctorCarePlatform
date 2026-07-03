from typing import Dict, Any, Optional, Generator, List  # 导入类型提示：Dict 字典，Any 任意类型，Optional 可为 None，Generator 生成器，List 列表
from core.mysql_client import mysql_client  # 导入 MySQL 客户端实例
import logging  # 导入日志模块
import json  # 导入 JSON 模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class InspectionAgent:  # 定义知识巡检 Agent 类
    """知识巡检Agent - 专门处理知识库质量检查的工作流"""

    def __init__(self):  # 构造函数
        self.inspection_types = {  # 巡检类型映射字典
            "duplicate": "重复文档检测",  # 重复文档
            "low_quality": "低质量片段检测",  # 低质量片段
            "stale": "过期知识检测",  # 过期知识
            "unpopular": "无人访问文档检测",  # 无人访问文档
        }

    def inspect(self, inspection_type: str, conversation_id: Optional[str] = None,  # inspect 方法：执行知识巡检
               user_id: Optional[str] = None, context: str = "",
               **kwargs) -> Dict[str, Any]:
        """
        执行知识巡检

        Args:
            inspection_type: 巡检类型 (duplicate/low_quality/stale/unpopular)
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            **kwargs: 其他参数

        Returns:
            包含巡检结果的字典
        """
        logger.info(f"[InspectionAgent] Processing inspection: {inspection_type}")

        try:
            if inspection_type == "duplicate":  # 重复文档检测
                return self._check_duplicate_docs()

            elif inspection_type == "low_quality":  # 低质量片段检测
                return self._check_low_quality_chunks()

            elif inspection_type == "stale":  # 过期知识检测
                return self._check_stale_knowledge()

            elif inspection_type == "unpopular":  # 无人访问文档检测
                return self._check_unpopular_docs()

            else:  # 其他类型执行完整巡检
                return self._run_full_inspection()

        except Exception as e:
            logger.error(f"[InspectionAgent] Inspection error: {str(e)}")
            return {  # 返回错误响应
                "answer": f"执行巡检时出错：{str(e)}",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "error": True
            }

    def inspect_stream(self, inspection_type: str, conversation_id: Optional[str] = None,  # 流式巡检方法
                      user_id: Optional[str] = None, context: str = "",
                      **kwargs) -> Generator[str, None, None]:  # 返回 JSON 事件生成器
        """
        流式执行知识巡检

        Args:
            inspection_type: 巡检类型
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            **kwargs: 其他参数

        Yields:
            JSON格式的事件流
        """
        logger.info(f"[InspectionAgent] Stream inspection: {inspection_type}")

        try:
            result = self.inspect(inspection_type, conversation_id, user_id, context, **kwargs)  # 先执行同步巡检获取完整结果
            answer = result.get("answer", "")  # 获取答案文本

            yield json.dumps({  # 产出巡检开始事件
                "type": "inspection_started",  # 事件类型
                "inspection_type": inspection_type  # 巡检类型
            })

            for char in answer:  # 逐字符遍历答案（模拟流式输出）
                yield json.dumps({
                    "type": "token",  # 事件类型：文本 token
                    "content": char  # 单个字符
                })

            yield json.dumps({  # 产出结束事件
                "type": "end",
                "content": result  # 携带完整巡检结果
            })
        except Exception as e:
            logger.error(f"[InspectionAgent] Stream error: {str(e)}")
            yield json.dumps({  # 产出错误事件
                "type": "error",
                "content": str(e)
            })

    def _check_duplicate_docs(self) -> Dict[str, Any]:  # 检测重复文档
        """检测重复文档"""
        try:
            # 查询可能有重复的文档（相同标题或相似内容）
            query = """  # SQL 查询语句：通过自连接查找标题相同的文档对
                SELECT d1.id as doc1_id, d1.title as doc1_title,
                       d2.id as doc2_id, d2.title as doc2_title,
                       d1.created_at
                FROM knowledge_docs d1
                JOIN knowledge_docs d2 ON d1.title = d2.title AND d1.id < d2.id  # JOIN 自连接：查找标题相同但ID不同的文档对
                WHERE d1.is_deleted = 0 AND d2.is_deleted = 0  # 排除已删除的文档
                LIMIT 20  # 最多返回20条
            """
            duplicates = mysql_client.fetch_all(query) or []  # fetch_all 返回所有匹配行的列表

            if not duplicates:  # 如果没有重复文档
                return {
                    "answer": "✅ 重复文档检测完成\n\n未发现明显的重复文档，知识库文档唯一性良好。",
                    "sources": [],
                    "has_sources": False,
                    "task_type": "knowledge_inspection",
                    "inspection_type": "duplicate",
                    "data": {"duplicates": [], "count": 0}
                }

            duplicate_list = []  # 初始化重复文档列表
            for dup in duplicates:  # 遍历每个重复文档对
                duplicate_list.append({  # 添加到列表
                    "doc1_id": dup.get("doc1_id"),  # 第一个文档ID
                    "doc1_title": dup.get("doc1_title"),  # 第一个文档标题
                    "doc2_id": dup.get("doc2_id"),  # 第二个文档ID
                    "doc2_title": dup.get("doc2_title"),  # 第二个文档标题
                })

            answer = f"""⚠️ 发现 {len(duplicates)} 对可能重复的文档：

"""
            for i, dup in enumerate(duplicate_list[:5], 1):  # enumerate() 返回索引和值的元组（类似 Java 的 for-each 带索引），第二个参数指定起始索引
                answer += f"{i}. 《{dup['doc1_title']}》 与 《{dup['doc2_title']}》\n"  # += 字符串拼接（类似 Java 的 StringBuilder.append）

            if len(duplicate_list) > 5:  # 如果超过5对
                answer += f"\n... 还有 {len(duplicate_list) - 5} 对重复文档未显示"  # 提示还有更多

            answer += "\n\n建议：请管理员核实这些文档是否真的重复，决定是否合并或删除。"  # 添加建议

            return {
                "answer": answer,
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "duplicate",
                "data": {"duplicates": duplicate_list, "count": len(duplicate_list)}
            }
        except Exception as e:
            logger.error(f"[InspectionAgent] Duplicate check error: {str(e)}")
            return {
                "answer": "重复文档检测失败，请稍后重试。",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "duplicate",
                "error": True
            }

    def _check_low_quality_chunks(self) -> Dict[str, Any]:  # 检测低质量知识片段
        """检测低质量知识片段"""
        try:
            # 查询可能低质量的片段（内容过短或过长）
            query = """
                SELECT id, doc_id, content, LENGTH(content) as content_length
                FROM knowledge_chunks
                WHERE is_deleted = 0
                  AND (LENGTH(content) < 50 OR LENGTH(content) > 5000)  # 内容长度不在合理范围内
                ORDER BY content_length ASC  # 按内容长度升序排列
                LIMIT 20
            """
            low_quality = mysql_client.fetch_all(query) or []  # 查询低质量片段

            if not low_quality:  # 如果没有低质量片段
                return {
                    "answer": "✅ 低质量片段检测完成\n\n未发现明显的低质量知识片段，所有片段长度都在合理范围内。",
                    "sources": [],
                    "has_sources": False,
                    "task_type": "knowledge_inspection",
                    "inspection_type": "low_quality",
                    "data": {"low_quality_chunks": [], "count": 0}
                }

            chunk_list = []  # 初始化片段列表
            for chunk in low_quality:  # 遍历每个低质量片段
                chunk_list.append({
                    "chunk_id": chunk.get("id"),
                    "doc_id": chunk.get("doc_id"),
                    "content_length": chunk.get("content_length"),
                })

            too_short = sum(1 for c in chunk_list if c["content_length"] < 50)  # sum() + 生成器表达式：统计过短片段数量（类似 Java 的 stream().filter().count()）
            too_long = sum(1 for c in chunk_list if c["content_length"] > 5000)  # 统计过长片段数量

            answer = f"""⚠️ 发现 {len(low_quality)} 个可能低质量的知识片段：

📊 统计：
- 内容过短（<50字）：{too_short} 个
- 内容过长（>5000字）：{too_long} 个

"""
            for i, chunk in enumerate(chunk_list[:5], 1):  # 遍历前5个片段
                if chunk["content_length"] < 50:  # 过短
                    answer += f"{i}. 片段ID {chunk['chunk_id']}：内容过短（{chunk['content_length']}字）\n"
                else:  # 过长
                    answer += f"{i}. 片段ID {chunk['chunk_id']}：内容过长（{chunk['content_length']}字）\n"

            if len(chunk_list) > 5:  # 超过5个未显示
                answer += f"\n... 还有 {len(chunk_list) - 5} 个片段未显示"

            answer += "\n\n建议：请管理员审核这些片段，过短的考虑合并，过长的考虑拆分。"

            return {
                "answer": answer,
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "low_quality",
                "data": {"low_quality_chunks": chunk_list, "count": len(chunk_list)}
            }
        except Exception as e:
            logger.error(f"[InspectionAgent] Low quality check error: {str(e)}")
            return {
                "answer": "低质量片段检测失败，请稍后重试。",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "low_quality",
                "error": True
            }

    def _check_stale_knowledge(self) -> Dict[str, Any]:  # 检测过期知识
        """检测过期知识"""
        try:
            # 查询30天以上未更新的文档
            query = """
                SELECT id, title, updated_at, created_at
                FROM knowledge_docs
                WHERE is_deleted = 0
                  AND updated_at < DATE_SUB(NOW(), INTERVAL 30 DAY)  # DATE_SUB 日期减法：30天前的日期
                ORDER BY updated_at ASC  # 按更新时间升序（最旧的在前）
                LIMIT 20
            """
            stale_docs = mysql_client.fetch_all(query) or []  # 查询过期文档

            if not stale_docs:  # 如果没有过期文档
                return {
                    "answer": "✅ 过期知识检测完成\n\n所有文档都在30天内更新过，知识库内容较为新鲜。",
                    "sources": [],
                    "has_sources": False,
                    "task_type": "knowledge_inspection",
                    "inspection_type": "stale",
                    "data": {"stale_docs": [], "count": 0}
                }

            doc_list = []  # 初始化文档列表
            for doc in stale_docs:  # 遍历过期文档
                doc_list.append({
                    "doc_id": doc.get("id"),
                    "title": doc.get("title"),
                    "updated_at": str(doc.get("updated_at")),  # str() 将日期对象转为字符串
                })

            answer = f"""⚠️ 发现 {len(stale_docs)} 个可能过期的知识文档（30天以上未更新）：

"""
            for i, doc in enumerate(doc_list[:5], 1):  # 遍历前5个
                answer += f"{i}. 《{doc['title']}》 - 最后更新：{doc['updated_at']}\n"

            if len(doc_list) > 5:
                answer += f"\n... 还有 {len(doc_list) - 5} 个文档未显示"

            answer += "\n\n建议：请管理员审核这些文档，确认内容是否仍然有效，必要时进行更新。"

            return {
                "answer": answer,
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "stale",
                "data": {"stale_docs": doc_list, "count": len(doc_list)}
            }
        except Exception as e:
            logger.error(f"[InspectionAgent] Stale knowledge check error: {str(e)}")
            return {
                "answer": "过期知识检测失败，请稍后重试。",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "stale",
                "error": True
            }

    def _check_unpopular_docs(self) -> Dict[str, Any]:  # 检测无人访问的文档
        """检测无人访问的文档"""
        try:
            # 查询从创建至今没有被访问过的文档
            query = """
                SELECT d.id, d.title, d.created_at,
                       (SELECT COUNT(*) FROM doc_view_logs WHERE doc_id = d.id) as view_count  # 子查询统计访问次数
                FROM knowledge_docs d
                WHERE d.is_deleted = 0
                  AND d.created_at < DATE_SUB(NOW(), INTERVAL 7 DAY)  # 创建超过7天的文档
                HAVING view_count = 0  # HAVING 过滤分组后的结果：访问次数为0
                ORDER BY d.created_at ASC
                LIMIT 20
            """
            unpopular = mysql_client.fetch_all(query) or []  # 查询无人访问文档

            if not unpopular:  # 如果所有文档都有访问
                return {
                    "answer": "✅ 无人访问文档检测完成\n\n所有文档在近7天内都有访问记录，知识库使用率良好。",
                    "sources": [],
                    "has_sources": False,
                    "task_type": "knowledge_inspection",
                    "inspection_type": "unpopular",
                    "data": {"unpopular_docs": [], "count": 0}
                }

            doc_list = []  # 初始化文档列表
            for doc in unpopular:  # 遍历无人访问文档
                doc_list.append({
                    "doc_id": doc.get("id"),
                    "title": doc.get("title"),
                    "created_at": str(doc.get("created_at")),
                    "view_count": doc.get("view_count", 0),
                })

            answer = f"""⚠️ 发现 {len(unpopular)} 个近7天无人访问的文档：

"""
            for i, doc in enumerate(doc_list[:5], 1):
                answer += f"{i}. 《{doc['title']}》 - 创建于：{doc['created_at']}\n"

            if len(doc_list) > 5:
                answer += f"\n... 还有 {len(doc_list) - 5} 个文档未显示"

            answer += "\n\n建议：请管理员审核这些文档，确认是否需要更新内容或从知识库移除。"

            return {
                "answer": answer,
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "unpopular",
                "data": {"unpopular_docs": doc_list, "count": len(doc_list)}
            }
        except Exception as e:
            logger.error(f"[InspectionAgent] Unpopular docs check error: {str(e)}")
            return {
                "answer": "无人访问文档检测失败，请稍后重试。",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "unpopular",
                "error": True
            }

    def _run_full_inspection(self) -> Dict[str, Any]:  # 执行完整巡检（包含所有检测项）
        """执行完整巡检"""
        try:
            # 获取各项巡检结果
            duplicate_result = self._check_duplicate_docs()  # 执行重复文档检测
            low_quality_result = self._check_low_quality_chunks()  # 执行低质量片段检测
            stale_result = self._check_stale_knowledge()  # 执行过期知识检测
            unpopular_result = self._check_unpopular_docs()  # 执行无人访问文档检测

            # 汇总问题数量
            total_issues = (  # 链式计算总问题数
                duplicate_result.get("data", {}).get("count", 0) +  # 重复文档数
                low_quality_result.get("data", {}).get("count", 0) +  # 低质量片段数
                stale_result.get("data", {}).get("count", 0) +  # 过期文档数
                unpopular_result.get("data", {}).get("count", 0)  # 无人访问文档数
            )

            answer = f"""🔍 知识库完整巡检报告

━━━━━━━━━━━━━━━━━━

📋 巡检项目概览：

1️⃣ 重复文档检测：{duplicate_result.get("data", {}).get("count", 0)} 个问题
2️⃣ 低质量片段检测：{low_quality_result.get("data", {}).get("count", 0)} 个问题
3️⃣ 过期知识检测：{stale_result.get("data", {}).get("count", 0)} 个问题
4️⃣ 无人访问文档：{unpopular_result.get("data", {}).get("count", 0)} 个问题

━━━━━━━━━━━━━━━━━━

📊 问题总计：{total_issues} 个

"""

            if total_issues == 0:  # 如果没有问题
                answer += "🎉 恭喜！知识库质量良好，未发现明显问题。"
            else:  # 有问题
                answer += "⚠️ 建议及时处理以上问题，以保持知识库质量。\n\n如需详细查看某一类问题，请单独执行该类巡检。"

            return {
                "answer": answer,
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "full",
                "data": {
                    "duplicate_count": duplicate_result.get("data", {}).get("count", 0),  # 重复文档数
                    "low_quality_count": low_quality_result.get("data", {}).get("count", 0),  # 低质量片段数
                    "stale_count": stale_result.get("data", {}).get("count", 0),  # 过期文档数
                    "unpopular_count": unpopular_result.get("data", {}).get("count", 0),  # 无人访问文档数
                    "total_issues": total_issues  # 总问题数
                }
            }
        except Exception as e:
            logger.error(f"[InspectionAgent] Full inspection error: {str(e)}")
            return {
                "answer": f"完整巡检失败：{str(e)}",
                "sources": [],
                "has_sources": False,
                "task_type": "knowledge_inspection",
                "inspection_type": "full",
                "error": True
            }

    def get_inspection_summary(self) -> Dict[str, Any]:  # 获取巡检摘要（不执行详细检测）
        """获取巡检摘要（不执行详细检测）"""
        return {
            "available_inspections": self.inspection_types,  # 可用的巡检类型
            "usage": {  # 各类型的使用说明
                "duplicate": "检测标题相同的重复文档",
                "low_quality": "检测内容过短或过长的片段",
                "stale": "检测30天以上未更新的文档",
                "unpopular": "检测7天内无人访问的文档",
                "full": "执行完整巡检（包含以上四项）"
            }
        }