from typing import Dict, Any, List, Optional, Tuple  # 导入类型注解：Dict（字典类型）、Any（任意类型）、List（列表类型）、Optional（可选类型）、Tuple（元组类型，类似 Java 的 Pair/Tuple）
from agent.state import AgentState, AgentStep, StepType, TerminationCondition, IntermediateConclusion  # 从 agent.state 模块导入 Agent 状态相关的类
from intent.classifier import IntentClassifier, IntentType, IntentResult  # 从意图分类器模块导入：IntentClassifier（意图分类器）、IntentType（意图类型枚举）、IntentResult（意图识别结果）
from dataclasses import dataclass  # 导入 dataclass 装饰器，自动生成 __init__ 等方法
from core.config import config
import time  # 导入 time 模块
import logging  # 导入 logging 模块

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器


class QuestionType:  # 问题类型常量类，使用类属性定义常量（非枚举，因为只需要字符串值）
    """问题类型枚举"""  # 类的文档字符串
    TECHNICAL = "technical"  # 技术类问题
    PROFESSIONAL = "professional"  # 专业类问题（法律、金融等）
    LIFE = "life"  # 生活类问题
    OPINION = "opinion"  # 观点类问题
    GREETING = "greeting"  # 问候类
    UNKNOWN = "unknown"  # 未知类型


@dataclass  # @dataclass 装饰器，自动生成构造函数和 __repr__ 等方法
class QuestionClassification:  # 问题分类结果数据类
    """问题分类结果"""  # 类的文档字符串
    question_type: str  # 问题类型
    confidence: float  # 分类置信度（0.0-1.0）
    keywords: List[str]  # 匹配到的关键词列表
    should_return_sources: bool  # 是否应该返回引用来源


@dataclass  # @dataclass 装饰器
class RewriteResult:  # 问题改写结果数据类
    """问题改写结果"""  # 类的文档字符串
    original_question: str  # 原始问题
    rewritten_question: str  # 改写后的问题
    rewrite_type: str  # 改写类型（"semantic" 语义改写 或 "simple" 简单替换）
    confidence: float  # 改写置信度


@dataclass  # @dataclass 装饰器
class RetrievalResult:  # 检索结果数据类
    """检索结果"""  # 类的文档字符串
    chunks: List[Any]  # 检索到的文档片段列表
    scores: List[float]  # 对应的相似度分数列表
    is_sufficient: bool  # 检索结果是否充分
    reasoning: str  # 判断理由
    coverage: float  # 覆盖度


@dataclass  # @dataclass 装饰器
class SufficiencyResult:  # 检索充分性判断结果数据类
    """结果充分性判断"""  # 类的文档字符串
    is_sufficient: bool  # 是否充分
    confidence: float  # 置信度
    reasoning: str  # 判断理由
    missing_aspects: List[str]  # 缺失的方面
    suggestions: List[str]  # 改进建议


