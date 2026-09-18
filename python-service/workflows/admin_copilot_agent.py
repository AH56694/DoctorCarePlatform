from typing import Dict, Any, Optional, Generator  # 导入类型提示：Dict 字典类型，Any 任意类型，Optional 可为 None，Generator 生成器类型
from core.mysql_client import mysql_client  # 导入 MySQL 客户端实例（用于数据库操作）
from workflows.ops_agent import ops_agent  # 导入运营分析 Agent 的全局实例
import logging  # 导入日志模块
import json  # 导入 JSON 序列化模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class AdminCopilotAgent:  # 定义管理助手 Agent 类
    """管理助手Agent - 专门处理管理端运营分析的工作流"""

    def __init__(self):  # 构造函数
        self.ops_agent = ops_agent  # 引用运营分析 Agent 的全局实例（不新建实例，复用单例）
        self.admin_operations = {  # 管理操作类型映射字典（键为操作标识，值为中文描述）
            "stats": "统计分析",  # 统计分析
            "knowledge_inspection": "知识巡检",  # 知识巡检
            "knowledge_gap": "知识缺口分析（P4-3）",  # 知识缺口分析
            "unanswered_analysis": "未命中分析",  # 未命中问题分析
            "user_activity": "用户活跃度分析",  # 用户活跃度分析
            "full_ops_report": "完整运营报告（P4-3）",  # 完整运营报告
            "hot_questions": "热门问题日报/周报",  # 热门问题分析
            "knowledge_growth": "知识库增长趋势",  # 知识库增长趋势
            "agent_success_rate": "Agent成功率分析",  # Agent 成功率分析
            "tool_call_failures": "工具调用失败排行",  # 工具调用失败排行
        }

    def handle(self, question: str, conversation_id: Optional[str] = None,  # handle 方法：处理管理助手请求
               user_id: Optional[str] = None, context: str = "",
               **kwargs) -> Dict[str, Any]:
        """
        处理管理助手请求

        Args:
            question: 用户问题
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            **kwargs: 其他参数

        Returns:
            包含answer和sources的字典
        """
        logger.info("AI request processing; content omitted")

        try:
            operation = self._parse_operation(question)  # 解析问题中的操作类型
            result = self._execute_operation(operation, question)  # 执行对应操作

            return result  # 返回操作结果

        except Exception as e:
            logger.error(f"[AdminCopilotAgent] Error: {e}", exc_info=True)  # 记录错误及完整堆栈
            return {  # 返回错误响应
                "answer": f"抱歉，处理管理请求时出错：{str(e)}",  # 错误提示
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def handle_stream(self, question: str, conversation_id: Optional[str] = None,
                     user_id: Optional[str] = None, context: str = "",
                     **kwargs) -> Generator[str, None, None]:  # 流式处理管理助手请求
        """流式处理管理助手请求"""
        logger.info("AI request processing; content omitted")

        try:
            operation = self._parse_operation(question)  # 解析操作类型

            if operation in ["knowledge_gap", "full_ops_report"]:  # 知识缺口和完整报告走流式分析
                yield from self.ops_agent.analyze_stream(  # yield from 委托给另一个生成器（类似 Java 的 Flux.concat），将子生成器的产出逐个传递
                    "knowledge_gap" if operation == "knowledge_gap" else "full_report"  # 三元表达式选择分析类型
                )
                return  # return 在生成器中终止迭代（类似 Java 的 return，但这里是在生成器中提前结束）

            result = self.handle(question, conversation_id, user_id, context, **kwargs)  # 调用同步方法获取完整结果
            answer = result.get("answer", "")  # 获取答案文本

            for char in answer:  # 逐字符遍历答案（模拟流式输出）
                yield json.dumps({"type": "token", "content": char})  # 产出 token 事件

            yield json.dumps({"type": "end", "content": result})  # 产出结束事件

        except Exception as e:
            logger.error(f"[AdminCopilotAgent] Stream error: {e}", exc_info=True)
            yield json.dumps({"type": "error", "error": str(e)})  # 产出错误事件

    def _parse_operation(self, question: str) -> str:  # 解析问题中的操作类型
        """解析操作类型"""
        lower_question = question.lower()  # 转为小写便于匹配

        if any(kw in lower_question for kw in ["知识缺口", "缺口", "未命中", "知识缺口分析"]):  # any() 检查是否包含任一关键词
            return "knowledge_gap"  # 返回知识缺口分析类型
        if any(kw in lower_question for kw in ["运营报告", "完整报告", "全报告", "运营分析"]):
            return "full_ops_report"  # 返回完整运营报告类型
        if any(kw in lower_question for kw in ["用户", "活跃度", "活跃用户"]):
            return "user_activity"  # 返回用户活跃度分析类型
        if any(kw in lower_question for kw in ["统计", "报表", "数据", "分析", "多少", "数量"]):
            return "stats"  # 返回统计分析类型
        if any(kw in lower_question for kw in ["知识", "文档", "巡检", "检查", "质量"]):
            return "knowledge_inspection"  # 返回知识巡检类型
        if any(kw in lower_question for kw in ["热门问题", "问题排行", "top问题", "常见问题"]):
            return "hot_questions"  # 返回热门问题分析类型
        if any(kw in lower_question for kw in ["知识库增长", "文档增长", "增长趋势", "新增文档"]):
            return "knowledge_growth"  # 返回知识库增长趋势类型
        if any(kw in lower_question for kw in ["成功率", "失败率", "agent成功", "运行成功"]):
            return "agent_success_rate"  # 返回 Agent 成功率分析类型
        if any(kw in lower_question for kw in ["工具调用", "工具失败", "工具错误", "工具排行"]):
            return "tool_call_failures"  # 返回工具调用失败排行类型

        return "stats"  # 默认返回统计分析类型

    def _execute_operation(self, operation: str, question: str) -> Dict[str, Any]:  # 执行管理操作
        """执行管理操作"""
        try:
            if operation == "stats":  # 统计分析
                return self._get_stats()
            elif operation == "knowledge_inspection":  # 知识巡检
                return self._knowledge_inspection()
            elif operation == "knowledge_gap":  # 知识缺口分析
                return self._analyze_knowledge_gap()
            elif operation == "user_activity":  # 用户活跃度分析
                return self._analyze_user_activity()
            elif operation == "full_ops_report":  # 完整运营报告
                return self._generate_full_ops_report()
            elif operation == "hot_questions":  # 热门问题分析
                period = "week" if "周" in question else "day"  # 根据问题中是否含"周"判断时间周期
                return self._analyze_hot_questions(period)
            elif operation == "knowledge_growth":  # 知识库增长趋势
                period = "week" if "周" in question else "month"  # 周或月
                return self._analyze_knowledge_growth(period)
            elif operation == "agent_success_rate":  # Agent 成功率分析
                period = "week" if "周" in question else "month"
                return self._analyze_agent_success_rate(period)
            elif operation == "tool_call_failures":  # 工具调用失败排行
                return self._analyze_tool_call_failures()
            else:  # 未知操作
                return {
                    "answer": "抱歉，我暂时无法处理这类管理请求。",
                    "sources": [],
                    "has_sources": False,
                    "task_type": "admin_copilot"
                }
        except Exception as e:
            logger.error(f"[AdminCopilotAgent] Operation error: {e}", exc_info=True)
            return {
                "answer": f"执行操作时出错：{str(e)}",
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _get_stats(self) -> Dict[str, Any]:  # 获取统计数据
        """获取统计数据"""
        try:
            doc_count = mysql_client.fetch_one("SELECT COUNT(*) as count FROM knowledge_doc") or {}  # 查询文档总数，fetch_one 返回单行记录（字典）
            chunk_count = mysql_client.fetch_one("SELECT COUNT(*) as count FROM knowledge_chunk") or {}  # 查询知识片段总数
            qa_count = mysql_client.fetch_one("SELECT COUNT(*) as count FROM qa_log") or {}  # 查询问答日志总数
            user_count = mysql_client.fetch_one("SELECT COUNT(*) as count FROM user") or {}  # 查询用户总数
            unanswered_count = mysql_client.fetch_one("SELECT COUNT(*) as count FROM qa_unanswered") or {}  # 查询未命中问题总数

            answer = f"""📊 系统统计信息

━━━━━━━━━━━━━━━━━━━━━━━━━

📚 知识库：
- 文档数量：{doc_count.get('count', 0)}
- 知识片段：{chunk_count.get('count', 0)}

💬 问答系统：
- 总问答次数：{qa_count.get('count', 0)}
- 未命中问题：{unanswered_count.get('count', 0)}

👥 用户管理：
- 注册用户：{user_count.get('count', 0)}

━━━━━━━━━━━━━━━━━━━━━━━━━

💡 提示：
- 说"知识缺口分析"可以查看知识缺口（P4-3功能）
- 说"完整运营报告"可以获取完整分析（P4-3功能）
"""  # f-string 多行模板，构建统计信息文本

            return {
                "answer": answer,
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": {  # 原始统计数据
                    "doc_count": doc_count.get('count', 0),
                    "chunk_count": chunk_count.get('count', 0),
                    "qa_count": qa_count.get('count', 0),
                    "user_count": user_count.get('count', 0),
                    "unanswered_count": unanswered_count.get('count', 0)
                }
            }
        except Exception as e:
            logger.error(f"[AdminCopilotAgent] Stats error: {e}", exc_info=True)
            return {
                "answer": "获取统计数据失败，请稍后重试。",
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _knowledge_inspection(self) -> Dict[str, Any]:  # 知识巡检
        """知识巡检 - 调用InspectionAgent"""
        from workflows.inspection_agent import InspectionAgent  # 延迟导入（避免循环依赖）
        inspection_agent = InspectionAgent()  # 创建知识巡检 Agent 实例
        return inspection_agent.inspect("full")  # 执行完整巡检

    def _analyze_knowledge_gap(self) -> Dict[str, Any]:  # 知识缺口分析
        """知识缺口分析 - P4-3功能 - 调用Ops Agent"""
        logger.info("[AdminCopilotAgent] Analyzing knowledge gap via Ops Agent")
        result = self.ops_agent.analyze("knowledge_gap")  # 委托给运营分析 Agent
        if result.get("success"):  # 如果分析成功
            return {
                "answer": result.get("answer", ""),  # 分析报告文本
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})  # 原始分析数据
            }
        else:  # 分析失败
            return {
                "answer": "知识缺口分析失败：" + str(result.get("error", "")),  # 拼接错误信息
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _analyze_user_activity(self) -> Dict[str, Any]:  # 用户活跃度分析
        """用户活跃度分析 - 调用Ops Agent"""
        logger.info("[AdminCopilotAgent] Analyzing user activity via Ops Agent")
        result = self.ops_agent.analyze("user_activity")  # 委托给运营分析 Agent
        if result.get("success"):
            return {
                "answer": result.get("answer", ""),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})
            }
        else:
            return {
                "answer": "用户活跃度分析失败：" + str(result.get("error", "")),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _generate_full_ops_report(self) -> Dict[str, Any]:  # 生成完整运营报告
        """生成完整运营报告 - P4-3功能 - 调用Ops Agent"""
        logger.info("[AdminCopilotAgent] Generating full ops report via Ops Agent")
        result = self.ops_agent.analyze("full_report")  # 委托给运营分析 Agent 生成完整报告
        if result.get("success"):
            return {
                "answer": result.get("answer", ""),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})
            }
        else:
            return {
                "answer": "完整运营报告生成失败：" + str(result.get("error", "")),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _analyze_hot_questions(self, period: str) -> Dict[str, Any]:  # 热门问题分析
        """分析热门问题 - 调用Ops Agent"""
        logger.info(f"[AdminCopilotAgent] Analyzing hot questions, period: {period}")
        result = self.ops_agent.analyze("hot_questions", period=period)  # 委托给运营分析 Agent
        if result.get("success"):
            return {
                "answer": result.get("answer", ""),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})
            }
        else:
            return {
                "answer": "热门问题分析失败：" + str(result.get("error", "")),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _analyze_knowledge_growth(self, period: str) -> Dict[str, Any]:  # 知识库增长趋势分析
        """分析知识库增长趋势 - 调用Ops Agent"""
        logger.info(f"[AdminCopilotAgent] Analyzing knowledge growth, period: {period}")
        result = self.ops_agent.analyze("knowledge_growth", period=period)  # 委托给运营分析 Agent
        if result.get("success"):
            return {
                "answer": result.get("answer", ""),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})
            }
        else:
            return {
                "answer": "知识库增长趋势分析失败：" + str(result.get("error", "")),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _analyze_agent_success_rate(self, period: str) -> Dict[str, Any]:  # Agent 成功率分析
        """分析Agent成功率 - 调用Ops Agent"""
        logger.info(f"[AdminCopilotAgent] Analyzing agent success rate, period: {period}")
        result = self.ops_agent.analyze("agent_success_rate", period=period)  # 委托给运营分析 Agent
        if result.get("success"):
            return {
                "answer": result.get("answer", ""),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})
            }
        else:
            return {
                "answer": "Agent成功率分析失败：" + str(result.get("error", "")),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }

    def _analyze_tool_call_failures(self) -> Dict[str, Any]:  # 工具调用失败排行分析
        """分析工具调用失败排行 - 调用Ops Agent"""
        logger.info("[AdminCopilotAgent] Analyzing tool call failures")
        result = self.ops_agent.analyze("tool_call_failures")  # 委托给运营分析 Agent
        if result.get("success"):
            return {
                "answer": result.get("answer", ""),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "data": result.get("data", {})
            }
        else:
            return {
                "answer": "工具调用失败分析失败：" + str(result.get("error", "")),
                "sources": [],
                "has_sources": False,
                "task_type": "admin_copilot",
                "error": True
            }