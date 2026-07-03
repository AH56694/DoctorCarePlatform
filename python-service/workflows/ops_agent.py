from typing import Dict, Any, Optional, Generator, List  # 导入类型提示：Dict 字典，Any 任意类型，Optional 可为 None，Generator 生成器，List 列表
from core.mysql_client import mysql_client  # 导入 MySQL 客户端实例
import logging  # 导入日志模块
import json  # 导入 JSON 模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class OpsAgent:  # 定义运营分析 Agent 类
    """
    Ops Agent - 负责运营分析与后台建议

    功能：
    1. 自动分析日志
    2. 自动提示知识缺口
    3. 自动生成后台建议
    4. 热门问题日报/周报
    5. 知识库增长趋势
    6. Agent 成功率与失败率趋势
    7. 工具调用失败排行
    """

    def __init__(self):  # 构造函数
        self.analysis_types = {  # 分析类型映射字典
            "knowledge_gap": "知识缺口分析",  # 知识缺口分析
            "qa_trend": "问答趋势分析",  # 问答趋势分析
            "user_activity": "用户活跃度分析",  # 用户活跃度分析
            "full_report": "完整运营报告",  # 完整运营报告
            "hot_questions": "热门问题分析",  # 热门问题分析
            "knowledge_growth": "知识库增长趋势",  # 知识库增长趋势
            "agent_success_rate": "Agent成功率分析",  # Agent 成功率分析
            "tool_call_failures": "工具调用失败排行"  # 工具调用失败排行
        }

    def analyze(self, analysis_type: str = "full_report", **kwargs) -> Dict[str, Any]:  # analyze 方法：执行运营分析
        """
        执行运营分析

        Args:
            analysis_type: 分析类型（knowledge_gap/qa_trend/user_activity/full_report）
            **kwargs: 其他参数

        Returns:
            分析结果与建议
        """
        logger.info(f"[OpsAgent] Starting analysis: {analysis_type}")

        try:
            if analysis_type == "knowledge_gap":  # 知识缺口分析
                return self._analyze_knowledge_gap()
            elif analysis_type == "qa_trend":  # 问答趋势分析
                return self._analyze_qa_trend()
            elif analysis_type == "user_activity":  # 用户活跃度分析
                return self._analyze_user_activity()
            elif analysis_type == "full_report":  # 完整运营报告
                return self._generate_full_report()
            elif analysis_type == "hot_questions":  # 热门问题分析
                return self._analyze_hot_questions(**kwargs)  # **kwargs 解包传递额外参数（如 period）
            elif analysis_type == "knowledge_growth":  # 知识库增长趋势
                return self._analyze_knowledge_growth(**kwargs)
            elif analysis_type == "agent_success_rate":  # Agent 成功率分析
                return self._analyze_agent_success_rate(**kwargs)
            elif analysis_type == "tool_call_failures":  # 工具调用失败排行
                return self._analyze_tool_call_failures()
            else:  # 未知分析类型
                return {
                    "success": False,
                    "error": f"Unknown analysis type: {analysis_type}",
                    "available_types": list(self.analysis_types.keys())  # list() 将字典的键转为列表（类似 Java 的 new ArrayList<>(map.keySet())）
                }

        except Exception as e:
            logger.error(f"[OpsAgent] Analysis failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def analyze_stream(self, analysis_type: str = "full_report", **kwargs) -> Generator[str, None, None]:  # 流式运营分析
        """流式执行运营分析"""
        logger.info(f"[OpsAgent] Starting streaming analysis: {analysis_type}")

        try:
            yield json.dumps({"type": "analysis_started", "analysis_type": analysis_type})  # 产出分析开始事件

            result = self.analyze(analysis_type, **kwargs)  # 执行同步分析获取完整结果

            yield json.dumps({"type": "analysis_progress", "step": "log_analysis", "status": "completed"})  # 产出进度事件
            yield json.dumps({"type": "analysis_progress", "step": "knowledge_gap_identification", "status": "completed"})
            yield json.dumps({"type": "analysis_progress", "step": "suggestion_generation", "status": "completed"})

            yield json.dumps({"type": "analysis_completed", "result": result})  # 产出分析完成事件（含完整结果）

        except Exception as e:
            logger.error(f"[OpsAgent] Stream analysis failed: {e}", exc_info=True)
            yield json.dumps({"type": "error", "error": str(e)})  # 产出错误事件

    def _analyze_knowledge_gap(self) -> Dict[str, Any]:  # 知识缺口分析
        """分析知识缺口 - P4-3核心功能"""
        logger.info("[OpsAgent] Analyzing knowledge gap")

        # 查询未命中问题
        unanswered_query = """  # SQL 查询未命中问题
            SELECT question, count, create_time
            FROM qa_unanswered
            ORDER BY count DESC  # 按命中次数降序（最频繁的在前）
            LIMIT 20
        """
        unanswered_questions = mysql_client.fetch_all(unanswered_query) or []  # 执行查询

        # 查询最近的QA日志
        qa_log_query = """
            SELECT question, answer, create_time
            FROM qa_log
            ORDER BY create_time DESC  # 按创建时间降序（最新的在前）
            LIMIT 50
        """
        recent_qa = mysql_client.fetch_all(qa_log_query) or []  # 查询最近50条问答日志

        # 分析知识缺口
        knowledge_gaps = []  # 初始化知识缺口列表
        for qa in unanswered_questions:  # 遍历未命中问题
            question = qa.get("question", "")  # 获取问题文本
            count = qa.get("count", 0)  # 获取未命中次数

            # 简单分类
            gap_type = self._classify_gap(question)  # 对问题进行分类
            knowledge_gaps.append({
                "question": question,
                "count": count,
                "gap_type": gap_type,
                "priority": "high" if count > 5 else "medium" if count > 2 else "low"  # 嵌套三元表达式（类似 Java 的 a ? b : c ? d : e）
            })

        # 生成建议
        suggestions = self._generate_gap_suggestions(knowledge_gaps)  # 根据缺口生成建议

        answer = f"""🔍 知识缺口分析报告

━━━━━━━━━━━━━━━━━━━━━━━━━

📊 未命中问题概览：
- 高优先级（>5次）：{len([g for g in knowledge_gaps if g["priority"] == "high"])}  # 列表推导式 + 条件过滤（类似 Java 的 stream().filter().count()）
- 中优先级（2-5次）：{len([g for g in knowledge_gaps if g["priority"] == "medium"])}
- 低优先级（1-2次）：{len([g for g in knowledge_gaps if g["priority"] == "low"])}

━━━━━━━━━━━━━━━━━━━━━━━━━

📋 TOP 未命中问题：
"""
        for i, gap in enumerate(knowledge_gaps[:10], 1):  # 遍历前10个缺口
            answer += f"{i}. [{gap['priority']}] {gap['question']} ({gap['count']}次)\n"

        answer += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━

💡 建议：
"""
        for i, suggestion in enumerate(suggestions[:5], 1):  # 遍历前5条建议
            answer += f"{i}. {suggestion}\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "knowledge_gaps": knowledge_gaps,  # 知识缺口列表
                "suggestions": suggestions,  # 建议列表
                "unanswered_count": len(unanswered_questions),  # 未命中问题数
                "recent_qa_count": len(recent_qa)  # 最近问答数
            },
            "task_type": "ops_analysis"
        }

    def _analyze_qa_trend(self) -> Dict[str, Any]:  # 问答趋势分析
        """分析问答趋势"""
        logger.info("[OpsAgent] Analyzing QA trend")

        # 查询最近7天的QA数量
        trend_query = """
            SELECT
                DATE(create_time) as log_date,  # DATE() 提取日期部分
                COUNT(*) as question_count
            FROM qa_log
            WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)  # 最近7天
            GROUP BY DATE(create_time)  # 按日期分组
            ORDER BY log_date DESC  # 按日期降序
        """
        qa_trend = mysql_client.fetch_all(trend_query) or []

        # 查询今日统计
        today_query = """
            SELECT COUNT(*) as today_count
            FROM qa_log
            WHERE DATE(create_time) = DATE(NOW())  # 今日的问答记录
        """
        today_stats = mysql_client.fetch_one(today_query) or {}  # fetch_one 返回单行记录

        answer = f"""📈 问答趋势分析

