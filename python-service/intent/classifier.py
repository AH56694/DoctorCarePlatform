"""统一意图分类器 - 使用LLM进行意图识别，关键词匹配作为fallback"""  # 模块文档字符串

import re  # 导入正则表达式模块，用于字符串匹配和替换
import json  # 导入 JSON 模块，用于解析 JSON 字符串
from enum import Enum  # 导入枚举基类，用于定义一组命名常量
from dataclasses import dataclass  # 导入 dataclass 装饰器
from typing import Optional, Dict, ClassVar  # 导入类型注解：Optional（可选类型）、Dict（字典类型）、ClassVar（类变量类型注解，表示该属性属于类而非实例，类似 Java 的 static）
import logging  # 导入日志模块

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器


class IntentType(Enum):  # 意图类型枚举类，继承自 Enum，类似 Java 的 enum IntentType {...}
    """意图类型枚举"""  # 类的文档字符串
    CHITCHAT = "chitchat"  # 闲聊意图
    KNOWLEDGE_QA = "knowledge_qa"  # 知识问答意图
    ADMIN_OPERATION = "admin_operation"  # 管理操作意图
    KNOWLEDGE_INSPECTION = "knowledge_inspection"  # 知识巡检意图
    IDENTITY_QUERY = "identity_query"  # 身份查询意图
    UNKNOWN = "unknown"  # 未知意图

    @classmethod
    def from_value(cls, intent_str: str) -> "IntentType":
        """
        根据字符串 value 查找对应的枚举成员，找不到返回 UNKNOWN
        等价于：next((x for x in IntentType if x.value == intent_str), IntentType.UNKNOWN)
        """
        return next((x for x in cls if x.value == intent_str), cls.UNKNOWN)


@dataclass  # @dataclass 装饰器，自动生成 __init__ 等方法
class IntentResult:  # 意图识别结果数据类
    """意图识别结果"""  # 类的文档字符串
    intent: IntentType  # 识别到的意图类型
    confidence: float  # 置信度（0.0-1.0）
    reasoning: str  # 判断理由
    requires_clarification: bool = False  # 是否需要向用户澄清，默认 False
    clarification_prompt: Optional[str] = None  # 澄清提示语，默认 None