class Planner:  # 任务规划器类，负责分析任务、规划执行步骤、判断终止条件
    """任务规划器 - 负责分析任务、规划步骤、判断状态"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self.classifier = IntentClassifier()  # 创建意图分类器实例

    def recognize_intent(self, state: AgentState) -> IntentResult:  # 意图识别方法，委托给分类器
        """意图识别 - 委托给统一分类器"""  # 方法文档字符串
        question = state.original_input or ""  # 获取用户原始输入，如果为 None 则使用空字符串（Python 的 or 短路特性）
        return self.classifier.classify(question)  # 调用分类器的 classify 方法进行意图识别

    def classify_question(self, question: str) -> QuestionClassification:  # 问题分类方法
        """问题分类"""  # 方法文档字符串
        lower_question = question.lower()  # 转为小写，用于不区分大小写的关键词匹配

        technical_keywords = ["编程", "代码", "算法", "数据库", "网络", "安全", "加密", "协议", "人工智能", "机器学习", "深度学习"]  # 技术类关键词列表
        professional_keywords = ["法律", "法规", "政策", "制度", "经济", "金融", "商业", "管理", "营销", "教育", "培训", "课程"]  # 专业类关键词列表
        life_keywords = ["天气", "美食", "旅游", "电影", "音乐", "健康", "健身", "感情", "购物"]  # 生活类关键词列表

        found_technical = [kw for kw in technical_keywords if kw in lower_question]  # 列表推导式：从技术关键词中筛选出在问题中出现的关键词，类似 Java Stream 的 filter
        found_professional = [kw for kw in professional_keywords if kw in lower_question]  # 筛选专业关键词
        found_life = [kw for kw in life_keywords if kw in lower_question]  # 筛选生活关键词

        if found_technical:  # 如果匹配到技术关键词
            return QuestionClassification(  # 返回技术类问题分类结果
                question_type=QuestionType.TECHNICAL,  # 问题类型为技术类
                confidence=0.85,  # 置信度 0.85
                keywords=found_technical,  # 匹配到的关键词
                should_return_sources=True  # 技术类问题需要返回引用来源
            )

        if found_professional:  # 如果匹配到专业关键词
            return QuestionClassification(  # 返回专业类问题分类结果
                question_type=QuestionType.PROFESSIONAL,  # 问题类型为专业类
                confidence=0.80,  # 置信度 0.80
                keywords=found_professional,  # 匹配到的关键词
                should_return_sources=True  # 专业类问题需要返回引用来源
            )

        if found_life:  # 如果匹配到生活关键词
            return QuestionClassification(  # 返回生活类问题分类结果
                question_type=QuestionType.LIFE,  # 问题类型为生活类
                confidence=0.75,  # 置信度 0.75
                keywords=found_life,  # 匹配到的关键词
                should_return_sources=False  # 生活类问题不需要返回引用来源
            )

        if any(kw in lower_question for kw in ["怎么", "如何", "为什么", "什么"]):  # any() 判断是否包含疑问词
            return QuestionClassification(  # 返回技术类问题分类结果（默认疑问词归类为技术类）
                question_type=QuestionType.TECHNICAL,  # 问题类型为技术类
                confidence=0.60,  # 置信度较低 0.60
                keywords=["疑问词"],  # 关键词标记为"疑问词"
                should_return_sources=True  # 需要返回来源
            )

        return QuestionClassification(  # 默认返回未知类型
            question_type=QuestionType.UNKNOWN,  # 问题类型为未知
            confidence=0.5,  # 置信度 0.5
            keywords=[],  # 无关键词
            should_return_sources=False  # 不返回来源
        )

    def check_clarification_needed(self, state: AgentState, intent: IntentResult) -> Tuple[bool, Optional[str]]:  # 判断是否需要向用户澄清问题
        """判断是否需要澄清"""  # 方法文档字符串
        question = state.original_input or ""  # 获取原始输入

        if intent.requires_clarification:  # 如果意图识别结果标记需要澄清
            return True, intent.clarification_prompt  # 返回需要澄清标志和澄清提示语

        vague_indicators = ["那个", "它", "这个", "他", "她", "这事", "那事"]  # 模糊指代词列表
        if any(ind in question for ind in vague_indicators) and len(question) < 15:  # 短文本包含模糊词
            return True, "您是指什么？请提供更多具体信息。"  # 返回需要澄清和提示语

        if len(question) < 5:  # 问题太短（少于5个字符）
            return True, "您的问题太简略了，请详细描述一下您想了解的内容。"  # 返回需要澄清和提示语

        return False, None  # 不需要澄清

    def rewrite_question(self, question: str, conversation_context: str = "",  # 问题改写方法
                         rewrite_type: str = "semantic") -> RewriteResult:  # 参数：原始问题、对话上下文、改写类型
        """问题改写 - LLM 语义改写，失败时 fallback 到简单替换"""  # 方法文档字符串
        if rewrite_type == "simple":  # 如果指定使用简单替换
            return self._rewrite_simple(question)  # 直接调用简单改写方法

        # 尝试 LLM 语义改写
        llm = self._get_llm()  # 获取 LLM 实例
        if llm:  # 如果 LLM 可用
            try:  # try-except 异常处理
                return self._rewrite_with_llm(question, conversation_context, llm)  # 使用 LLM 进行语义改写
            except Exception as e:  # 捕获所有异常
                logger.warning(f"LLM rewrite failed, falling back to simple: {e}")  # 记录警告日志

        return self._rewrite_simple(question)  # LLM 不可用或失败时，fallback 到简单替换

    def _get_llm(self):  # 延迟获取 LLM 实例，下划线前缀表示内部方法
        """延迟获取 LLM 实例"""  # 方法文档字符串
        if not hasattr(self, '_llm'):  # hasattr() 检查对象是否有指定属性，类似 Java 的反射字段检查
            try:  # try-except 处理导入失败的情况
                from core.llm import llm_service  # 延迟导入 LLM 服务，避免循环依赖
                self._llm = llm_service  # 使用统一服务，包含 Ollama/OpenAI-compatible 降级链
            except Exception:  # 导入失败
                self._llm = None  # 设为 None 表示不可用
        return self._llm  # 返回 LLM 实例

    def _rewrite_with_llm(self, question: str, conversation_context: str, llm) -> RewriteResult:  # 使用 LLM 进行语义改写
        """LLM 语义改写"""  # 方法文档字符串
        prompt = """请对以下用户问题进行改写，目标是提升知识库检索的召回率。

