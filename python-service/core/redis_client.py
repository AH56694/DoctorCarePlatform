import redis  # 导入 redis-py 库，Python 的 Redis 客户端（类似 Java 的 Jedis/Lettuce）
import json  # 导入 json 模块，用于 JSON 序列化和反序列化
import time  # 导入 time 模块，用于获取时间戳
import logging  # 导入日志模块
from core.config import config  # 从 core 包导入全局配置实例

logger = logging.getLogger(__name__)  # 获取当前模块的 Logger 实例

class RedisClient:  # 定义 Redis 客户端类，封装会话存储操作
    """Redis 客户端，用于会话记忆存储"""  # 类的 docstring

    def __init__(self):  # 构造方法，初始化 Redis 连接池和客户端
        """初始化Redis连接池"""  # 方法的 docstring
        self.pool = redis.ConnectionPool(  # 创建 Redis 连接池（类似 Java 的连接池，减少连接创建开销）
            host=config.REDIS_HOST,  # Redis 服务器地址
            port=config.REDIS_PORT,  # Redis 服务器端口
            password=config.REDIS_PASSWORD if config.REDIS_PASSWORD else None,  # 密码（有值则传入，无则传 None 表示无密码）
            db=config.REDIS_DB,  # Redis 数据库编号（0-15）
            decode_responses=True,  # 自动将响应从字节解码为字符串（否则返回 bytes 类型）
            max_connections=20  # 连接池最大连接数
        )
        self.client = redis.Redis(connection_pool=self.pool)  # 创建 Redis 客户端，使用连接池（类似 Java 的 JedisPool.getResource）
        logger.info(f"Redis client initialized: {config.REDIS_HOST}:{config.REDIS_PORT}")  # 记录初始化信息

    def add_message(self, conversation_id: str, role: str, content: str):  # 定义添加消息到会话的方法
        """追加消息到会话"""  # 方法的 docstring
        key = f"conversation:{conversation_id}:messages"  # 构造 Redis 键名（f-string 格式化），格式为 conversation:{会话ID}:messages
        message = json.dumps({  # 将消息对象序列化为 JSON 字符串
            "role": role,  # 消息角色（如 "user"、"assistant"）
            "content": content,  # 消息内容
            "timestamp": time.time()  # 当前时间戳（秒级，类似 Java 的 System.currentTimeMillis()/1000）
        }, ensure_ascii=False)  # ensure_ascii=False 保留中文字符，不转义为 \uXXXX
        self.client.rpush(key, message)  # rpush 将消息追加到列表右端（Redis 的 List 操作，类似队列）
        self.client.expire(key, 86400)  # 设置键的过期时间为 86400 秒（24小时）
        logger.debug(f"Added message to conversation {conversation_id}: {role}")  # 记录 DEBUG 级别日志

    def get_messages(self, conversation_id: str, limit: int = 10) -> list:  # 定义获取最近 N 条消息的方法，limit 默认 10
        """获取最近 N 条消息"""  # 方法的 docstring
        key = f"conversation:{conversation_id}:messages"  # 构造 Redis 键名
        messages = self.client.lrange(key, -limit, -1)  # lrange 获取列表中指定范围的元素，负索引表示从末尾计数（-limit 到 -1 即最后 limit 条）
        return [json.loads(m) for m in messages]  # 列表推导式：将每条 JSON 字符串反序列化为 Python 字典

    def get_all_messages(self, conversation_id: str) -> list:  # 定义获取所有消息的方法
        """获取所有消息"""  # 方法的 docstring
        key = f"conversation:{conversation_id}:messages"  # 构造 Redis 键名
        messages = self.client.lrange(key, 0, -1)  # lrange(key, 0, -1) 获取列表中所有元素（0 到 -1 表示从第一个到最后一个）
        return [json.loads(m) for m in messages]  # 将每条 JSON 反序列化为字典

    def get_message_count(self, conversation_id: str) -> int:  # 定义获取消息总数的方法
        """获取消息总数"""  # 方法的 docstring
        key = f"conversation:{conversation_id}:messages"  # 构造 Redis 键名
        return self.client.llen(key)  # llen 返回列表的长度（元素个数）

    def clear_conversation(self, conversation_id: str):  # 定义清空会话的方法
        """清空会话"""  # 方法的 docstring
        key = f"conversation:{conversation_id}:messages"  # 消息列表的键名
        summary_key = f"conversation:{conversation_id}:summary"  # 会话摘要的键名
        summary_count_key = f"conversation:{conversation_id}:summary_count"
        self.client.delete(key)  # 删除消息列表
        self.client.delete(summary_key)  # 删除会话摘要
        self.client.delete(summary_count_key)
        logger.info(f"Cleared conversation {conversation_id}")  # 记录清空操作

    def get_summary(self, conversation_id: str) -> str:  # 定义获取会话摘要的方法
        """获取会话摘要"""  # 方法的 docstring
        summary_key = f"conversation:{conversation_id}:summary"  # 构造摘要键名
        return self.client.get(summary_key)  # get 获取字符串值（如果键不存在返回 None）

    def get_summary_count(self, conversation_id: str) -> int:
        summary_count_key = f"conversation:{conversation_id}:summary_count"
        value = self.client.get(summary_count_key)
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def set_summary(
        self,
        conversation_id: str,
        summary: str,
        expire: int = 3600,
        covered_count: int = 0,
    ):
        """设置会话摘要"""  # 方法的 docstring
        summary_key = f"conversation:{conversation_id}:summary"  # 构造摘要键名
        summary_count_key = f"conversation:{conversation_id}:summary_count"
        pipeline = self.client.pipeline()
        pipeline.setex(summary_key, expire, summary)
        pipeline.setex(summary_count_key, expire, max(0, int(covered_count)))
        pipeline.execute()
        logger.debug(f"Set summary for conversation {conversation_id}")  # 记录设置操作

# 创建全局实例
redis_client = RedisClient()  # 模块级别创建 Redis 客户端的全局单例
