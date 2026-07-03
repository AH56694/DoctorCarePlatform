from fastapi import FastAPI  # 导入 FastAPI 框架，用于构建高性能 Web API
from fastapi.middleware.cors import CORSMiddleware  # 导入 CORS 中间件，处理跨域资源共享（类似 Java 中的 @CrossOrigin）
import uvicorn  # 导入 uvicorn，一个 ASGI 服务器，用于运行 FastAPI 应用（类似 Java 中的 Tomcat）
from pathlib import Path  # 导入 Path，用于跨平台的文件路径操作（类似 Java 中的 java.nio.file.Path）
from dotenv import load_dotenv  # 导入 load_dotenv，用于从 .env 文件加载环境变量（类似 Java 中的读取 properties 文件）
from middleware.middlewares import TimingMiddleware  # 导入自定义的耗时统计中间件

# 加载环境变量 (确保加载当前目录下的 .env 文件)
env_path = Path(__file__).parent / '.env'  # __file__ 是当前文件路径，parent 获取父目录，/ 是 Path 的路径拼接操作符
load_dotenv(dotenv_path=env_path)  # 加载 .env 文件中的环境变量到 os.environ 中

from api.routes import router  # 导入基础 API 路由（导入必须在 load_dotenv 之后，因为路由模块可能依赖环境变量）
from api.agent_routes import router as agent_router  # 导入 Agent API 路由，并重命名为 agent_router 以避免与上面的 router 冲突
from api.integration_routes import router as integration_router
import tools  # 导入 tools 包，触发其 __init__.py 中的工具注册逻辑

app = FastAPI(title="AI Knowledge System - Python Service")  # 创建 FastAPI 应用实例，类似 Java 中的 SpringApplication.run()

# 中间件
app.add_middleware(TimingMiddleware, enable=True, threshold=0.0)  # 注册自定义耗时统计中间件，enable=True 表示启用，threshold=0.0 表示所有请求都记录（不论耗时）

# 配置 CORS（跨域资源共享）
app.add_middleware(  # 添加 CORS 中间件，类似 Java 中 Spring 的 CorsFilter
    CORSMiddleware,  # CORS 中间件类
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8181", "http://127.0.0.1:8181"],  # 允许的前端来源地址列表
    allow_credentials=True,  # 允许携带 Cookie 等认证信息（类似 Java 中的 allowCredentials = "true"）
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # 允许的 HTTP 方法
    allow_headers=["Content-Type", "Authorization"],  # 允许的请求头
)


# 注册路由
app.include_router(router, prefix="/api")  # 将基础路由注册到 /api 路径下，类似 Java 中 @RequestMapping("/api")
app.include_router(agent_router, prefix="/api")  # 将 Agent 路由注册到 /api 路径下
app.include_router(integration_router, prefix="/api/v1")

@app.get("/")  # 装饰器，注册 GET 请求处理函数，路径为 "/"，类似 Java 中的 @GetMapping("/")
async def root():  # async 表示异步函数，Python 异步编程关键字，类似 Java 中的 CompletableFuture
    return {"message": "AI Knowledge System Python Service is running"}  # 返回 JSON 响应，FastAPI 自动将字典序列化为 JSON

# 健康检查端点
@app.get("/health")  # 注册健康检查的 GET 端点，类似 Java 中 Spring Boot Actuator 的 /health
async def health_check():  # 异步健康检查函数
    import os  # 导入 os 模块，用于读取环境变量（类似 Java 中的 System.getenv()）
    # 检查环境变量
    has_api_key = os.getenv("DASHSCOPE_API_KEY") is not None  # 检查是否配置了阿里云 DashScope API Key
    use_milvus = os.getenv("USE_MILVUS", "true").lower() == "true"  # 读取是否使用 Milvus 向量数据库，默认为 "true"
    milvus_host = os.getenv("MILVUS_HOST", "localhost")  # 读取 Milvus 主机地址，默认为 localhost
    milvus_port = os.getenv("MILVUS_PORT", "19530")  # 读取 Milvus 端口号，默认为 19530

    # 检查向量存储
    vector_store_info = {}  # 初始化向量存储信息字典（类似 Java 中的 Map）
    if use_milvus:  # 如果使用 Milvus 向量数据库
        vector_store_info = {  # 构造 Milvus 的状态信息
            "type": "Milvus",  # 类型为 Milvus
            "host": milvus_host,  # Milvus 主机地址
            "port": milvus_port,  # Milvus 端口号
            "status": "configured"  # 状态为已配置
        }
    else:  # 如果不使用 Milvus，则使用 FAISS 本地向量库
        vector_store_dir = os.path.join(os.getcwd(), "faiss_index")  # 拼接 FAISS 索引文件的目录路径
        vector_store_exists = os.path.exists(vector_store_dir)  # 检查 FAISS 索引目录是否存在
        vector_store_info = {  # 构造 FAISS 的状态信息
            "type": "FAISS",  # 类型为 FAISS
            "exists": vector_store_exists,  # 索引是否存在
            "directory": vector_store_dir  # 索引目录路径
        }

    return {  # 返回健康检查结果
        "status": "healthy",  # 状态为健康
        "environment": {  # 环境配置信息
            "has_dashscope_api_key": has_api_key,  # 是否配置了 API Key
            "use_milvus": use_milvus  # 是否使用 Milvus
        },
        "vector_store": vector_store_info  # 向量存储信息
    }

if __name__ == "__main__":  # Python 入口判断，只有直接运行此文件时才执行（被 import 时不执行），类似 Java 中的 main 方法
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)  # 启动 uvicorn 服务器，"main:app" 指当前模块的 app 变量，reload=True 开发热重载（开发模式）