改写规则：
1. 补全省略的主语/宾语
2. 将口语化表达转为书面化
3. 将代词替换为具体指代（结合上下文）
4. 保留原始意图，不要改变问题含义

对话上下文：{conversation_context}

用户问题：{question}

请直接输出改写后的问题，不要解释。""".format(
            question=question,
            conversation_context=conversation_context or "无",
        )

        if llm.llm:
            rewritten = llm.generate(prompt, temperature=0.1, max_tokens=160).strip()
        else:
            rewritten = llm._generate_with_fallback_models(prompt, temperature=0.1, max_tokens=160)
            if not rewritten:
                raise RuntimeError("No generation model is available for semantic rewrite")
            rewritten = rewritten.strip()

        return RewriteResult(  # 返回改写结果
            original_question=question,  # 原始问题
            rewritten_question=rewritten,  # 改写后的问题
            rewrite_type="semantic",  # 改写类型为语义改写
            confidence=0.85  # 置信度
        )

    def _rewrite_simple(self, question: str) -> RewriteResult:  # 简单的问题改写（fallback 方案）
        """简单替换（fallback）"""  # 方法文档字符串
        rewritten = question.strip()  # 去除首尾空白
        if "？" in rewritten:  # 如果包含中文问号
            rewritten = rewritten.replace("？", "?")  # 替换为英文问号
        if "!" in rewritten:  # 如果包含英文感叹号
            rewritten = rewritten.replace("!", "。")  # 替换为句号
        return RewriteResult(  # 返回改写结果
            original_question=question,  # 原始问题
            rewritten_question=rewritten,  # 改写后的问题
            rewrite_type="simple",  # 改写类型为简单替换
            confidence=0.6  # 置信度较低
        )

    def evaluate_retrieval_sufficiency(self, chunks, question, scores=None) -> SufficiencyResult:
        """Preliminary relevance gate; the loop separately validates semantic evidence.

        A similarity score alone is not evidence of coverage. Unknown scores are
        kept unknown and require the semantic evaluator to establish sufficiency.
        """
        import math
        import re

        def terms(text):
            words = set(re.findall(r"[a-zA-Z]{2,}", text.lower()))
            for phrase in re.findall(r"[\u4e00-\u9fff]+", text):
                words.update(phrase[i:i + 2] for i in range(len(phrase) - 1))
            return words - {"什么", "怎么", "如何", "需要", "可以", "应该", "是否", "患者"}

        query_terms = terms(question)
        supported = 0
        for index, chunk in enumerate(chunks):
            content = (chunk.get("content") or chunk.get("page_content") or "") if isinstance(chunk, dict) else getattr(chunk, "page_content", "")
            score = (scores or [])[index] if index < len(scores or []) else None
            if (isinstance(score, (int, float)) and not isinstance(score, bool)
                    and math.isfinite(score) and score >= config.RAG_SIMILARITY_THRESHOLD
                    and query_terms.intersection(terms(str(content)))):
                supported += 1
        sufficient = supported > 0
        return SufficiencyResult(
            is_sufficient=sufficient, confidence=0.0,
            reasoning="通过初步相关性检查，仍需验证语义证据" if sufficient else "缺少有分数且与问题相关的证据",
            missing_aspects=[] if sufficient else ["可验证的相关证据"],
            suggestions=[] if sufficient else ["围绕缺失信息重新检索"],
        )

    def plan_steps(self, state: AgentState) -> List[str]:  # 根据意图规划执行步骤
        """规划执行步骤"""  # 方法文档字符串
        intent = self.recognize_intent(state)  # 先进行意图识别

        # 如果有会话ID，在开始时读取记忆
        has_conversation = bool(state.conversation_id)  # bool() 将值转为布尔类型，None/空字符串为 False

        if intent.intent == IntentType.CHITCHAT:  # 如果意图是闲聊
            steps = []  # 初始化步骤列表
            if has_conversation:  # 如果有会话上下文
                steps.append("memory_read")  # 先读取记忆
            steps.append("answer_generation")  # 生成回答
            if has_conversation:  # 如果有会话上下文
                steps.append("memory_write")  # 写入记忆
            return steps  # 返回闲聊的步骤列表

        if intent.intent == IntentType.IDENTITY_QUERY:  # 如果意图是身份查询（如"你是谁"）
            steps = []
            if has_conversation:
                steps.append("memory_read")
            steps.append("identity_answer")
            if has_conversation:
                steps.append("memory_write")
            return steps

        if intent.intent == IntentType.KNOWLEDGE_QA:  # 如果意图是知识问答
            steps = []  # 初始化步骤列表
            if has_conversation:  # 如果有会话上下文
                steps.append("memory_read")  # 先读取记忆
            steps.append("question_rewrite")  # 问题改写
            if len(state.original_input or "") < 10:  # 如果问题很短（少于10个字符）
                steps.append("clarification")  # 可能需要澄清
            steps.extend([  # extend() 将列表中的所有元素追加到末尾，类似 Java 的 list.addAll()
                "knowledge_search",  # 知识检索
                "result_evaluation",  # 结果评估
                "answer_generation"  # 答案生成
            ])
            if has_conversation:  # 如果有会话上下文
                steps.append("memory_write")  # 写入记忆
            return steps  # 返回知识问答的步骤列表

        if intent.intent == IntentType.ADMIN_OPERATION:  # 如果意图是管理操作
            steps = ["admin_operation"]  # 管理操作步骤
            if has_conversation:  # 如果有会话上下文
                steps.append("memory_write")  # 写入记忆
            return steps  # 返回管理操作的步骤列表

        steps = []  # 默认步骤列表
        if has_conversation:  # 如果有会话上下文
            steps.append("memory_read")  # 读取记忆
        steps.extend(["question_rewrite", "knowledge_search", "answer_generation"])  # 添加默认步骤
        if has_conversation:  # 如果有会话上下文
            steps.append("memory_write")  # 写入记忆
        return steps  # 返回默认步骤列表

    def should_terminate(self, state: AgentState) -> Tuple[bool, str]:  # 判断是否应该终止执行
        """判断是否应该终止"""  # 方法文档字符串
        reason = TerminationCondition.get_termination_reason(state)  # 获取终止原因
        return TerminationCondition.should_terminate(state), reason  # 返回元组：(是否终止, 原因)