class IntentClassifier:  # 统一意图分类器类，优先使用 LLM，LLM 不可用时 fallback 到关键词匹配
    """统一意图分类器 - 优先使用LLM，fallback到关键词匹配"""  # 类的文档字符串

    def __init__(self):  # 构造函数
        self._llm_service = None  # LLM 服务的缓存，初始为 None，延迟加载

        # 闲聊关键词库（fallback用）
        self.chitchat_keywords = [  # 闲聊关键词列表
            # 问候类
            "你好", "您好", "hello", "hi", "早上好", "下午好", "晚上好", "嗨", "嘿",  # 问候语
            # 告别类
            "谢谢", "感谢", "多谢", "再见", "拜拜", "拜拜咯", "下次见",  # 告别语
            # 身份询问类（针对系统）
            "你叫什么", "你是谁", "你是什么", "你的名字", "你从哪来",  # 身份相关问题
            # 日常闲聊类
            "讲个笑话", "说个故事", "聊聊天", "有空吗", "最近怎么样", "最近如何",  # 日常聊天
            "在干嘛", "在做什么", "忙吗", "累不累",  # 日常问候
            # 时间天气类（无法获取真实数据）
            "天气", "下雨", "晴天", "温度", "几点", "现在几点", "时间", "日期", "今天几号",  # 时间天气
            # 娱乐类
            "笑话", "搞笑", "有趣", "好玩", "电影", "音乐", "歌曲",  # 娱乐相关
            # 生活类
            "好吃", "美食", "餐厅", "好玩", "旅游", "景点",  # 生活相关
            # 情感类
            "开心", "高兴", "难过", "伤心", "郁闷", "不爽",  # 情感表达
            # 确认类
            "可以吗", "行吗", "好吗", "对不对", "是不是", "会不会",  # 确认性问题
        ]

        # 管理助手关键词库（fallback用）
        self.admin_keywords = [  # 管理操作关键词列表
            "管理", "后台", "运营", "统计", "报表", "仪表盘",  # 后台管理
            "用户", "会员", "注册", "活跃", "用户分析",  # 用户管理
            "未命中", "没有答案", "回答不了", "未知问题",  # 问题管理
            "知识巡检", "文档检查", "质量检测", "过期",  # 知识管理
            "热门问题", "问答统计", "使用率",  # 数据统计
            # P4-3 Ops Agent新增
            "知识缺口", "缺口分析", "运营报告", "运营分析",  # 运营分析
            "日志分析", "运营建议", "后台建议",  # 运营建议
            "活跃用户", "活跃度", "用户活动",  # 用户活跃度
        ]

        # 知识巡检关键词库（fallback用）
        self.inspection_keywords = [  # 知识巡检关键词列表
            "巡检", "检查", "检测", "审查",  # 检查相关
            "重复文档", "重复", "一样", "相同",  # 重复检测
            "低质量", "质量差", "片段", "内容短", "内容长",  # 质量检查
            "过期", "陈旧", "太久", "未更新",  # 时效检查
            "无人访问", "没人看", "没人查", "访问量",  # 访问统计
            "知识库健康", "知识库状态", "文档状态",  # 健康状态
        ]

        # 专业问答关键词库（fallback用）
        self.knowledge_qa_keywords = [  # 知识问答关键词列表
            # 数据库相关（重要！）
            "mysql", "oracle", "postgresql", "mongodb", "redis", "elasticsearch",  # 数据库名称
            "sql", "nosql", "关系型", "非关系型", "数据表", "索引", "事务", "锁", "并发",  # 数据库概念
            "封锁协议", "一级封锁协议", "二级封锁协议", "三级封锁协议",  # 数据库协议
            "并发控制", "隔离级别", "可重复读", "脏读", "不可重复读", "丢失修改",  # 并发控制
            # 疑问词
            "什么", "怎么", "如何", "为什么", "哪个", "哪里", "谁", "多少", "几", "何时", "怎样",  # 疑问词
            # 技术类
            "编程", "代码", "算法", "数据结构", "数据库", "网络", "安全", "加密", "协议",  # 技术基础
            "人工智能", "机器学习", "深度学习", "神经网络", "大模型", "LLM", "RAG", "AGI",  # AI 相关
            "java", "python", "javascript", "js", "c++", "go", "rust", "typescript", "php", "ruby",  # 编程语言
            "spring", "django", "flask", "react", "vue", "angular", "nodejs", "node.js",  # 框架
            # 概念类
            "原理", "机制", "工作原理", "实现原理", "概念", "定义", "术语", "解释", "说明",  # 概念解释
            "是什么", "什么意思", "指什么",  # 定义类
            # 方法类
            "步骤", "流程", "方法", "技巧", "策略", "方案", "思路",  # 方法相关
            "怎么做", "如何实现", "如何处理", "如何解决",  # 操作类
            # 比较类
            "比较", "对比", "区别", "差异", "不同", "优势", "缺点", "优缺点",  # 比较类
            "哪个好", "有什么区别", "有什么不同",  # 对比类
            # 应用类
            "应用", "用途", "使用场景", "案例", "例子", "实例",  # 应用类
            "可以用在", "适用于", "用于",  # 用途类
            # 技术概念
            "架构", "设计模式", "微服务", "分布式", "集群", "容器", "docker", "k8s", "kubernetes",  # 架构相关
            "缓存", "队列", "消息", "api", "rest", "rpc", "grpc", "websocket",  # 中间件
            "前端", "后端", "全栈", "运维", "DevOps", "CI/CD",  # 开发领域
            # 其他技术领域
            "区块链", "物联网", "云计算", "边缘计算", "5G", "大数据", "数据分析",  # 新技术
            "机器视觉", "自然语言处理", "NLP", "CV", "语音识别",  # AI 子领域
        ]

        # 情感分析词汇（fallback用）
        self.emotion_keywords = [  # 情感关键词列表
            "哈哈", "呵呵", "嘿嘿", "开心", "高兴", "难过", "伤心", "郁闷", "烦",  # 情绪词
            "累", "困", "饿", "渴", "舒服", "不爽", "真好", "太棒了", "不错",  # 感受词
        ]

    @property  # @property 装饰器，将方法变为属性访问
    def llm_service(self):  # 延迟加载 LLM 服务
        """延迟加载LLM服务"""  # 方法文档字符串
        if self._llm_service is None:  # 如果尚未加载
            try:  # try-except 处理加载失败
                from core.llm import llm_service  # 延迟导入 LLM 服务
                self._llm_service = llm_service  # 缓存 LLM 服务实例
            except Exception as e:  # 导入失败
                logger.warning(f"Failed to load LLM service: {e}")  # 记录警告
                self._llm_service = False  # 标记为不可用（使用 False 而非 None，防止重复尝试加载）
        return self._llm_service  # 返回 LLM 服务（可能是实例或 False）

    def classify(self, input_text: str, is_admin: bool = False) -> IntentResult:  # 统一意图分类入口方法
        """
        统一意图分类 - 优先使用LLM，fallback到关键词匹配

        Args:
            input_text: 用户输入文本
            is_admin: 是否为管理员

        Returns:
            IntentResult: 意图识别结果
        """  # 方法文档字符串（多行格式，描述参数和返回值）
        # 优先使用LLM进行意图识别
        if self.llm_service and self.llm_service.llm:  # 检查 LLM 服务是否可用（注意 llm_service 可能是 False）
            try:  # try-except 处理 LLM 调用失败
                result = self._classify_with_llm(input_text, is_admin)  # 使用 LLM 分类
                if result:  # 如果 LLM 返回了有效结果
                    return result  # 返回 LLM 分类结果
            except Exception as e:  # LLM 调用失败
                logger.warning(f"LLM classification failed, falling back to keywords: {e}")  # 记录警告

        # Fallback到关键词匹配
        return self._classify_with_keywords(input_text, is_admin)  # 使用关键词匹配作为兜底方案

    def _classify_with_llm(self, input_text: str, is_admin: bool = False) -> Optional[IntentResult]:  # 使用 LLM 进行意图识别
        """使用LLM进行意图识别"""  # 方法文档字符串
        from langchain_core.prompts import PromptTemplate  # 导入 LangChain 提示模板
        from langchain_core.output_parsers import StrOutputParser  # 导入字符串输出解析器

        # 构建意图识别的prompt
        intent_prompt = PromptTemplate.from_template(  # 从模板创建提示
            """
            你是一个意图识别系统。请分析用户输入，判断其意图类型。

            用户输入：{input_text}
            是否管理员：{is_admin}

            可选的意图类型：
            1. chitchat - 闲聊（问候、告别、日常聊天、情感表达、身份询问等）
            2. knowledge_qa - 知识问答（技术问题、概念解释、方法步骤、比较分析等）
            3. admin_operation - 管理操作（后台管理、数据统计、运营分析等，需要管理员权限）
            4. knowledge_inspection - 知识巡检（检查文档质量、重复、过期等）
            5. identity_query - 身份查询（询问系统身份、名称等）
            6. unknown - 无法确定

            请返回JSON格式：
            {{"intent": "意图类型", "confidence": 0.0-1.0, "reasoning": "判断理由"}}

            只返回JSON，不要其他内容。
            """
        )

        try:  # try-except 处理 LLM 调用和结果解析
            chain = intent_prompt | self.llm_service.llm | StrOutputParser()  # LangChain 管道操作符 | 串联：模板 -> LLM -> 解析器
            result_str = chain.invoke({  # 调用处理链
                "input_text": input_text,  # 用户输入
                "is_admin": "是" if is_admin else "否"  # 三元表达式：根据布尔值选择中文
            })

            # 解析JSON结果
            result_str = result_str.strip()  # 去除首尾空白
            # 提取JSON部分（处理可能的markdown代码块）
            json_match = re.search(r'\{[^}]+\}', result_str)  # re.search() 使用正则表达式搜索第一个匹配，\{[^}]+\} 匹配花括号内的内容
            if json_match:  # 如果找到 JSON
                result_json = json.loads(json_match.group())  # json.loads() 解析 JSON 字符串，.group() 获取匹配的文本
            else:  # 没有找到 JSON 格式
                result_json = json.loads(result_str)  # 尝试直接解析整个字符串

            intent_str = result_json.get("intent", "unknown")  # 获取意图类型字符串
            intent = IntentType.from_value(intent_str)  # 通过类方法将字符串转为枚举值
            confidence = float(result_json.get("confidence", 0.5))  # 获取置信度并转为浮点数
            reasoning = result_json.get("reasoning", "LLM判断")  # 获取判断理由

            return IntentResult(  # 返回意图识别结果
                intent=intent,  # 意图类型枚举
                confidence=confidence,  # 置信度
                reasoning=f"LLM: {reasoning}"  # 添加 "LLM:" 前缀标识来源
            )

        except Exception as e:  # 捕获所有异常
            logger.error(f"LLM intent classification error: {e}")  # 记录错误
            return None  # 返回 None 表示 LLM 分类失败

    def _classify_with_keywords(self, input_text: str, is_admin: bool = False) -> IntentResult:  # 使用关键词匹配进行意图识别（fallback 方案）
        """使用关键词匹配进行意图识别（fallback）"""  # 方法文档字符串
        lower_text = input_text.lower()  # 转为小写

        # 身份查询优先检查
        if any(keyword in lower_text for keyword in ["我是谁", "我叫什么", "我的名字", "我的身份"]):  # 检查身份查询关键词
            return IntentResult(  # 返回身份查询结果
                intent=IntentType.IDENTITY_QUERY,  # 意图为身份查询
                confidence=0.95,  # 高置信度
                reasoning="用户询问身份相关问题"  # 理由
            )

        # 去除中英文标点符号，避免 "你是谁？" 中 "？" 干扰分类
        clean_text = re.sub(r'[，。！？、；：""''【】《》（）\(\)\[\]\{\}<>\?\!\.\,\;\:\"\'\-\—\…\~\`]', '', lower_text)  # re.sub(正则, 替换, 原字符串) 去除所有标点符号

        # 计算各类关键词命中数量（使用去除标点后的文本）
        chitchat_score = sum(1 for kw in self.chitchat_keywords if kw in clean_text)  # 计算闲聊关键词命中数
        knowledge_score = sum(1 for kw in self.knowledge_qa_keywords if kw in clean_text)  # 计算知识问答关键词命中数
        admin_score = sum(1 for kw in self.admin_keywords if kw in clean_text)  # 计算管理关键词命中数
        inspection_score = sum(1 for kw in self.inspection_keywords if kw in clean_text)  # 计算巡检关键词命中数
        emotion_score = sum(1 for kw in self.emotion_keywords if kw in clean_text)  # 计算情感关键词命中数

        logger.debug(f"[IntentClassifier] Scores - chitchat:{chitchat_score}, knowledge:{knowledge_score}, admin:{admin_score}, inspection:{inspection_score}")  # 记录各分类得分

        # 管理员模式：优先处理管理相关任务
        if is_admin:  # 如果是管理员模式
            # 知识巡检优先级最高
            if inspection_score > 0:  # 如果命中巡检关键词
                return IntentResult(  # 返回巡检结果
                    intent=IntentType.KNOWLEDGE_INSPECTION,  # 意图为知识巡检
                    confidence=min(0.95, 0.6 + inspection_score * 0.1),  # min() 取最小值，置信度随命中数递增但有上限
                    reasoning=f"管理员模式，命中{inspection_score}个巡检关键词"  # 理由
                )
            # 管理助手
            if admin_score > 0:  # 如果命中管理关键词
                # 如果技术词汇更多，可能是知识问答
                if knowledge_score >= admin_score:  # 如果技术词不比管理词少
                    return IntentResult(  # 返回知识问答结果
                        intent=IntentType.KNOWLEDGE_QA,  # 意图为知识问答
                        confidence=min(0.95, 0.5 + knowledge_score * 0.15),  # 置信度
                        reasoning=f"管理员模式，但技术词更多（{knowledge_score} vs {admin_score}）"  # 理由
                    )
                return IntentResult(  # 返回管理操作结果
                    intent=IntentType.ADMIN_OPERATION,  # 意图为管理操作
                    confidence=min(0.9, 0.5 + admin_score * 0.1),  # 置信度
                    reasoning=f"管理员模式，命中{admin_score}个管理关键词"  # 理由
                )

        # 知识巡检（管理员和普通用户都可以触发）
        if inspection_score > 0 and inspection_score >= knowledge_score:  # 如果命中巡检词且不少于知识词
            return IntentResult(  # 返回巡检结果
                intent=IntentType.KNOWLEDGE_INSPECTION,  # 意图为知识巡检
                confidence=min(0.9, 0.6 + inspection_score * 0.1),  # 置信度
                reasoning=f"命中{inspection_score}个巡检关键词"  # 理由
            )

        # 技术问题优先判定为知识问答
        if knowledge_score >= 2:  # 如果命中 2 个及以上知识关键词
            return IntentResult(  # 返回知识问答结果
                intent=IntentType.KNOWLEDGE_QA,  # 意图为知识问答
                confidence=min(0.95, 0.5 + knowledge_score * 0.15),  # 置信度
                reasoning=f"命中{knowledge_score}个知识关键词"  # 理由
            )

        # 闲聊判断（基于多个因素）
        if chitchat_score > 0 or emotion_score > 0:  # 如果命中闲聊或情感关键词
            # 如果文本较短且包含闲聊词汇
            if len(input_text.strip()) < 15:  # 短文本（少于15字符）
                # 包含技术词汇则优先知识问答（技术词汇权重更高）
                if knowledge_score > chitchat_score:  # 如果技术词更多
                    return IntentResult(  # 返回知识问答结果
                        intent=IntentType.KNOWLEDGE_QA,  # 意图
                        confidence=min(0.9, 0.5 + knowledge_score * 0.15),  # 置信度
                        reasoning=f"短文本但技术词更多（{knowledge_score} vs {chitchat_score}）"  # 理由
                    )
                # 包含管理词汇则优先管理操作
                if admin_score > 0:  # 如果有管理关键词
                    return IntentResult(  # 返回管理操作结果
                        intent=IntentType.ADMIN_OPERATION,  # 意图
                        confidence=min(0.9, 0.5 + admin_score * 0.1),  # 置信度
                        reasoning=f"短文本，命中{admin_score}个管理关键词"  # 理由
                    )
                return IntentResult(  # 返回闲聊结果
                    intent=IntentType.CHITCHAT,  # 意图为闲聊
                    confidence=min(0.9, 0.5 + chitchat_score * 0.1),  # 置信度
                    reasoning=f"短文本，命中{chitchat_score}个闲聊关键词"  # 理由
                )
            # 长文本：如果闲聊词和技术词都多，取分值高的
            if knowledge_score > chitchat_score:  # 如果技术词比闲聊词多
                return IntentResult(  # 返回知识问答结果
                    intent=IntentType.KNOWLEDGE_QA,  # 意图
                    confidence=min(0.9, 0.5 + knowledge_score * 0.15),  # 置信度
                    reasoning=f"长文本，技术词更多（{knowledge_score} vs {chitchat_score}）"  # 理由
                )
            # 包含管理词汇则优先管理操作
            if admin_score > 0:  # 如果有管理关键词
                return IntentResult(  # 返回管理操作结果
                    intent=IntentType.ADMIN_OPERATION,  # 意图
                    confidence=min(0.9, 0.5 + admin_score * 0.1),  # 置信度
                    reasoning=f"长文本，命中{admin_score}个管理关键词"  # 理由
                )
            return IntentResult(  # 返回闲聊结果
                intent=IntentType.CHITCHAT,  # 意图为闲聊
                confidence=min(0.85, 0.5 + chitchat_score * 0.1),  # 置信度
                reasoning=f"长文本，闲聊词更多（{chitchat_score} vs {knowledge_score}）"  # 理由
            )

        # 短文本处理（没有任何关键词命中）
        if len(input_text.strip()) < 10:  # 如果文本很短（少于10字符）
            # 检查是否包含管理关键词
            if admin_score > 0:  # 如果有管理关键词
                return IntentResult(  # 返回管理操作结果
                    intent=IntentType.ADMIN_OPERATION,  # 意图
                    confidence=min(0.85, 0.5 + admin_score * 0.1),  # 置信度
                    reasoning=f"短文本，命中{admin_score}个管理关键词"  # 理由
                )
            # 检查是否包含疑问词
            question_words = ["什么", "怎么", "如何", "为什么", "哪个", "哪里", "谁", "多少", "?", "？"]  # 疑问词列表
            if any(kw in clean_text for kw in question_words):  # 如果包含疑问词
                return IntentResult(  # 返回知识问答结果
                    intent=IntentType.KNOWLEDGE_QA,  # 意图
                    confidence=0.6,  # 较低置信度
                    reasoning="短文本包含疑问词"  # 理由
                )
            # 检查是否包含中文字符
            has_chinese = bool(re.search(r'[一-鿿]', input_text))  # 正则匹配中文字符范围，bool() 将匹配结果转为布尔值
            if has_chinese:  # 如果包含中文
                # 有中文但无关键词，视为闲聊
                return IntentResult(  # 返回闲聊结果
                    intent=IntentType.CHITCHAT,  # 意图为闲聊
                    confidence=0.5,  # 低置信度
                    reasoning="短文本默认为闲聊"  # 理由
                )
            # 无中文且无关键词，返回UNKNOWN
            return IntentResult(  # 返回未知结果
                intent=IntentType.UNKNOWN,  # 意图为未知
                confidence=0.5,  # 置信度
                reasoning="无法确定意图类型"  # 理由
            )

        # 有一个技术关键词就判定为知识问答
        if knowledge_score >= 1:  # 如果至少命中 1 个知识关键词
            return IntentResult(  # 返回知识问答结果
                intent=IntentType.KNOWLEDGE_QA,  # 意图
                confidence=min(0.85, 0.5 + knowledge_score * 0.15),  # 置信度
                reasoning=f"命中{knowledge_score}个知识关键词"  # 理由
            )

        # 默认是知识问答
        return IntentResult(  # 默认返回知识问答结果
            intent=IntentType.KNOWLEDGE_QA,  # 意图为知识问答
            confidence=0.5,  # 低置信度（不确定）
            reasoning="默认为知识问答"  # 理由
        )

    def get_keyword_stats(self) -> dict:  # 获取各类关键词数量统计（用于调试和分析）
        """获取各类关键词数量统计（用于调试和分析）"""  # 方法文档字符串
        return {  # 返回统计字典
            "chitchat_keywords": len(self.chitchat_keywords),  # 闲聊关键词数量
            "knowledge_qa_keywords": len(self.knowledge_qa_keywords),  # 知识问答关键词数量
            "admin_keywords": len(self.admin_keywords),  # 管理关键词数量
            "inspection_keywords": len(self.inspection_keywords),  # 巡检关键词数量
            "emotion_keywords": len(self.emotion_keywords),  # 情感关键词数量
        }
