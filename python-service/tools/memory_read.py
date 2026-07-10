from typing import Dict, Any, List  # 导入类型注解：Dict=字典，Any=任意类型，List=列表类型（类似 Java 的 List<?>）
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.config import config  # 导入全局配置单例
from core.redis_client import redis_client  # 导入 Redis 客户端单例（用于存储对话消息）
from core.llm import LLMService  # 导入 LLM（大语言模型）服务类

# 压缩阈值配置
COMPRESS_THRESHOLD = config.MEMORY_COMPRESS_THRESHOLD
KEEP_RECENT = config.MEMORY_KEEP_RECENT


class ConversationMemoryReadTool(Tool):  # 对话记忆读取工具，继承自 Tool 抽象基类
    """对话记忆读取工具（含上下文压缩）"""

    def __init__(self):  # 构造函数
        input_schema = ToolSchema(  # 定义输入参数 Schema
            properties={
                "conversation_id": SchemaProperty(  # 对话 ID 参数
                    type="string",  # 字符串类型
                    description="对话ID",  # 参数描述
                    required=True  # 必填
                ),
                "limit": SchemaProperty(  # 返回消息数量限制参数
                    type="number",  # 数字类型
                    description="返回消息数量限制",  # 参数描述
                    required=False,  # 非必填
                    default=10  # 默认返回10条
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果 Schema
            properties={
                "messages": SchemaProperty(  # 消息列表输出
                    type="array",  # 数组类型
                    description="对话消息列表",  # 描述
                    required=True  # 必填
                ),
                "conversation_id": SchemaProperty(  # 对话 ID 输出
                    type="string",  # 字符串类型
                    description="对话ID",  # 描述
                    required=True  # 必填
                ),
                "total_count": SchemaProperty(  # 总消息数输出
                    type="number",  # 数字类型
                    description="总消息数量",  # 描述
                    required=True  # 必填
                ),
                "compressed": SchemaProperty(  # 是否已压缩输出
                    type="boolean",  # 布尔类型
                    description="是否已压缩",  # 描述
                    required=False  # 非必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=10000,  # 超时时间10秒（压缩可能需要更长时间）
            max_retries=1,  # 最大重试1次
            permission="user",  # 用户级权限
            description="读取对话记忆"  # 工具描述
        )

        super().__init__(  # 调用父类构造函数（类似 Java 的 super()）
            name="conversation_memory_read",  # 工具名称
            description="读取对话记忆",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

        self.llm_service = LLMService()  # 初始化 LLM 服务实例，用于上下文压缩时调用大模型

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行对话记忆读取
        """执行对话记忆读取（含上下文压缩）"""
        conversation_id = parameters.get("conversation_id")  # 获取对话 ID
        limit = int(parameters.get("limit", 10))  # 获取消息数量限制，默认10

        config.logger.info(f"Reading conversation memory for ID: {conversation_id}")  # 记录读取日志

        # 获取消息总数
        total_count = redis_client.get_message_count(conversation_id)  # 从 Redis 获取该对话的消息总数

        if total_count == 0:  # 如果没有消息
            # 没有消息，返回空列表
            return {
                "messages": [],  # 空消息列表
                "conversation_id": conversation_id,  # 对话 ID
                "total_count": 0,  # 总数为0
                "compressed": False  # 未压缩
            }

        if total_count <= COMPRESS_THRESHOLD:  # 如果消息数不超过压缩阈值（10条）
            # 消息不多，直接返回最近的
            messages = redis_client.get_messages(conversation_id, limit)  # 从 Redis 获取最近 limit 条消息
            return {
                "messages": messages,  # 消息列表
                "conversation_id": conversation_id,  # 对话 ID
                "total_count": total_count,  # 总消息数
                "compressed": False  # 未压缩
            }

        # 超过阈值，触发压缩
        # 保留最近 N 轮完整对话
        recent_messages = redis_client.get_messages(conversation_id, KEEP_RECENT)  # 获取最近 KEEP_RECENT(5) 条消息

        early_message_count = max(0, total_count - KEEP_RECENT)
        # 检查是否已有缓存的摘要
        cached_summary = redis_client.get_summary(conversation_id)  # 从 Redis 获取已缓存的摘要
        cached_summary_count = redis_client.get_summary_count(conversation_id)

        if cached_summary and cached_summary_count == early_message_count:  # 如果摘要恰好覆盖当前早期消息
            summary = cached_summary  # 直接使用缓存
            config.logger.info(f"Using cached summary for conversation {conversation_id}")  # 记录使用缓存日志
        else:  # 没有缓存
            all_messages = redis_client.get_all_messages(conversation_id)  # 获取所有消息
            if cached_summary and 0 <= cached_summary_count < early_message_count:
                early_messages = all_messages[cached_summary_count:early_message_count]
                summary = self._compress_history(
                    early_messages,
                    conversation_id,
                    prior_summary=cached_summary,
                )
            else:
                early_messages = all_messages[:early_message_count]
                summary = self._compress_history(early_messages, conversation_id)
            redis_client.set_summary(
                conversation_id,
                summary,
                covered_count=early_message_count,
            )
            config.logger.info(f"Compressed {len(early_messages)} new messages into summary")

        # 返回：摘要 + 最近5轮
        return {
            "messages": [  # 消息列表
                {"role": "system", "content": f"[历史对话摘要] {summary}"}  # 将摘要作为 system 角色消息插入
            ] + recent_messages,  # 列表拼接（+ 运算符合并两个列表，类似 Java 的 Stream.concat）
            "conversation_id": conversation_id,  # 对话 ID
            "total_count": total_count,  # 总消息数
            "compressed": True,  # 标记已压缩
            "original_count": total_count  # 原始消息数量
        }

    def _compress_history(
        self,
        messages: List[Dict],
        conversation_id: str,
        prior_summary: str = "",
    ) -> str:
        """用 LLM 压缩早期对话为摘要"""
        if not messages:
            return prior_summary or "无历史对话记录。"

        history_text = "\n".join([  # 将消息列表拼接为文本（join 类似 Java 的 String.join）
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"  # 格式化每条消息为 "角色: 内容"
            for m in messages  # 遍历所有消息
        ])[-config.MEMORY_CONTEXT_MAX_CHARS:]

        prompt = f"""请增量更新历史对话摘要，保留关键信息：
1. 用户问了什么问题
2. AI 回答了什么要点
3. 用户明确提供的症状、病史、过敏史、用药和检查结果
4. 用户的偏好或关注点

已有摘要：
{prior_summary or "无"}

新增对话内容：
{history_text}

请使用精炼要点输出，最多 8 条；不要遗漏医疗事实、时间变化和尚未解决的问题。"""

        try:  # 尝试调用 LLM 生成摘要
            summary = self.llm_service.chat(prompt)  # 调用 LLM 的 chat 方法生成摘要
            return summary  # 返回摘要文本
        except Exception as e:  # 捕获异常
            config.logger.warning(f"Failed to compress history: {e}")  # 记录警告日志
            # 压缩失败时，返回简化版本
            suffix = f"新增 {len(messages)} 条对话，讨论了相关知识问题。"
            return f"{prior_summary} {suffix}".strip()
