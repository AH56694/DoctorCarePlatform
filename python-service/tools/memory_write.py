from typing import Dict, Any  # 导入类型注解：Dict=字典类型，Any=任意类型
from tools.base import Tool, ToolSchema, SchemaProperty, ToolMetadata  # 导入工具基类及数据类
from core.config import config  # 导入全局配置单例
from core.redis_client import redis_client  # 导入 Redis 客户端单例
import uuid  # 导入 UUID 模块，用于生成唯一标识符（类似 Java 的 java.util.UUID）


class ConversationMemoryWriteTool(Tool):  # 对话记忆写入工具，继承自 Tool 抽象基类
    """对话记忆写入工具（真实存储）"""

    def __init__(self):  # 构造函数
        input_schema = ToolSchema(  # 定义输入参数 Schema
            properties={
                "conversation_id": SchemaProperty(  # 对话 ID 参数
                    type="string",  # 字符串类型
                    description="对话ID",  # 参数描述
                    required=True  # 必填
                ),
                "role": SchemaProperty(  # 消息角色参数
                    type="string",  # 字符串类型
                    description="角色 (user 或 assistant)",  # 参数描述
                    required=True  # 必填
                ),
                "content": SchemaProperty(  # 消息内容参数
                    type="string",  # 字符串类型
                    description="消息内容",  # 参数描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        output_schema = ToolSchema(  # 定义输出结果 Schema
            properties={
                "success": SchemaProperty(  # 是否成功输出
                    type="boolean",  # 布尔类型
                    description="是否成功",  # 描述
                    required=True  # 必填
                ),
                "message_id": SchemaProperty(  # 消息 ID 输出
                    type="string",  # 字符串类型
                    description="消息ID",  # 描述
                    required=True  # 必填
                ),
                "conversation_id": SchemaProperty(  # 对话 ID 输出
                    type="string",  # 字符串类型
                    description="对话ID",  # 描述
                    required=True  # 必填
                )
            },
            type="object"  # 整体类型为对象
        )

        metadata = ToolMetadata(  # 创建工具元数据
            timeout_ms=5000,  # 超时时间5秒
            max_retries=1,  # 最大重试1次
            permission="user",  # 用户级权限
            description="写入对话记忆"  # 工具描述
        )

        super().__init__(  # 调用父类构造函数（类似 Java 的 super()）
            name="conversation_memory_write",  # 工具名称
            description="写入对话记忆",  # 工具描述
            input_schema=input_schema,  # 输入 Schema
            output_schema=output_schema,  # 输出 Schema
            metadata=metadata  # 元数据
        )

    def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:  # 实现抽象方法，执行对话记忆写入
        """执行对话记忆写入（真实存储到Redis）"""
        conversation_id = parameters.get("conversation_id")  # 获取对话 ID
        role = parameters.get("role")  # 获取消息角色
        content = parameters.get("content")  # 获取消息内容

        # 验证角色
        if role not in ["user", "assistant"]:  # 检查角色是否合法（in 检查列表中是否包含某元素，类似 Java 的 list.contains()）
            raise ValueError(f"Invalid role: {role}, must be 'user' or 'assistant'")  # 抛出参数异常

        # 生成消息ID
        message_id = str(uuid.uuid4())  # 生成 UUID 并转为字符串（类似 Java 的 UUID.randomUUID().toString()）

        config.logger.info(f"Writing message to conversation {conversation_id}: role={role}")  # 记录写入日志

        # 写入Redis
        redis_client.add_message(conversation_id, role, content)  # 将消息写入 Redis 存储

        # 如果对话轮数超过阈值，清除旧摘要（让它在下次读取时重新生成）
        message_count = redis_client.get_message_count(conversation_id)  # 获取当前对话的消息总数
        if message_count > 10:  # 如果超过10条消息
            summary = redis_client.get_summary(conversation_id)  # 获取已有的摘要
            if summary:  # 如果摘要存在
                redis_client.client.delete(f"conversation:{conversation_id}:summary")  # 删除旧摘要的 Redis 缓存键
                config.logger.info(f"Cleared stale summary for conversation {conversation_id}")  # 记录清除日志

        return {  # 返回结果字典
            "success": True,  # 写入成功
            "message_id": message_id,  # 消息 ID
            "conversation_id": conversation_id  # 对话 ID
        }
