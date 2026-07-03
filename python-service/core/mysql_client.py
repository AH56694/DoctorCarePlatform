import os  # 导入 os 模块，用于读取环境变量
import json  # 导入 json 模块，用于 JSON 序列化和反序列化
import mysql.connector  # 导入 MySQL 官方连接器（类似 Java 的 mysql-connector-java）
from mysql.connector import Error, pooling  # 导入 MySQL 错误类和连接池模块（pooling 类似 Java 的 HikariCP 连接池）
from typing import List, Dict, Any  # 导入类型提示：List 列表，Dict 字典（Map），Any 任意类型
import logging  # 导入日志模块

logger = logging.getLogger(__name__)  # 获取当前模块的 Logger 实例

class MySQLClient:  # 定义 MySQL 客户端类，封装数据库操作
    """MySQL 数据库客户端"""  # 类的 docstring

    def __init__(self):  # 构造方法，初始化数据库连接参数
        self.host = os.getenv("MYSQL_HOST", "localhost")  # MySQL 主机地址
        self.port = int(os.getenv("MYSQL_PORT", "3306"))  # MySQL 端口，int() 转为整数
        self.database = os.getenv("MYSQL_DATABASE", "ai_knowledge_db")  # 数据库名
        self.username = os.getenv("MYSQL_USERNAME", "root")  # 用户名
        self.password = os.getenv("MYSQL_PASSWORD", "change-me")  # 密码
        self.connection = None  # 数据库连接对象，初始为 None（类似 Java 的 null）

    def connect(self):  # 定义建立数据库连接的方法
        """建立数据库连接"""  # 方法的 docstring
        try:  # try-except 异常处理
            self.connection = mysql.connector.connect(  # 创建 MySQL 连接
                host=self.host,  # 主机地址
                port=self.port,  # 端口号
                database=self.database,  # 数据库名
                user=self.username,  # 用户名
                password=self.password,  # 密码
                use_unicode=True,  # 启用 Unicode 支持
                charset='utf8mb4',  # 使用 utf8mb4 字符集（支持完整的 Unicode，包括 emoji）
                time_zone='+08:00'  # 设置时区为中国标准时间
            )
            if self.connection.is_connected():  # 检查连接是否成功
                logger.info("Successfully connected to MySQL database")  # 记录成功日志
                # 设置会话时区
                cursor = self.connection.cursor()  # 创建游标对象（类似 Java 中 Statement/PreparedStatement）
                cursor.execute("SET time_zone = '+08:00'")  # 执行 SQL 设置会话时区
                cursor.close()  # 关闭游标
        except Error as e:  # 捕获 MySQL 特有的异常（类似 Java 的 catch(SQLException e)）
            logger.error(f"Error connecting to MySQL: {e}")  # 记录错误日志

    def disconnect(self):  # 定义关闭数据库连接的方法
        """关闭数据库连接"""  # 方法的 docstring
        if self.connection and self.connection.is_connected():  # 检查连接存在且处于连接状态（短路求值）
            self.connection.close()  # 关闭连接
            logger.info("MySQL connection closed")  # 记录关闭日志

    def insert_chunks(self, doc_id: int, chunks: List[Dict[str, Any]]):  # 定义批量插入文本块的方法，参数类型提示：doc_id 整数，chunks 是字典列表
        """批量插入 chunks 到 knowledge_chunk 表"""  # 方法的 docstring
        if not chunks:  # 如果 chunks 为空列表（空列表在 Python 中为 False）
            return 0  # 返回插入数量 0

        if not self.connection or not self.connection.is_connected():  # 检查连接是否可用
            self.connect()  # 重新建立连接

        try:
            cursor = self.connection.cursor()  # 创建游标

            # 先删除该文档已有的 chunks（避免重复）
            delete_sql = "DELETE FROM knowledge_chunk WHERE doc_id = %s"  # SQL 删除语句，%s 是参数占位符（类似 JDBC 的 ?）
            cursor.execute(delete_sql, (doc_id,))  # 执行删除，(doc_id,) 是单元素元组（注意逗号不能少，否则会被当作括号表达式）

            # 批量插入新 chunks
            insert_sql = """  # SQL 插入语句（多行字符串，用三引号包围）
                INSERT INTO knowledge_chunk (doc_id, chunk_index, chunk_text, create_time)
                VALUES (%s, %s, %s, NOW())
            """

            data = [  # 准备批量插入的数据
                (doc_id, chunk.get('chunk_index', i), chunk.get('page_content', ''),)  # chunk.get 类似 Java Map 的 getOrDefault，取 key 不存在时返回默认值
                for i, chunk in enumerate(chunks)  # enumerate 同时获取索引和元素（类似 Java 的 for i=0; i<list.size(); i++）
            ]

            cursor.executemany(insert_sql, data)  # 批量执行插入语句（类似 JDBC 的 addBatch + executeBatch）
            self.connection.commit()  # 提交事务（类似 Java 的 connection.commit()）

            inserted_count = cursor.rowcount  # 获取受影响的行数（插入的记录数）
            logger.info(f"Inserted {inserted_count} chunks for doc_id {doc_id}")  # 记录插入数量

            cursor.close()  # 关闭游标
            return inserted_count  # 返回插入数量

        except Error as e:  # 捕获 MySQL 异常
            logger.error(f"Error inserting chunks: {e}")  # 记录错误
            if self.connection:  # 如果连接存在
                self.connection.rollback()  # 回滚事务（类似 Java 的 connection.rollback()）
            return 0  # 返回 0 表示插入失败

    def get_chunk_count(self, doc_id: int = None) -> int:  # 定义获取文本块数量的方法，doc_id 默认为 None（类似 Java 的方法重载）
        """获取 chunk 数量"""  # 方法的 docstring
        if not self.connection or not self.connection.is_connected():  # 检查连接
            self.connect()  # 重新连接

        try:
            cursor = self.connection.cursor()  # 创建游标

            if doc_id:  # 如果指定了文档 ID
                sql = "SELECT COUNT(*) FROM knowledge_chunk WHERE doc_id = %s"  # 按文档 ID 统计
                cursor.execute(sql, (doc_id,))  # 执行查询
            else:  # 否则统计全部
                sql = "SELECT COUNT(*) FROM knowledge_chunk"  # 统计所有文本块数量
                cursor.execute(sql)  # 执行查询（无参数）

            result = cursor.fetchone()  # 获取查询结果的第一行（返回元组，如 (10,)）
            cursor.close()  # 关闭游标
            return result[0] if result else 0  # 如果结果存在则返回第一个元素（计数），否则返回 0

        except Error as e:
            logger.error(f"Error getting chunk count: {e}")
            return 0

    def fetch_one(self, sql: str, params: tuple = None) -> Dict[str, Any]:  # 定义查询单行的方法，返回字典（键是列名，值是数据）
        """执行查询并返回单行结果"""  # 方法的 docstring
        if not self.connection or not self.connection.is_connected():  # 检查连接
            self.connect()

        try:
            cursor = self.connection.cursor(dictionary=True)  # dictionary=True 使结果以字典形式返回（列名作为键），默认返回元组

            if params:  # 如果有参数
                cursor.execute(sql, params)  # 带参数执行
            else:  # 无参数
                cursor.execute(sql)  # 直接执行

            result = cursor.fetchone()  # 获取一行结果
            cursor.close()  # 关闭游标
            return result  # 返回结果字典或 None

        except Error as e:
            logger.error(f"Error fetching one: {e}")
            return None  # 返回 None（Python 的空值）

    def fetch_all(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:  # 定义查询所有行的方法，返回字典列表
        """执行查询并返回所有结果"""  # 方法的 docstring
        if not self.connection or not self.connection.is_connected():  # 检查连接
            self.connect()

        try:
            cursor = self.connection.cursor(dictionary=True)  # 使用字典游标

            if params:  # 如果有参数
                cursor.execute(sql, params)
            else:  # 无参数
                cursor.execute(sql)

            result = cursor.fetchall()  # 获取所有结果行（返回列表）
            cursor.close()  # 关闭游标
            return result  # 返回结果列表

        except Error as e:
            logger.error(f"Error fetching all: {e}")
            return []  # 返回空列表（类似 Java 的 Collections.emptyList()）

    def execute(self, sql: str, params: tuple = None) -> int:  # 定义执行增删改 SQL 的方法，返回受影响行数
        """执行SQL语句（INSERT/UPDATE/DELETE）"""  # 方法的 docstring
        if not self.connection or not self.connection.is_connected():  # 检查连接
            self.connect()

        try:
            cursor = self.connection.cursor()  # 创建游标

            if params:  # 如果有参数
                cursor.execute(sql, params)
            else:  # 无参数
                cursor.execute(sql)

            self.connection.commit()  # 提交事务
            affected_rows = cursor.rowcount  # 获取受影响的行数
            cursor.close()  # 关闭游标
            return affected_rows  # 返回受影响行数

        except Error as e:
            logger.error(f"Error executing SQL: {e}")
            if self.connection:  # 如果连接存在
                self.connection.rollback()  # 回滚事务
            return 0  # 返回 0 表示执行失败

# 创建全局实例
mysql_client = MySQLClient()  # 模块级别创建 MySQL 客户端的全局单例


class UserMemoryClient:  # 定义用户记忆客户端类，使用连接池管理连接
    """用户记忆客户端（连接池版本）"""  # 类的 docstring

    _pool = None  # 类变量，保存连接池实例（类似 Java 的 private static），初始为 None

    @classmethod  # 类方法装饰器，定义类级别的方法（类似 Java 的 static 方法），第一个参数是 cls（类本身）而非 self（实例）
    def get_pool(cls):  # 定义获取连接池的方法
        """获取连接池（懒初始化，单例）"""  # 方法的 docstring
        if cls._pool is None:  # 如果连接池尚未创建（is None 是判断 None 的推荐写法，不用 ==）
            cls._pool = pooling.MySQLConnectionPool(  # 创建 MySQL 连接池（类似 Java 的 HikariDataSource）
                pool_name="user_memory_pool",  # 连接池名称
                pool_size=10,               # 连接池大小：最大连接数
                pool_reset_session=True,     # 归还连接时重置会话状态
                host=os.getenv("MYSQL_HOST", "localhost"),  # MySQL 主机
                port=int(os.getenv("MYSQL_PORT", "3306")),  # MySQL 端口
                user=os.getenv("MYSQL_USERNAME", "root"),  # 用户名
                password=os.getenv("MYSQL_PASSWORD", "change-me"),  # 密码
                database=os.getenv("MYSQL_DATABASE", "ai_knowledge_db"),  # 数据库名
                charset="utf8mb4",  # 字符集
                autocommit=True  # 自动提交事务（每个 SQL 语句自动 commit）
            )
        return cls._pool  # 返回连接池实例

    def _get_connection(self):  # 定义从连接池获取连接的私有方法
        """从连接池获取连接"""  # 方法的 docstring
        return self.get_pool().get_connection()  # 从连接池中获取一个连接

    def get_user_memory(self, user_id: str) -> Dict[str, Any]:  # 定义获取用户所有记忆的方法
        """获取用户所有记忆"""  # 方法的 docstring
        conn = self._get_connection()  # 从连接池获取连接
        try:  # try-finally 确保连接一定被归还（类似 Java 的 try-finally）
            cursor = conn.cursor(dictionary=True)  # 创建字典游标
            cursor.execute(  # 执行查询
                "SELECT memory_key, memory_value FROM user_memory WHERE user_id = %s",  # SQL 查询语句
                (user_id,)  # 参数（单元素元组）
            )
            rows = cursor.fetchall()  # 获取所有结果行
            cursor.close()  # 关闭游标
        finally:  # finally 块，无论是否异常都会执行
            conn.close()  # 归还到连接池，不是真正关闭（连接池的 close 是归还连接）

        memory = {}  # 创建空字典（类似 Java 的新 HashMap）
        for row in rows:  # 遍历查询结果
            try:  # 尝试解析 JSON
                memory[row["memory_key"]] = json.loads(row["memory_value"])  # json.loads 将 JSON 字符串解析为 Python 对象（类似 Java 的 objectMapper.readValue）
            except:  # 裸 except 捕获所有异常（不推荐但在快速处理时可用）
                memory[row["memory_key"]] = row["memory_value"]  # JSON 解析失败则直接保存原始字符串
        return memory  # 返回用户记忆字典

    def update_user_memory(self, user_id: str, key: str, value: Dict[str, Any],
                           source: str = "agent", confidence: float = 1.0):  # 定义更新用户记忆的方法，支持多参数和默认值
        """更新用户记忆（upsert）"""  # 方法的 docstring，upsert 表示存在则更新，不存在则插入
        conn = self._get_connection()  # 从连接池获取连接
        try:
            cursor = conn.cursor()  # 创建游标
            cursor.execute("""  # 执行 upsert SQL
                INSERT INTO user_memory (user_id, memory_key, memory_value, source, confidence)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE  # MySQL 特有语法：唯一键冲突时执行更新
                    memory_value = VALUES(memory_value),
                    source = VALUES(source),
                    confidence = VALUES(confidence)
            """, (user_id, key, json.dumps(value, ensure_ascii=False), source, confidence))  # json.dumps 将 Python 对象序列化为 JSON 字符串，ensure_ascii=False 保留中文字符
            conn.commit()  # 提交事务
            cursor.close()  # 关闭游标
        finally:
            conn.close()  # 归还到连接池

    def batch_get_user_memories(self, user_ids: list) -> Dict[str, Dict]:  # 定义批量获取多个用户记忆的方法
        """批量获取多个用户的记忆（减少连接获取次数）"""  # 方法的 docstring
        if not user_ids:  # 如果用户 ID 列表为空
            return {}  # 返回空字典

        conn = self._get_connection()  # 从连接池获取连接
        try:
            cursor = conn.cursor(dictionary=True)  # 创建字典游标
            placeholders = ",".join(["%s"] * len(user_ids))  # 生成占位符字符串，如 "%s,%s,%s"（类似 Java 的 String.join）
            cursor.execute(  # 执行 IN 查询
                f"SELECT user_id, memory_key, memory_value FROM user_memory WHERE user_id IN ({placeholders})",  # f-string 格式化，动态生成 SQL
                user_ids  # 参数列表
            )
            rows = cursor.fetchall()  # 获取所有结果
            cursor.close()  # 关闭游标
        finally:
            conn.close()  # 归还连接

        result = {uid: {} for uid in user_ids}  # 字典推导式：为每个用户 ID 创建空字典（类似 Java 的 Stream + Collectors.toMap）
        for row in rows:  # 遍历查询结果
            try:
                result[row["user_id"]][row["memory_key"]] = json.loads(row["memory_value"])  # 解析 JSON 并存入对应用户的记忆字典
            except:
                result[row["user_id"]][row["memory_key"]] = row["memory_value"]  # 解析失败则保存原始字符串
        return result  # 返回所有用户的记忆数据


# 创建全局实例
user_memory_client = UserMemoryClient()  # 模块级别创建用户记忆客户端的全局单例
