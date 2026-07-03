from typing import Dict, Any, List  # 导入类型注解：Dict=字典，Any=任意类型，List=列表类型（类似 Java 的 List<?>）
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.config import config  # 导入全局配置单例
from core.redis_client import redis_client  # 导入 Redis 客户端单例（用于存储对话消息）
from core.llm import LLMService  # 导入 LLM（大语言模型）服务类

# 压缩阈值配置
COMPRESS_THRESHOLD = 10  # 超过10轮对话触发上下文压缩
KEEP_RECENT = 5          # 压缩时保留最近5轮完整对话


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

        # 检查是否已有缓存的摘要
        cached_summary = redis_client.get_summary(conversation_id)  # 从 Redis 获取已缓存的摘要

        if cached_summary:  # 如果有缓存的摘要
            summary = cached_summary  # 直接使用缓存
            config.logger.info(f"Using cached summary for conversation {conversation_id}")  # 记录使用缓存日志
        else:  # 没有缓存
            # 获取早期消息用于压缩
            all_messages = redis_client.get_all_messages(conversation_id)  # 获取所有消息
            early_messages = all_messages[:-KEEP_RECENT]  # 切片取前面的消息（[:-5] 表示取除最后5条外的所有，类似 Java 的 subList(0, size-5)）
            summary = self._compress_history(early_messages, conversation_id)  # 调用压缩方法生成摘要
            # 缓存摘要
            redis_client.set_summary(conversation_id, summary)  # 将摘要缓存到 Redis
            config.logger.info(f"Compressed {len(early_messages)} messages into summary")  # 记录压缩日志

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

    def _compress_history(self, messages: List[Dict], conversation_id: str) -> str:  # 私有方法，用 LLM 压缩早期对话为摘要（下划线前缀表示私有，类似 Java 的 private）
        """用 LLM 压缩早期对话为摘要"""
        if not messages:  # 如果消息列表为空（Python 中空列表为 falsy 值）
            return "无历史对话记录。"  # 返回默认文本

        history_text = "\n".join([  # 将消息列表拼接为文本（join 类似 Java 的 String.join）
            f"{m.get('role', 'unknown')}: {m.get('content', '')}"  # 格式化每条消息为 "角色: 内容"
            for m in messages  # 遍历所有消息
        ])  # 列表推导式生成字符串列表后用换行符连接

        prompt = f"""请将以下对话压缩成简短摘要，保留关键信息：  # f-string 多行字符串模板（类似 Java 的 TextBlock / String.format）
1. 用户问了什么问题
2. AI 回答了什么要点
3. 用户的偏好或关注点

对话内容：
{history_text}

请用 2-3 句话概括，不要遗漏重要信息。"""

        try:  # 尝试调用 LLM 生成摘要
            summary = self.llm_service.chat(prompt)  # 调用 LLM 的 chat 方法生成摘要
            return summary  # 返回摘要文本
        except Exception as e:  # 捕获异常
            config.logger.warning(f"Failed to compress history: {e}")  # 记录警告日志
            # 压缩失败时，返回简化版本
            return f"用户进行了 {len(messages)} 轮对话，讨论了相关知识问题。"  # 返回兜底的简化摘要