━━━━━━━━━━━━━━━━━━━━━━━━━

📊 今日问答：
- 今日问答次数：{today_stats.get('today_count', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━

📅 近7天趋势：
"""
        for i, daily in enumerate(qa_trend, 1):  # 遍历每日统计数据
            log_date = str(daily.get('log_date', ''))  # 将日期转为字符串
            count = daily.get('question_count', 0)  # 获取当日问答数
            answer += f"{log_date}: {count} 次问答\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "qa_trend": qa_trend,
                "today_count": today_stats.get('today_count', 0)
            },
            "task_type": "ops_analysis"
        }

    def _analyze_user_activity(self) -> Dict[str, Any]:  # 用户活跃度分析
        """分析用户活跃度"""
        logger.info("[OpsAgent] Analyzing user activity")

        # 查询活跃用户
        user_query = """
            SELECT
                userId as user_id,
                COUNT(*) as qa_count,  # 每个用户的问答次数
                MAX(create_time) as last_active  # 最后活跃时间
            FROM qa_log
            WHERE create_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)  # 最近7天
            GROUP BY userId  # 按用户ID分组
            ORDER BY qa_count DESC  # 按问答次数降序
            LIMIT 20
        """
        active_users = mysql_client.fetch_all(user_query) or []

        # 查询总用户
        user_count_query = "SELECT COUNT(*) as user_count FROM users"
        user_count = mysql_client.fetch_one(user_count_query) or {}

        answer = f"""👥 用户活跃度分析

━━━━━━━━━━━━━━━━━━━━━━━━━

📊 总用户：{user_count.get('user_count', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━

🏆 活跃用户 TOP 10：
"""
        for i, user in enumerate(active_users[:10], 1):  # 遍历前10个活跃用户
            user_id = user.get('user_id', 'N/A')  # N/A 表示无数据
            qa_count = user.get('qa_count', 0)
            last_active = str(user.get('last_active', ''))
            answer += f"{i}. 用户 {user_id}: {qa_count} 次问答 (最后活跃: {last_active})\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "active_users": active_users,
                "total_users": user_count.get('user_count', 0)
            },
            "task_type": "ops_analysis"
        }

    def _generate_full_report(self) -> Dict[str, Any]:  # 生成完整运营报告
        """生成完整运营报告"""
        logger.info("[OpsAgent] Generating full report")

        gap_result = self._analyze_knowledge_gap()  # 获取知识缺口分析结果
        trend_result = self._analyze_qa_trend()  # 获取问答趋势分析结果
        activity_result = self._analyze_user_activity()  # 获取用户活跃度分析结果

        # 整合建议
        suggestions = []  # 初始化建议列表
        if gap_result.get("data", {}).get("knowledge_gaps", []):  # 如果有知识缺口
            suggestions.append("建议优先补充高频未命中问题的知识")  # 添加建议
        if activity_result.get("data", {}).get("active_users", []):  # 如果有活跃用户
            suggestions.append("可以关注活跃用户的问题需求")
        suggestions.append("定期进行知识巡检保证知识库质量")  # 通用建议

        answer = f"""📋 完整运营分析报告

━━━━━━━━━━━━━━━━━━━━━━━━━

1️⃣ 知识缺口分析
{gap_result.get('answer', '').split('━━━━━━━━━━━━━━━━━━━━━━━━━')[1].split('💡 建议')[0]}  # .split() 分割字符串取指定部分

━━━━━━━━━━━━━━━━━━━━━━━━━

2️⃣ 问答趋势分析
{trend_result.get('answer', '').split('━━━━━━━━━━━━━━━━━━━━━━━━━')[1]}

━━━━━━━━━━━━━━━━━━━━━━━━━

3️⃣ 用户活跃度分析
{activity_result.get('answer', '').split('━━━━━━━━━━━━━━━━━━━━━━━━━')[1]}

━━━━━━━━━━━━━━━━━━━━━━━━━

✅ 运营建议：
"""
        for i, suggestion in enumerate(suggestions, 1):  # enumerate 从1开始编号
            answer += f"{i}. {suggestion}\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "knowledge_gap": gap_result.get("data"),  # 知识缺口数据
                "qa_trend": trend_result.get("data"),  # 问答趋势数据
                "user_activity": activity_result.get("data"),  # 用户活跃度数据
                "suggestions": suggestions  # 建议列表
            },
            "task_type": "ops_analysis"
        }

    def _classify_gap(self, question: str) -> str:  # 分类知识缺口类型
        """分类知识缺口类型"""
        lower_q = question.lower()  # 转为小写

        tech_keywords = ["python", "java", "sql", "database", "算法", "编程", "代码"]  # 技术关键词列表
        for kw in tech_keywords:  # 遍历关键词
            if kw in lower_q:  # 如果问题中包含该关键词
                return "技术知识"  # 返回技术知识类型

        business_keywords = ["流程", "制度", "规定", "流程", "审批"]  # 业务关键词列表
        for kw in business_keywords:
            if kw in lower_q:
                return "业务知识"  # 返回业务知识类型

        return "通用知识"  # 默认返回通用知识类型

    def _generate_gap_suggestions(self, knowledge_gaps: List[Dict]) -> List[str]:  # 生成知识缺口建议
        """生成知识缺口建议"""
        suggestions = []  # 初始化建议列表

        if knowledge_gaps:  # 如果有知识缺口
            high_priority = [g for g in knowledge_gaps if g.get("priority") == "high"]  # 过滤高优先级缺口（列表推导式）
            if high_priority:  # 如果有高优先级缺口
                suggestions.append(f"优先补充高频问题：{high_priority[0].get('question', '')}")  # 建议补充第一个高频问题

            tech_gaps = [g for g in knowledge_gaps if g.get("gap_type") == "技术知识"]  # 过滤技术类缺口
            if tech_gaps:
                suggestions.append("建议完善技术知识库")

            suggestions.append("可以创建一个新的知识分类来整理这些未覆盖的知识")  # 通用建议

        return suggestions  # 返回建议列表

    def _analyze_hot_questions(self, period: str = "week") -> Dict[str, Any]:  # 热门问题分析
        """分析热门问题（日报/周报）"""
        logger.info(f"[OpsAgent] Analyzing hot questions, period: {period}")

        days = 7 if period == "week" else 1  # 周报取7天，日报取1天

        hot_query = f"""  # f-string 格式化 SQL 查询
            SELECT question, COUNT(*) as count
            FROM qa_log
            WHERE DATE(create_time) >= DATE(DATE_SUB(CURDATE(), INTERVAL {days} DAY))
            GROUP BY question  # 按问题文本分组
            ORDER BY count DESC  # 按出现次数降序
            LIMIT 15
        """
        hot_questions = mysql_client.fetch_all(hot_query) or []

        total_count = sum(q.get('count', 0) for q in hot_questions)  # sum() + 生成器表达式：计算总次数
        unique_count = len(hot_questions)  # 独立问题数

        report_type = "周报" if period == "week" else "日报"  # 判断报告类型

        answer = f"""📊 热门问题{report_type}

【统计概览】
- 统计周期：最近 {days} 天
- 问题总数：{total_count} 次
- 独立问题数：{unique_count} 个

【TOP 10 热门问题排行】
"""
        for i, q in enumerate(hot_questions[:10], 1):  # 遍历前10个热门问题
            question = q.get('question', '')
            count = q.get('count', 0)
            answer += f"  {i}. {question}（{count}次）\n"

        if len(hot_questions) > 10:  # 如果超过10个
            remaining = hot_questions[10:]  # 列表切片：取第11个及之后的元素
            answer += "\n【其他热门问题】\n"
            for q in remaining:
                answer += f"  • {q.get('question', '')}（{q.get('count', 0)}次）\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "hot_questions": hot_questions,
                "period": period,
                "total_count": total_count,
                "unique_count": unique_count
            },
            "task_type": "ops_analysis"
        }

    def _analyze_knowledge_growth(self, period: str = "week") -> Dict[str, Any]:  # 知识库增长趋势分析
        """分析知识库增长趋势"""
        logger.info(f"[OpsAgent] Analyzing knowledge growth, period: {period}")

        days = 7 if period == "week" else 30  # 周取7天，月取30天

        growth_query = f"""
            SELECT
                DATE(create_time) as log_date,
                COUNT(*) as doc_count
            FROM knowledge_doc
            WHERE create_time >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY DATE(create_time)
            ORDER BY log_date ASC  # 按日期升序（时间线）
        """
        growth_data = mysql_client.fetch_all(growth_query) or []

        chunk_growth_query = f"""
            SELECT
                DATE(k.create_time) as log_date,
                COUNT(*) as chunk_count
            FROM knowledge_chunk k
            JOIN knowledge_doc d ON k.doc_id = d.id  # JOIN 关联知识片段和文档表
            WHERE d.create_time >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY DATE(k.create_time)
            ORDER BY log_date ASC
        """
        chunk_data = mysql_client.fetch_all(chunk_growth_query) or []

        total_docs = mysql_client.fetch_one("SELECT COUNT(*) as count FROM knowledge_doc") or {}  # 文档总数
        total_chunks = mysql_client.fetch_one("SELECT COUNT(*) as count FROM knowledge_chunk") or {}  # 片段总数

        period_label = "近7天" if period == "week" else "近30天"
        total_doc_count = total_docs.get('count', 0)  # 文档总数
        total_chunk_count = total_chunks.get('count', 0)  # 片段总数
        period_docs = sum(d.get('doc_count', 0) for d in growth_data)  # 期间新增文档数
        period_chunks = sum(c.get('chunk_count', 0) for c in chunk_data)  # 期间新增片段数

        answer = f"""
📈 知识库增长趋势

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【知识库规模概览】

  📚 文档总数：{total_doc_count} 篇
  📄 知识片段：{total_chunk_count} 个
  📅 统计周期：{period_label}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【期间新增统计】

  新增文档：{period_docs} 篇
  🔖 新增片段：{period_chunks} 个

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【每日增长趋势】

"""
        for day in growth_data:  # 遍历每日增长数据
            date = day.get('log_date', '')
            count = day.get('doc_count', 0)
            bar_length = min(count * 5, 40)  # min() 取较小值，限制柱状图最大长度
            bar = '█' * bar_length  # 字符串乘法：重复字符（如 '█' * 3 = '███'）
            answer += f"  {date} │ {bar} {count}篇\n"

        answer += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "growth_data": growth_data,
                "chunk_data": chunk_data,
                "total_docs": total_doc_count,
                "total_chunks": total_chunk_count,
                "period_docs": period_docs,
                "period_chunks": period_chunks,
                "period": period
            },
            "task_type": "ops_analysis"
        }

    def _analyze_agent_success_rate(self, period: str = "week") -> Dict[str, Any]:  # Agent 成功率分析
        """分析Agent成功率与失败率趋势"""
        logger.info(f"[OpsAgent] Analyzing agent success rate, period: {period}")

        days = 7 if period == "week" else 30

        success_query = f"""
            SELECT
                DATE(start_time) as log_date,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as success_count,  # SUM + CASE 条件统计成功数（类似 Java 的 if-else 累加）
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,  # 统计失败数
                COUNT(*) as total_count
            FROM agent_run
            WHERE start_time >= DATE_SUB(NOW(), INTERVAL {days} DAY)
            GROUP BY DATE(start_time)
            ORDER BY log_date ASC
        """
        success_data = mysql_client.fetch_all(success_query) or []

        total_success = sum(d.get('success_count', 0) for d in success_data)  # 总成功次数
        total_failed = sum(d.get('failed_count', 0) for d in success_data)  # 总失败次数
        total_runs = total_success + total_failed  # 总运行次数
        overall_rate = (total_success / total_runs * 100) if total_runs > 0 else 0  # 计算总体成功率，避免除以零

        period_label = "近7天" if period == "week" else "近30天"

        answer = f"""
✅ Agent成功率分析

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【总体统计】

  📅 统计周期：{period_label}
  🔄 运行总次数：{total_runs} 次
  ✅ 成功次数：{total_success} 次
  ❌ 失败次数：{total_failed} 次
  📊 总体成功率：{overall_rate:.1f}%  # :.1f 格式化为保留1位小数的浮点数

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【每日成功率趋势】

"""
        for day in success_data:  # 遍历每日数据
            date = day.get('log_date', '')
            day_total = day.get('total_count', 0)
            day_success = day.get('success_count', 0)
            day_rate = (day_success / day_total * 100) if day_total > 0 else 0  # 计算每日成功率
            success_bar_length = min(int(day_rate), 50)  # int() 将浮点数转为整数
            success_bar = '█' * success_bar_length  # 生成柱状图
            answer += f"  {date}\n     成功率: {day_rate:.1f}% ({success_bar})\n     成功/总数: {day_success}/{day_total}\n\n"

        answer += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

        return {
            "success": True,
            "answer": answer,
            "data": {
                "success_data": success_data,
                "total_runs": total_runs,
                "total_success": total_success,
                "total_failed": total_failed,
                "overall_success_rate": overall_rate,
                "period": period
            },
            "task_type": "ops_analysis"
        }

    def _analyze_tool_call_failures(self) -> Dict[str, Any]:  # 工具调用失败排行分析
        """分析工具调用失败排行"""
        logger.info("[OpsAgent] Analyzing tool call failures")

        failure_query = """
            SELECT
                tool_name,
                COUNT(*) as failure_count,
                GROUP_CONCAT(DISTINCT error_message ORDER BY timestamp DESC LIMIT 5) as recent_errors  # GROUP_CONCAT 分组内拼接字符串
            FROM tool_call
            WHERE status = 'failed'  # 只查询失败的记录
            GROUP BY tool_name  # 按工具名称分组
            ORDER BY failure_count DESC  # 按失败次数降序
            LIMIT 10
        """
        failure_data = mysql_client.fetch_all(failure_query) or []

        total_failures = sum(f.get('failure_count', 0) for f in failure_data)  # 总失败次数
        failed_tool_count = len(failure_data)  # 失败工具种类数

        answer = f"""
🔧 工具调用失败排行

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【统计概览】

  🔨 失败工具种类：{failed_tool_count} 个
  ❌ 总失败次数：{total_failures} 次

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【失败排行 TOP 10】

"""
        max_count = max([f.get('failure_count', 1) for f in failure_data], default=1)  # max() 取最大值，default 参数在列表为空时返回默认值
        for i, tool in enumerate(failure_data, 1):  # 遍历失败排行
            tool_name = tool.get('tool_name', '')
            count = tool.get('failure_count', 0)
            bar_length = min(int(count / max_count * 30), 30)  # 按比例计算柱状图长度
            bar = '█' * bar_length
            answer += f"  {i}. {tool_name}\n     {' ' * 4}{bar} {count}次失败\n\n"

        answer += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 建议：关注失败次数较多的工具，检查其配置和依赖服务是否正常。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

        return {
            "success": True,
            "answer": answer,
            "data": {
                "failure_data": failure_data,
                "total_failures": total_failures,
                "failed_tool_count": failed_tool_count
            },
            "task_type": "ops_analysis"
        }

    def get_analysis_options(self) -> Dict[str, Any]:  # 获取可执行的分析选项
        """获取可执行的分析选项"""
        return {
            "available_analysis": self.analysis_types,  # 可用的分析类型
            "usage": {  # 各类型的使用说明
                "knowledge_gap": "分析知识缺口和未命中问题",
                "qa_trend": "分析问答趋势和统计",
                "user_activity": "分析用户活跃度",
                "full_report": "生成完整运营报告（推荐）",
                "hot_questions": "分析热门问题日报/周报",
                "knowledge_growth": "分析知识库增长趋势",
                "agent_success_rate": "分析Agent成功率与失败率",
                "tool_call_failures": "分析工具调用失败排行"
            }
        }


# 全局实例
ops_agent = OpsAgent()  # 创建运营分析 Agent 的全局实例（模块级单例，类似 Java 的 static final）