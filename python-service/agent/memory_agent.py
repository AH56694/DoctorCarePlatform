"""Memory Agent - 独立的记忆管理Agent"""  # 模块文档字符串

from typing import Dict, Any, Optional, List  # 导入类型注解：Dict（字典类型）、Any（任意类型）、Optional（可选类型）、List（列表类型）
from concurrent.futures import ThreadPoolExecutor
from tools.registry import tool_registry  # 从工具注册表模块导入工具注册表单例
from core.llm import LLMService  # 从 LLM 核心模块导入 LLM 服务类
from core.config import config
import logging  # 导入 logging 模块，用于日志记录
import json  # 导入 json 模块，用于 JSON 序列化和反序列化

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器
preference_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory-preference")


class MemoryAgent:  # 记忆管理 Agent 类，负责主动管理记忆生命周期
    """独立的记忆管理 Agent - 主动管理记忆生命周期"""  # 类的文档字符串

    # 压缩配置
    COMPRESS_THRESHOLD = config.MEMORY_COMPRESS_THRESHOLD
    KEEP_RECENT = config.MEMORY_KEEP_RECENT

    def __init__(self):  # 构造函数，self 类似 Java 的 this
        self.llm_service = LLMService()  # 创建 LLM 服务实例

    def load_memory(self, state) -> str:  # 加载记忆上下文，返回拼接好的上下文字符串
        """加载记忆上下文（会话记忆 + 用户画像）"""  # 方法文档字符串
        context_parts = []  # 初始化上下文片段列表

        # 1. 加载会话记忆
        if state.conversation_id and tool_registry.has_tool("conversation_memory_read"):  # 如果有会话 ID 且记忆读取工具可用
            try:  # try-except 异常处理
                history = tool_registry.invoke_tool(  # 通过工具注册表调用记忆读取工具
                    "conversation_memory_read",  # 工具名称
                    {  # 工具参数
                        "conversation_id": state.conversation_id,  # 会话 ID
                        "limit": 10  # 最多读取 10 条消息
                    },
                    run_id=state.run_id  # 传入运行 ID 用于追踪
                )
                messages = history.get("messages", [])  # 从返回结果中获取消息列表，如果键不存在则返回空列表
                if not messages and self._hydrate_conversation_memory(state.conversation_id):
                    history = tool_registry.invoke_tool(
                        "conversation_memory_read",
                        {"conversation_id": state.conversation_id, "limit": 10},
                        run_id=state.run_id,
                    )
                    messages = history.get("messages", [])
                if messages:  # 如果有历史消息
                    formatted = self._format_history(messages)  # 调用内部方法格式化消息
                    context_parts.append(formatted)  # 将格式化后的消息添加到上下文片段列表
                    logger.info(f"[{state.run_id}] MemoryAgent loaded {len(messages)} messages"  # 记录信息日志
                                f" (compressed: {history.get('compressed', False)})")  # 显示是否经过压缩
            except Exception as e:  # 捕获所有异常
                logger.warning(f"[{state.run_id}] MemoryAgent failed to load conversation: {e}")  # 记录警告日志

        # 2. 加载用户画像（如果有 user_id）
        if state.user_id:  # 如果有用户 ID
            user_profile = self._load_user_profile(state.user_id)  # 加载用户画像
            if user_profile:  # 如果成功加载用户画像
                context_parts.append(f"[用户画像] {json.dumps(user_profile, ensure_ascii=False)}")  # json.dumps() 将字典转为 JSON 字符串，ensure_ascii=False 允许中文直接输出

        context = "\n\n".join(context_parts) if context_parts else ""
        return self._limit_context(context)

    def save_memory(self, state, question: str, answer: str):  # 保存记忆（用户问题 + AI 回答 + 提取偏好）
        """保存记忆（用户问题 + AI回答 + 提取偏好）"""  # 方法文档字符串
        if not state.conversation_id:  # 如果没有会话 ID
            return  # 直接返回，不保存

        # 1. 写入用户问题
        if tool_registry.has_tool("conversation_memory_write"):  # 如果记忆写入工具可用
            try:  # try-except 异常处理
                tool_registry.invoke_tool(  # 调用记忆写入工具
                    "conversation_memory_write",  # 工具名称
                    {  # 工具参数
                        "conversation_id": state.conversation_id,  # 会话 ID
                        "role": "user",  # 角色：用户
                        "content": question  # 用户问题内容
                    },
                    run_id=state.run_id  # 运行 ID
                )
            except Exception as e:  # 捕获异常
                logger.warning(f"[{state.run_id}] MemoryAgent failed to write user message: {e}")  # 记录警告

        # 2. 写入 AI 回答
        if tool_registry.has_tool("conversation_memory_write"):  # 如果记忆写入工具可用
            try:  # try-except 异常处理
                tool_registry.invoke_tool(  # 调用记忆写入工具
                    "conversation_memory_write",  # 工具名称
                    {  # 工具参数
                        "conversation_id": state.conversation_id,  # 会话 ID
                        "role": "assistant",  # 角色：AI 助手
                        "content": answer  # AI 回答内容
                    },
                    run_id=state.run_id  # 运行 ID
                )
            except Exception as e:  # 捕获异常
                logger.warning(f"[{state.run_id}] MemoryAgent failed to write assistant message: {e}")  # 记录警告

        # 3. 异步提取用户偏好（不阻塞主流程）
        if state.user_id and config.MEMORY_EXTRACT_USER_PREFERENCES:
            preference_executor.submit(self._extract_user_preference, state, question, answer)

    def _load_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:  # 加载用户画像，下划线前缀表示内部方法
        """加载用户画像"""  # 方法文档字符串
        try:  # try-except 异常处理
            from core.mysql_client import user_memory_client  # 延迟导入 MySQL 客户端，避免循环依赖
            return user_memory_client.get_user_memory(user_id)  # 调用客户端获取用户记忆数据
        except Exception as e:  # 捕获异常
            logger.warning(f"Failed to load user profile: {e}")  # 记录警告日志
            return None  # 返回 None 表示加载失败

    def _hydrate_conversation_memory(self, conversation_id: str) -> bool:
        """Rebuild expired Redis memory from durable AI messages."""
        if not config.MEMORY_HYDRATE_FROM_MYSQL:
            return False
        try:
            from core.mysql_client import mysql_client
            from core.redis_client import redis_client

            rows = mysql_client.fetch_all(
                """
                SELECT sender, content
                FROM (
                    SELECT sender, content, created_at
                    FROM ai_messages
                    WHERE session_id = %s AND content <> ''
                    ORDER BY created_at DESC
                    LIMIT %s
                ) AS recent_messages
                ORDER BY created_at ASC
                """,
                (conversation_id, config.MEMORY_MAX_MESSAGES),
            )
            for row in rows:
                role = "assistant" if row.get("sender") in {"ai", "assistant"} else "user"
                content = str(row.get("content") or "").strip()
                if content:
                    redis_client.add_message(conversation_id, role, content)
            return bool(rows)
        except Exception as exc:
            logger.warning(f"Failed to hydrate conversation {conversation_id} from MySQL: {exc}")
            return False

    def _limit_context(self, context: str) -> str:
        if len(context) <= config.MEMORY_CONTEXT_MAX_CHARS:
            return context
        marker = "[较早上下文已截断]\n"
        tail_budget = max(0, config.MEMORY_CONTEXT_MAX_CHARS - len(marker))
        tail = context[-tail_budget:] if tail_budget else ""
        return (marker + tail)[:config.MEMORY_CONTEXT_MAX_CHARS]

    def _extract_user_preference(self, state, question: str, answer: str):  # 提取用户偏好（使用 LLM 分析问答内容）
        """异步提取用户偏好"""  # 方法文档字符串
        try:  # try-except 异常处理
            from core.mysql_client import user_memory_client  # 延迟导入 MySQL 客户端

            prompt = f"""分析以下问答，判断用户是否有明显的偏好特征。

用户问题：{question}
AI回答：{answer}

如果有，返回 JSON：{{"preference_style": "简洁/详细", "topics": ["主题1"]}}
如果没有明显偏好，返回：null
只返回 JSON 或 null，不要解释。"""  # f-string 多行字符串，构建 LLM 提示词。{{}} 在 f-string 中表示字面量花括号（转义）

            result = self.llm_service.chat(prompt)  # 调用 LLM 服务进行对话
            if result and result.strip() != "null":  # 如果结果非空且不是 "null"
                # 清理 markdown 代码块
                cleaned = result.strip()  # 去除首尾空白
                if cleaned.startswith("```"):  # 如果以 markdown 代码块标记开头
                    cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]  # split("\n", 1) 最多分割一次，取第二部分（去掉 ```json 行）
                    cleaned = cleaned.rsplit("```", 1)[0]  # rsplit 从右边分割，去掉结尾的 ```

                preference = json.loads(cleaned.strip())  # json.loads() 将 JSON 字符串解析为 Python 字典
                user_memory_client.update_user_memory(  # 更新用户记忆
                    state.user_id, "preference_style", preference,  # 用户ID、字段名、偏好值
                    source="agent", confidence=0.8  # 来源标记为 agent，置信度 0.8
                )
                logger.info(f"[{state.run_id}] Extracted user preference: {preference}")  # 记录提取结果
        except Exception as e:  # 捕获所有异常
            logger.debug(f"[{state.run_id}] Extract user preference failed: {e}")  # 静默失败，只记录调试级别日志

    def _format_history(self, messages: list) -> str:  # 格式化对话历史为文本
        """格式化对话历史"""  # 方法文档字符串
        if not messages:  # 如果消息列表为空
            return ""  # 返回空字符串

        formatted = []  # 初始化格式化后的消息列表
        for msg in messages:  # 遍历每条消息
            role = msg.get("role", "unknown")  # 获取角色，默认为 "unknown"
            content = msg.get("content", "")  # 获取内容，默认为空字符串
            if role == "system":  # 系统消息
                formatted.append(content)  # 直接添加内容
            elif role == "user":  # 用户消息
                formatted.append(f"用户: {content}")  # 添加 "用户:" 前缀
            elif role == "assistant":  # AI 回答
                formatted.append(f"AI: {content}")  # 添加 "AI:" 前缀
            else:  # 其他角色
                formatted.append(content)  # 直接添加内容

        return "\n".join(formatted)  # 将所有消息用换行符拼接成字符串
