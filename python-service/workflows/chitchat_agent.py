from typing import Dict, Any, Optional, Generator  # 导入类型提示（Dict 是字典类型，Any 是任意类型，Optional 表示可为 None，Generator 是生成器类型）
from core.llm import llm  # 从 core.llm 模块导入 LLM 实例（大语言模型服务）
from tools.registry import tool_registry  # 从 tools.registry 模块导入工具注册表（类似 Java 的 ServiceRegistry）
import logging  # 导入日志模块
import json  # 导入 JSON 序列化模块

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class ChitChatAgent:  # 定义闲聊 Agent 类
    """闲聊Agent - 专门处理日常对话和闲聊的工作流"""

    def __init__(self):  # 构造函数
        self.chitchat_prompts = {  # 初始化闲聊预设回复字典（键为类别，值为回复列表）
            "greeting": [  # 问候类预设回复
                "你好！很高兴见到你，有什么我可以帮助你的吗？",
                "您好！今天过得怎么样？有什么想聊的吗？",
                "Hi！有什么可以为你效劳的？",
            ],
            "thanks": [  # 感谢类预设回复
                "不客气！能帮到你我很开心！",
                "不用谢，这是我应该做的！",
                "不客气，随时为你服务！",
            ],
            "identity": [  # 身份询问类预设回复
                "我是你的AI知识助手，可以帮你回答问题、查阅资料，也可以陪你聊聊天。你想了解什么？",
                "我是AI知识库助手，专注于知识问答，同时也可以陪你聊聊日常。",
            ],
            "weather": [  # 天气类预设回复
                "很抱歉，我无法实时获取天气信息。不过你可以查看天气预报APP来了解天气情况。",
            ],
            "time": [  # 时间类预设回复
                f"很抱歉，我无法告诉你当前时间，请查看你的设备时钟。",  # f-string 格式化（这里无变量，仅为演示）
            ],
            "joke": [  # 笑话类预设回复
                "程序员最讨厌的季节是什么？是秋天！因为秋高气爽（bug少），但也会有很多落叶（bug）！",
                "你知道为什么程序员总是分不清万圣节和圣诞节吗？因为Oct 31 = Dec 25！",
                "为什么程序员喜欢黑暗模式？因为 Light attracts bugs！",
            ],
            "default": [  # 默认回复
                "哈哈，这个话题挺有意思的！你最近有什么新鲜事想分享吗？",
                "嗯嗯，我听着呢～还有什么想聊的吗？",
                "有意思！能跟我说说更多吗？",
            ]
        }

    def chat(self, question: str, conversation_id: Optional[str] = None,  # chat 方法，处理闲聊请求
             user_id: Optional[str] = None, context: str = "",
             **kwargs) -> Dict[str, Any]:  # **kwargs 接收额外的关键字参数
        """
        处理闲聊

        Args:
            question: 用户问题
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            **kwargs: 其他参数

        Returns:
            包含answer的字典
        """
        logger.info("AI request processing; content omitted")

        try:
            # 1. 读取会话记忆作为上下文
            conversation_history = ""  # 初始化对话历史为空字符串
            if conversation_id and tool_registry.has_tool("conversation_memory_read"):  # 如果有会话ID且工具注册表中存在会话记忆读取工具
                try:
                    history = tool_registry.invoke_tool(  # 调用工具注册表中的会话记忆读取工具
                        "conversation_memory_read",  # 工具名称
                        {  # 传入参数字典
                            "conversation_id": conversation_id,  # 会话ID
                            "limit": 10  # 最多读取10条历史消息
                        }
                    )
                    messages = history.get("messages", [])  # 从返回结果中获取消息列表，若无则返回空列表
                    if messages:  # 如果有历史消息
                        conversation_history = self._format_history(messages)  # 格式化历史消息为字符串
                        logger.info(f"[ChitChatAgent] Loaded {len(messages)} messages from memory")  # len() 获取列表长度
                except Exception as e:  # 捕获异常
                    logger.warning(f"[ChitChatAgent] Failed to read conversation memory: {e}")  # 记录警告日志

            # 2. 生成回复（带会话上下文）
            answer = self._generate_chitchat_response(question, conversation_history)  # 调用生成回复方法

            # 3. 写入会话记忆
            self._save_to_memory(conversation_id, question, answer)  # 保存当前对话到会话记忆

            return {  # 返回结果字典
                "answer": answer,  # 闲聊回复内容
                "sources": [],  # 闲聊无引用来源
                "has_sources": False,  # 标记无来源
                "task_type": "chitchat"  # 任务类型为闲聊
            }
        except Exception as e:
            logger.error(f"[ChitChatAgent] Error: {str(e)}")  # 记录错误日志
            return {  # 返回错误响应
                "answer": "抱歉，我现在状态不太好，稍后再聊吧。",  # 错误提示
                "sources": [],
                "has_sources": False,
                "task_type": "chitchat",
                "error": True  # 标记为错误
            }

    def _format_history(self, messages: list) -> str:  # _format_history 私有方法，格式化对话历史
        """格式化对话历史为上下文字符串"""
        if not messages:  # 如果消息列表为空（None、空列表 [] 都会被视为 False）
            return ""  # 返回空字符串

        formatted = []  # 初始化格式化后的消息列表
        for msg in messages:  # 遍历每条消息
            role = msg.get("role", "unknown")  # 获取消息角色（user/assistant/system），默认为 "unknown"
            content = msg.get("content", "")  # 获取消息内容，默认为空字符串
            if role == "system":  # 系统消息直接添加内容
                formatted.append(content)  # append() 向列表末尾添加元素（类似 Java 的 List.add()）
            elif role == "user":  # 用户消息添加前缀
                formatted.append(f"用户: {content}")
            elif role == "assistant":  # AI 消息添加前缀
                formatted.append(f"AI: {content}")

        return "\n".join(formatted)  # "\n".join() 将列表用换行符连接成字符串（类似 Java 的 String.join("\n", list)）

    def _save_to_memory(self, conversation_id: str, question: str, answer: str):
        """保存对话到会话记忆"""
        if not conversation_id or not tool_registry.has_tool("conversation_memory_write"):  # 如果没有会话ID或不存在写入工具
            return  # 直接返回，不保存
        try:
            tool_registry.invoke_tool(  # 调用工具保存用户消息
                "conversation_memory_write",
                {"conversation_id": conversation_id, "role": "user", "content": question}  # 写入用户问题
            )
            tool_registry.invoke_tool(  # 调用工具保存 AI 回复
                "conversation_memory_write",
                {"conversation_id": conversation_id, "role": "assistant", "content": answer}  # 写入 AI 回复
            )
            logger.info(f"[ChitChatAgent] Saved conversation to memory")
        except Exception as e:
            logger.warning(f"[ChitChatAgent] Failed to write conversation memory: {e}")

    def chat_stream(self, question: str, conversation_id: Optional[str] = None,
                    user_id: Optional[str] = None, context: str = "",
                    **kwargs) -> Generator[str, None, None]:  # 返回生成器，逐个产出字符串
        """
        流式处理闲聊

        Args:
            question: 用户问题
            conversation_id: 会话ID
            user_id: 用户ID
            context: 对话上下文
            **kwargs: 其他参数

        Yields:
            JSON格式的事件流
        """
        logger.info("AI request processing; content omitted")

        try:
            answer = self._generate_chitchat_response(question)  # 生成完整回复（注意流式模式下未传对话历史）

            for char in answer:  # 逐字符遍历回复内容（模拟流式输出效果）
                yield json.dumps({  # yield 产出 JSON 格式的 token 事件
                    "type": "token",  # 事件类型：文本 token
                    "content": char  # 单个字符
                })

            yield json.dumps({  # 产出结束事件
                "type": "end",  # 事件类型：结束
                "content": {  # 结束事件携带的完整内容
                    "answer": answer,  # 完整回复
                    "sources": [],  # 空来源列表
                    "task_type": "chitchat"  # 任务类型
                }
            })
        except Exception as e:
            logger.error(f"[ChitChatAgent] Stream error: {str(e)}")
            yield json.dumps({  # 产出错误事件
                "type": "error",  # 事件类型：错误
                "content": str(e)  # 错误信息
            })

    def _generate_chitchat_response(self, question: str, conversation_history: str = "") -> str:
        """
           生成闲聊回复（Hybrid Chitchat Response）。

           本方法根据用户意图的复杂度，动态选择响应策略以平衡性能与体验：

           策略 A：规则匹配（Rule-based）
               - 适用场景：高频寒暄（你好/谢谢）、事实查询（时间/日期）、身份确认。
               - 优势：响应极快（<1ms），无 Token 消耗，稳定性高。

           策略 B：大模型生成（LLM-based）
               - 适用场景：需要共情的情感对话、创意类请求（讲笑话）、开放式知识问答。
               - 优势：回复自然流畅，具备多轮对话的记忆与理解能力。

           参数:
               question: 用户当前的输入文本。
               conversation_history: 历史对话上下文（仅LLM场景使用）。

           返回:
               str: 生成的回复文本。
       """
        lower_question = question.lower()  # 将问题转为小写，便于不区分大小写匹配

        # 问候类 — 简短直接，不需要LLM
        if any(kw in lower_question for kw in ["你好", "您好", "hello", "hi", "早上好", "下午好", "晚上好", "嗨", "嘿"]):  # any() + 生成器表达式：检查问题中是否包含任意问候关键词
            return self.chitchat_prompts["greeting"][0]  # 返回第一个预设问候回复

        # 感谢类 — 简短直接，不需要LLM
        if any(kw in lower_question for kw in ["谢谢", "感谢", "多谢", "thanks", "thank you"]):
            return self.chitchat_prompts["thanks"][0]  # 返回第一个预设感谢回复

        # 身份询问类 — 简短直接，不需要LLM
        if any(kw in lower_question for kw in ["你叫什么", "你是谁", "你是什么", "你的名字", "你是机器人", "你是AI"]):
            return self.chitchat_prompts["identity"][0]  # 返回第一个预设身份回复

        # 以下场景需要理解能力，调LLM生成自然回复

        # "你知道X吗" 类 — 用LLM给出有内容的回复，而不是机械重定向
        if any(kw in lower_question for kw in ["你知道", "你了解", "你认识", "听说过", "你听过"]):
            return self._llm_chitchat(question, conversation_history)  # 调用 LLM 生成回复

        # 天气类 — 用LLM给出更自然的回复
        if any(kw in lower_question for kw in ["天气", "下雨", "晴天", "温度"]):
            return self._llm_chitchat(question, conversation_history)

        # 时间类
        if any(kw in lower_question for kw in ["几点", "时间", "日期", "今天是"]):
            return self.chitchat_prompts["time"][0]  # 返回预设时间回复

        # 笑话类 — 用LLM讲笑话，比预设的更有趣
        if any(kw in lower_question for kw in ["笑话", "讲个笑话", "笑", "搞笑"]):
            return self._llm_chitchat(question, conversation_history)

        # 日常闲聊类 — 用LLM自然回复
        if any(kw in lower_question for kw in ["在干嘛", "在做什么", "忙吗", "累不累", "无聊", "睡不着"]):
            return self._llm_chitchat(question, conversation_history)

        # 引导类 — 用LLM自然回复
        if any(kw in lower_question for kw in ["聊聊", "聊天", "陪我", "有空吗", "最近怎么样", "最近好吗"]):
            return self._llm_chitchat(question, conversation_history)

        # 情感类 — 用LLM给出有共情的回复
        if any(kw in lower_question for kw in ["开心", "高兴", "难过", "伤心", "郁闷", "烦", "累", "困", "饿"]):
            return self._llm_chitchat(question, conversation_history)

        # 确认/反问类
        if any(kw in lower_question for kw in ["可以吗", "行吗", "好吗", "对不对", "是不是", "会不会"]):
            return self._llm_chitchat(question, conversation_history)

        # 其他所有闲聊 — 调LLM生成自然回复
        return self._llm_chitchat(question, conversation_history)

    def _llm_chitchat(self, question: str, conversation_history: str = "") -> str:
        """调用LLM生成自然的闲聊回复"""
        try:
            # 构建上下文
            context_section = ""  # 初始化上下文部分为空
            if conversation_history:  # 如果有对话历史
                context_section = f"""  # 拼接历史上下文提示
对话历史：
{conversation_history}

请基于对话历史，理解上下文后回复用户。"""

            prompt = f"""你是一个友好、健谈的AI助手。请用自然、亲切的方式回复用户，就像朋友之间聊天一样。
回复要简短有趣，100字以内。不要说"你可以问我知识类问题"这种话。
{context_section}

用户说：{question}"""  # f-string 多行模板，构建完整的 LLM 提示词

            response = llm.generate(prompt, temperature=0.7, max_tokens=150)  # 调用 LLM 生成回复，temperature 控制随机性（0-1，越高越随机），max_tokens 限制最大输出长度
            return response.strip()  # .strip() 去除首尾空白字符（类似 Java 的 trim()）
        except:  # 裸 except（不推荐，但此处作为简单兜底）：捕获所有异常
            return self.chitchat_prompts["default"][0]  # LLM 调用失败时返回默认回复