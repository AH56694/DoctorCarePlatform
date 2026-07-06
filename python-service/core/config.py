import os  # 导入 os 模块，用于访问操作系统功能（如读取环境变量、创建目录等）
import logging  # 导入 logging 模块，用于记录日志信息（类似 Java 中的 Log4j/SLF4J）
from typing import Dict, Any  # 从 typing 模块导入类型提示，Dict 相当于 Java 的 Map<String, Object>，Any 相当于 Java 的 Object
from urllib.parse import urlparse

class ConfigManager:  # 定义配置管理器类，类似 Java 中的 class，用于集中管理所有配置项
    """统一配置管理模块"""  # 类的 docstring，说明这是一个统一配置管理模块

    def __init__(self):  # 构造方法，类似 Java 中的构造器，self 相当于 Java 中的 this，指向当前实例
        """初始化配置管理器"""  # 方法的 docstring
        self._load_config()  # 调用 _load_config 方法加载所有配置项，下划线前缀表示"私有方法"（Python 约定，并非强制）
        self._setup_logging()  # 调用 _setup_logging 方法初始化日志配置

    def _load_config(self):  # 定义加载配置的私有方法
        """加载配置项"""  # 方法的 docstring
        # AI Embeddings
        self.DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")  # 从环境变量读取阿里云 DashScope API 密钥，第二个参数是默认值（空字符串）
        self.DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")  # 从环境变量读取通义千问 API 密钥，第二个参数是默认值（空字符串）
        self.LLM_FALLBACK_PROVIDERS = [
            provider.strip().lower()
            for provider in os.getenv("LLM_FALLBACK_PROVIDERS", "ollama,openai_compatible,retrieval").split(",")
            if provider.strip()
        ]
        self.OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        self.OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
        self.LOCAL_LLM_TIMEOUT_SECONDS = int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "45"))
        self.OPENAI_COMPATIBLE_BASE_URL = os.getenv("OPENAI_COMPATIBLE_BASE_URL", "").rstrip("/")
        self.OPENAI_COMPATIBLE_API_KEY = os.getenv("OPENAI_COMPATIBLE_API_KEY", "")
        self.OPENAI_COMPATIBLE_MODEL = os.getenv("OPENAI_COMPATIBLE_MODEL", "")
        # Embedding模型选择: "dashscope" 使用云端API, "local" 使用本地中文模型
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "dashscope")  # 读取 Embedding 模型类型配置，默认使用阿里云端 API
        # 本地Embedding模型名称（仅当EMBEDDING_MODEL=local时生效）
        self.LOCAL_EMBEDDING_MODEL = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")  # 读取本地 Embedding 模型名称，默认为 BGE 中文小模型
        # 本地Embedding模型的磁盘路径（如果设置了此路径，则直接从本地加载，不联网下载）
        self.LOCAL_EMBEDDING_MODEL_PATH = os.getenv("LOCAL_EMBEDDING_MODEL_PATH", "")  # 本地模型目录路径，如 ./models/bge-small-zh-v1.5，为空则使用HuggingFace自动下载

        # Milvus Configuration
        self.MILVUS_HOST = os.getenv("MILVUS_HOST", "localhost")  # Milvus 向量数据库主机地址，默认 localhost
        self.MILVUS_PORT = os.getenv("MILVUS_PORT", "19530")  # Milvus 向量数据库端口，默认 19530
        self.MILVUS_USER = os.getenv("MILVUS_USER", "")  # Milvus 用户名，默认为空
        self.MILVUS_PASSWORD = os.getenv("MILVUS_PASSWORD", "")  # Milvus 密码，默认为空

        # Redis Configuration
        redis_url = os.getenv("REDIS_URL", "")
        parsed_redis = urlparse(redis_url) if redis_url else None
        self.REDIS_HOST = os.getenv(
            "REDIS_HOST",
            parsed_redis.hostname if parsed_redis and parsed_redis.hostname else "localhost",
        )  # Redis 主机地址，默认 localhost
        self.REDIS_PORT = int(os.getenv(
            "REDIS_PORT",
            str(parsed_redis.port or 6379) if parsed_redis else "6379",
        ))  # Redis 端口，int() 将字符串转为整数，默认 6379
        self.REDIS_PASSWORD = os.getenv(
            "REDIS_PASSWORD",
            parsed_redis.password if parsed_redis and parsed_redis.password else "",
        )  # Redis 密码，默认为空
        redis_path = (parsed_redis.path or "").lstrip("/") if parsed_redis else ""
        self.REDIS_DB = int(os.getenv("REDIS_DB", redis_path or "0"))  # Redis 数据库编号（0-15），默认使用 0 号库

        # MySQL Configuration
        self.DB_HOST = os.getenv("MYSQL_HOST", "localhost")  # MySQL 主机地址，默认 localhost
        self.DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))  # MySQL 端口，int() 将字符串转为整数，默认 3306
        self.DB_USER = os.getenv("MYSQL_USERNAME", "root")  # MySQL 用户名，默认 root
        self.DB_PASSWORD = os.getenv("MYSQL_PASSWORD", "change-me")  # MySQL 密码，默认 change-me
        self.DB_NAME = os.getenv("MYSQL_DATABASE", "doctor_care_platform")  # MySQL 数据库名，默认 doctor_care_platform

        # Vector Store Configuration
        self.USE_MILVUS = os.getenv("USE_MILVUS", "true").lower() == "true"  # 是否使用 Milvus（布尔值），.lower() 统一转小写后与 "true" 比较，类似 Java 的 equalsIgnoreCase
        self.VECTOR_STORE_PERSIST_DIR = os.getenv("VECTOR_STORE_PERSIST_DIR", "./faiss_index")  # FAISS 向量库持久化目录，默认 ./faiss_index
        self.VECTOR_STORE_COLLECTION_NAME = os.getenv("VECTOR_STORE_COLLECTION_NAME", "ai_knowledge_collection")  # Milvus 集合名称（类似 MySQL 表名），默认 ai_knowledge_collection

        # RAG safety configuration. These defaults make medical/knowledge answers evidence-first.
        self.RAG_STRICT_MODE = os.getenv("RAG_STRICT_MODE", "true").lower() == "true"
        self.RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.68"))
        self.RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
        self.RAG_USE_RERANK = os.getenv("RAG_USE_RERANK", "true").lower() == "true"
        self.RAG_MIN_SOURCE_COUNT = int(os.getenv("RAG_MIN_SOURCE_COUNT", "1"))

        # Rerank Configuration
        self.RERANKER_TYPE = os.getenv("RERANKER_TYPE", "simple")  # 重排序器类型，可选 "simple"、"bge"、"cohere"，默认 simple
        self.COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")  # Cohere API 密钥（用于 Cohere 重排序服务），默认为空

        # Text Chunking Configuration
        self.CHUNK_STRATEGY = os.getenv("CHUNK_STRATEGY", "semantic")  # 文本切分策略，"semantic" 为语义切分，默认 semantic
        self.CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # 每个文本块的最大字符数，默认 500
        self.CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))  # 相邻文本块的重叠字符数，默认 50
        self.MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "100"))  # 文本块的最小字符数（太小的块会被合并），默认 100

        # Tesseract OCR Configuration（默认为空，由 parser.py 自动检测）
        self.TESSERACT_PATH = os.getenv("TESSERACT_PATH", "")  # Tesseract OCR 可执行文件路径，默认为空（由程序自动检测）

        # Temporary Files Configuration
        self.TEMP_DIR = os.getenv("TEMP_DIR", "./temp")  # 临时文件目录路径，默认 ./temp
        # 确保临时目录存在
        os.makedirs(self.TEMP_DIR, exist_ok=True)  # 创建目录，exist_ok=True 表示目录已存在时不抛异常（类似 Java 的 Files.createDirectories）

        # Logging Configuration
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 日志级别，默认 INFO

        # API Configuration
        self.API_HOST = os.getenv("API_HOST", "0.0.0.0")  # API 服务监听地址，0.0.0.0 表示监听所有网络接口
        self.API_PORT = int(os.getenv("API_PORT", "8300"))  # API 服务监听端口，默认 8300

        # CORS Configuration
        self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")  # 允许跨域的前端地址列表，.split(",") 按逗号分割字符串为列表（类似 Java 的 String.split）

    def _setup_logging(self):  # 定义设置日志的私有方法
        """设置日志配置"""  # 方法的 docstring
        log_level = getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)  # getattr 类似 Java 的反射，通过字符串名称获取属性；将日志级别字符串转为 logging 模块中的常量（如 "INFO" -> logging.INFO），找不到时默认 INFO
        logging.basicConfig(  # 配置全局日志格式
            level=log_level,  # 设置日志级别
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 日志格式：时间 - 模块名 - 级别 - 消息
            handlers=[  # 日志处理器列表
                logging.StreamHandler()  # 输出到控制台（标准输出流）
            ]
        )
        self.logger = logging.getLogger(__name__)  # 创建当前模块的 Logger 实例，__name__ 是当前模块名（类似 Java 的 LoggerFactory.getLogger(Class)）
        self.logger.info("Configuration loaded successfully")  # 记录 INFO 级别日志，表示配置加载成功

    def get_config(self) -> Dict[str, Any]:  # 定义获取所有配置的方法，-> Dict[str, Any] 是返回值类型提示（类似 Java 方法的返回类型声明）
        """获取所有配置项"""  # 方法的 docstring
        return {  # 返回一个字典（类似 Java 的 Map），包含所有配置项
            "DASHSCOPE_API_KEY": "***" if self.DASHSCOPE_API_KEY else "",  # 三元表达式：如果有密钥则显示 ***（脱敏），否则空字符串
            "DEEPSEEK_API_KEY": "***" if self.DEEPSEEK_API_KEY else "",  # 三元表达式：如果有密钥则显示 ***（脱敏），否则空字符串
            "MILVUS_HOST": self.MILVUS_HOST,  # Milvus 主机地址
            "MILVUS_PORT": self.MILVUS_PORT,  # Milvus 端口
            "USE_MILVUS": self.USE_MILVUS,  # 是否使用 Milvus
            "VECTOR_STORE_PERSIST_DIR": self.VECTOR_STORE_PERSIST_DIR,  # 向量库持久化目录
            "VECTOR_STORE_COLLECTION_NAME": self.VECTOR_STORE_COLLECTION_NAME,  # Milvus 集合名称
            "RAG_STRICT_MODE": self.RAG_STRICT_MODE,
            "RAG_SIMILARITY_THRESHOLD": self.RAG_SIMILARITY_THRESHOLD,
            "RAG_TOP_K": self.RAG_TOP_K,
            "RAG_USE_RERANK": self.RAG_USE_RERANK,
            "RAG_MIN_SOURCE_COUNT": self.RAG_MIN_SOURCE_COUNT,
            "EMBEDDING_MODEL": self.EMBEDDING_MODEL,  # Embedding 模型类型
            "LOCAL_EMBEDDING_MODEL": self.LOCAL_EMBEDDING_MODEL,  # 本地 Embedding 模型名称
            "RERANKER_TYPE": self.RERANKER_TYPE,  # 重排序器类型
            "CHUNK_STRATEGY": self.CHUNK_STRATEGY,  # 文本切分策略
            "CHUNK_SIZE": self.CHUNK_SIZE,  # 文本块最大字符数
            "CHUNK_OVERLAP": self.CHUNK_OVERLAP,  # 文本块重叠字符数
            "MIN_CHUNK_SIZE": self.MIN_CHUNK_SIZE,  # 文本块最小字符数
            "TESSERACT_PATH": self.TESSERACT_PATH,  # Tesseract OCR 路径
            "TEMP_DIR": self.TEMP_DIR,  # 临时文件目录
            "LOG_LEVEL": self.LOG_LEVEL,  # 日志级别
            "API_HOST": self.API_HOST,  # API 监听地址
            "API_PORT": self.API_PORT,  # API 监听端口
            "CORS_ORIGINS": self.CORS_ORIGINS  # 跨域允许的前端地址列表
        }

    def validate_config(self) -> bool:  # 定义验证配置的方法，-> bool 表示返回布尔值
        """验证配置项"""  # 方法的 docstring
        is_valid = True  # 初始化验证结果为 True（类似 Java 的 boolean isValid = true）

        # 验证必要的配置项
        if not self.DASHSCOPE_API_KEY:  # 如果 DashScope API 密钥未设置（空字符串在 Python 中为 False）
            self.logger.warning("DASHSCOPE_API_KEY not set, will use local embeddings")  # 记录警告日志

        # 验证Tesseract路径（空值表示由 parser.py 自动检测）
        if self.TESSERACT_PATH and not os.path.exists(self.TESSERACT_PATH):  # 如果设置了路径但路径不存在（and 短路求值，类似 Java 的 &&）
            self.logger.warning(f"Tesseract not found at {self.TESSERACT_PATH}, will try other locations")  # f-string 格式化字符串（类似 Java 的 String.format），记录警告

        return is_valid  # 返回验证结果

# 创建全局配置实例
config = ConfigManager()  # 模块级别创建单例配置实例（Python 中模块天然是单例的，import 时只执行一次）
