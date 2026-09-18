from fastapi import APIRouter, HTTPException, Request  # 导入 FastAPI 的路由器、HTTP 异常类和请求对象
from fastapi.responses import StreamingResponse  # 导入流式响应类，用于 SSE（Server-Sent Events）流式返回
from pydantic import BaseModel  # 导入 Pydantic 的基础模型类，用于定义请求/响应的数据结构（类似 Java 中的 DTO/VO，自带参数校验）
from core.parser import DocumentParser  # 导入文档解析器，负责将文档解析为文本块
from core.vector_store import vector_store  # 导入向量存储管理器（单例），用于文档的向量化存储和检索
from core.llm import LLMService  # 导入大语言模型服务，封装与 LLM 的交互
from core.mysql_client import mysql_client  # 导入 MySQL 客户端，用于数据库操作
from workflows import RouterAgent  # 导入路由 Agent，负责根据用户输入路由到不同的处理流程
import os  # 导入操作系统接口模块，用于文件路径操作和环境变量读取（类似 Java 中的 java.lang.System 和 java.io.File）
import re  # 导入正则表达式模块（类似 Java 中的 java.util.regex）
import logging  # 导入日志模块（类似 Java 中的 SLF4J/Logback）
import json  # 导入 JSON 处理模块（类似 Java 中的 Jackson/Gson）
import time  # 导入时间模块，用于计时（类似 Java 中的 System.currentTimeMillis()）

logger = logging.getLogger(__name__)  # 创建当前模块的 Logger 实例，__name__ 是 Python 内置变量，值为模块名

router = APIRouter()  # 创建 API 路由器实例，用于定义子路由（类似 Java 中的 @RestController），最后会挂载到 FastAPI 应用上

# 初始化 RouterAgent
router_agent = RouterAgent()  # 创建路由 Agent 实例，负责将用户请求路由到不同的处理工作流

# 问题类型判断器 - 判断问题是否应该返回文档引用
def should_return_sources(question: str) -> bool:  # 定义函数，参数 question 类型为 str，返回值类型为 bool（-> bool 是类型注解，类似 Java 方法的返回类型声明）
    """
    判断用户问题是否应该返回文档引用

    规则：
    1. 技术类、专业类、知识类问题 - 返回文档引用（优先匹配）
    2. 生活类、聊天类、娱乐类问题 - 不返回文档引用
    3. 基于关键词和问题模式判断
    """
    lower_question = question.lower()  # 将问题转为小写，便于不区分大小写地匹配关键词

    # 1. 技术类、专业类、知识类问题 - 返回文档引用（优先匹配）
    # 这些关键词表示可能需要专业知识
    knowledge_keywords = [  # 知识类关键词列表（类似 Java 中的 List<String>）
        # 技术相关 - 精确匹配模式
        "什么是", "如何", "怎么", "为什么", "原理", "机制", "工作",
        "定义", "概念", "术语", "解释", "说明",
        "步骤", "流程", "方法", "技巧", "策略",
        "优势", "缺点", "优缺点", "特点", "特性",
        "比较", "对比", "区别", "差异",
        "应用", "用途", "使用场景", "案例",
        "发展", "历史", "趋势", "未来",
        "标准", "规范", "协议", "框架",

        # 专业领域
        "编程", "代码", "算法", "数据结构", "数据库",
        "网络", "安全", "加密", "协议",
        "人工智能", "机器学习", "深度学习", "神经网络",
        "大数据", "云计算", "物联网", "区块链",
        "数学", "物理", "化学", "生物", "医学",
        "经济", "金融", "商业", "管理", "营销",
        "法律", "法规", "政策", "制度",
        "教育", "学习", "培训", "课程",

        # 文档相关
        "文档", "资料", "文件", "报告", "论文", "研究",
        "根据", "参考", "依据", "来源",
    ]

    for keyword in knowledge_keywords:  # 遍历所有知识类关键词（类似 Java 的 for-each 循环）
        # 检查关键词是否在问题中
        if keyword in lower_question:  # in 操作符检查字符串是否包含子串（类似 Java 的 contains()）
            # 特殊处理"什么是"和"是什么"的歧义
            if keyword == "什么是":  # 特殊处理"什么是"这个关键词，避免误匹配
                # "什么是"应该匹配"什么是一级封锁协议"，但不匹配"是什么地方"
                # 检查"什么是"是否出现在问题开头或前面有边界
                if lower_question.startswith("什么是"):  # startswith 检查字符串是否以指定前缀开头（类似 Java 的 startsWith()）
                    logger.info("AI request processing; content omitted")
                    return True  # 返回 True，表示应该返回文档引用
                # 检查"什么是"是否作为独立词出现
                pattern = r'(^|\s|[,.!?;:])什么是($|\s|[,.!?;:])'  # 正则表达式，匹配独立出现的"什么是"，r 前缀表示原始字符串（不转义）
                if re.search(pattern, lower_question):  # re.search 在字符串中搜索正则匹配（类似 Java 的 Pattern.matcher().find()）
                    logger.info("AI request processing; content omitted")
                    return True
            else:
                # 对于其他关键词，简单匹配
                logger.info("AI request processing; content omitted")
                return True

    # 2. 生活类、聊天类、娱乐类问题 - 不返回文档引用
    life_chat_keywords = [  # 生活类关键词列表
        # 问候聊天
        "你好", "您好", "hello", "hi", "早上好", "下午好", "晚上好",
        "最近好吗", "最近怎么样", "在干嘛", "在做什么",
        "谢谢", "感谢", "再见", "拜拜",

        # 知道/了解类闲聊
        "知道", "了解", "认识", "听说过", "听过",
        "你觉得", "你认为", "你怎么看", "你怎么想",

        # 日常生活
        "今天天气", "天气预报", "天气怎么样",
        "现在几点", "现在时间", "今天日期", "今天是",
        "有什么好吃的", "好吃", "美食", "餐厅", "饭店",
        "好玩", "旅游", "景点", "去哪里玩",
        "电影", "电视剧", "音乐", "歌曲", "娱乐",
        "购物", "买什么", "哪里买",
        "健康", "健身", "运动", "减肥",
        "感情", "恋爱", "爱情", "婚姻", "家庭",

        # 个人相关
        "你叫什么", "你是谁", "你是什么", "你的名字",
        "我帅吗", "我漂亮吗", "我聪明吗", "我怎么样",

        # 娱乐闲聊
        "讲个笑话", "说个故事", "唱首歌", "猜谜语",
        "星座", "运势", "算命", "占卜",

        # 询问意见/建议
        "可以吗", "行吗", "好吗", "对不对", "是不是",
        "能不能", "会不会", "要不要", "该不该",

        # 简单事实查询（可能不需要文档引用）
        "在哪里", "是什么地方", "哪个城市", "哪个国家",
        "多少钱", "价格", "贵不贵",
        "怎么去", "路线", "交通",
    ]

    for keyword in life_chat_keywords:  # 遍历所有生活类关键词
        if keyword in lower_question:  # 检查问题中是否包含生活类关键词
            # 特殊处理"是什么地方"的歧义
            if keyword == "是什么地方":  # 特殊处理"是什么地方"
                # "是什么地方"应该匹配"北京是什么地方"，但不匹配"什么是一级封锁协议"
                # 检查"是什么地方"是否出现在问题中
                if "是什么地方" in lower_question:
                    logger.info("AI request processing; content omitted")
                    return False  # 返回 False，表示不应返回文档引用
            else:
                # 对于其他生活类关键词，简单匹配
                logger.info("AI request processing; content omitted")
                return False

    # 3. 默认：对于不确定的问题，保守起见不返回文档引用
    # 只有明确的技术问题才返回引用，闲聊问题不返回
    logger.info("AI request processing; content omitted")
    return False  # 默认不返回文档引用

# 初始化核心服务
try:  # try-except 异常处理，类似 Java 中的 try-catch
    logger.info("Initializing DocumentParser...")  # 记录初始化日志
    parser = DocumentParser()  # 创建文档解析器实例
    logger.info("Using shared VectorStoreManager singleton...")  # 记录使用共享单例的日志
    logger.info("Initializing LLMService...")  # 记录初始化 LLM 服务的日志
    llm_service = LLMService()  # 创建大语言模型服务实例
    logger.info("Services initialized successfully.")  # 记录初始化成功的日志
except Exception as e:  # 捕获所有异常，Exception 是所有异常的基类（类似 Java 中的 catch(Exception e)）
    logger.error(f"Error initializing services: {e}")  # 记录初始化失败的错误日志
    # Consider whether to exit or just log, depending on whether the app can run partially.
    # For now, we'll let it run, but requests might fail.

class ParseRequest(BaseModel):  # 定义解析请求的数据模型，继承自 BaseModel（类似 Java 中的 DTO 类）
    file_path: str  # 文件路径字段，类型为字符串
    doc_id: int  # 文档 ID 字段，类型为整数

class ChatRequest(BaseModel):  # 定义聊天请求的数据模型
    question: str  # 用户问题字段
    context: str = "" # Optional, if context is passed directly (not used here)  # 上下文字段，默认值为空字符串（Python 中函数参数可以有默认值，类似 Java 方法的可选参数）
    conversation_id: str = None # Optional, for conversation memory  # 会话 ID，默认为 None（Python 中的 None 类似 Java 中的 null）
    username: str = None # Optional, if username is provided  # 用户名，默认为 None
    is_admin: bool = False # Optional, whether user is admin  # 是否管理员，默认为 False

class SummaryRequest(BaseModel):  # 定义摘要请求的数据模型
    question: str  # 问题字段，用于生成会话标题

# 移除中间件，改用在每个路由中记录请求时间
# APIRouter 不支持 middleware 方法，中间件只能添加到 FastAPI 应用实例

@router.post("/parse")  # 装饰器，注册 POST 请求处理函数，路径为 /parse，类似 Java 中的 @PostMapping("/parse")
async def parse_document(request: ParseRequest):  # 异步函数，参数类型为 ParseRequest，FastAPI 会自动解析和校验请求体
    """
    解析文档并存入向量库
    """
    start_time = time.time()  # 记录请求开始时间（time.time() 返回当前时间戳，单位为秒）
    try:  # 开始异常处理块
        # 判断 file_path 是 URL 还是本地路径
        is_url = request.file_path.startswith('http://') or request.file_path.startswith('https://')  # 判断路径是否为 HTTP/HTTPS URL

        if not is_url and not os.path.exists(request.file_path):  # 如果不是 URL 且本地文件不存在
            logger.warning(f"File not found: {request.file_path}")  # 记录警告日志
            raise HTTPException(status_code=404, detail="文件不存在")  # 抛出 HTTP 异常，返回 404 状态码（类似 Java 中的 ResponseStatusException）

        logger.info(f"Parsing document: {request.file_path}")  # 记录解析日志
        # Parse the document
        chunks = parser.parse(request.file_path)  # 调用解析器解析文档，返回文本块列表

        # Add metadata
        for chunk in chunks:  # 遍历所有文本块（类似 Java 的 for-each）
            chunk.metadata["doc_id"] = request.doc_id  # 为每个文本块添加文档 ID 元数据
            chunk.metadata["source"] = request.file_path  # 为每个文本块添加文件来源元数据

        logger.info(f"Generated {len(chunks)} chunks. Adding to vector store...")  # 记录生成的文本块数量
        try:  # 嵌套 try-except，单独处理向量存储可能的异常
            vector_store.add_documents(chunks)  # 将文本块添加到向量存储中
        except Exception as ve:  # 捕获向量存储异常
            logger.error(f"Vector store add_documents failed: {type(ve).__name__}: {ve}", exc_info=True)  # 记录详细错误信息，exc_info=True 会打印完整堆栈
            raise ve  # 重新抛出异常（类似 Java 中的 throw）

        logger.info(f"Saving chunks to MySQL database...")  # 记录保存到数据库的日志
        mysql_client.insert_chunks(request.doc_id, [  # 将文本块保存到 MySQL 数据库
            {"page_content": chunk.page_content, "chunk_index": chunk.metadata.get("chunk_index", i)}  # 构造每个文本块的字典（类似 Java 中的 Map），get() 方法有默认值
            for i, chunk in enumerate(chunks)  # 列表推导式（类似 Java Stream 的 map+collect），enumerate() 同时获取索引和元素
        ])

        process_time = time.time() - start_time  # 计算处理耗时（秒）
        logger.info(  # 记录结构化请求日志
            json.dumps({  # 将字典转为 JSON 字符串
                "method": "POST",  # 请求方法
                "path": "/api/parse",  # 请求路径
                "status_code": 200,  # HTTP 状态码
                "process_time": process_time  # 处理耗时
            })
        )
        return {"status": "success", "chunks_count": len(chunks)}  # 返回成功响应，包含文本块数量
    except HTTPException as e:  # 捕获 HTTP 异常（类似 Java 中 catch 特定异常类型）
        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/parse",
                "status_code": e.status_code,
                "process_time": process_time
            })
        )
        raise  # 直接重新抛出 HTTP 异常，不做额外处理（类似 Java 中的 throw，单独的 raise 保留原始堆栈）
    except Exception as e:  # 捕获其他所有异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error parsing document: {type(e).__name__}: {str(e)}", exc_info=True)  # 记录错误日志，type(e).__name__ 获取异常类名
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/parse",
                "status_code": 500,
                "process_time": process_time
            })
        )
        # 不返回具体错误信息，避免泄露内部实现细节
        raise HTTPException(status_code=500, detail="文档解析失败")  # 返回 500 错误，隐藏内部细节

@router.post("/ask")  # 装饰器，注册 POST /ask 路由
async def ask_question(request: ChatRequest):  # 异步问答接口，参数自动校验为 ChatRequest 类型
    """
    问答接口 - 使用 RouterAgent 进行任务路由
    """
    start_time = time.time()  # 记录请求开始时间
    try:  # 开始异常处理
        logger.info("AI request processing; content omitted")

        # 处理身份相关问题
        lower_question = request.question.lower()  # 将问题转为小写
        identity_keywords = ["我是谁", "我叫什么", "我的名字", "我的身份"]  # 身份相关关键词列表
        if any(keyword in lower_question for keyword in identity_keywords) and request.username:  # any() 函数检查是否有任意一个关键词匹配（类似 Java Stream 的 anyMatch()）
            logger.info("AI request processing; content omitted")
            answer = f"你是 {request.username}，是本系统的注册用户。"  # 生成身份回答
            response = {"answer": answer, "sources": [], "task_type": "chitchat"}  # 构造直接响应，不调用 Agent
        else:  # 非身份问题，走正常路由流程
            # 使用 RouterAgent 进行任务路由
            result = router_agent.route(  # 调用路由 Agent 的 route 方法进行任务分发
                input_text=request.question,  # 用户问题文本
                conversation_id=request.conversation_id,  # 会话 ID
                context=request.context,  # 上下文信息
                username=request.username,  # 用户名
                is_admin=request.is_admin  # 是否管理员
            )

            # 构建响应
            response = {  # 构造响应字典
                "answer": result.get("answer", ""),  # 获取回答，默认空字符串
                "sources": result.get("sources", []),  # 获取文档引用来源，默认空列表
                "task_type": result.get("task_type", "unknown")  # 获取任务类型，默认 "unknown"
            }

        logger.info(f"Response generated successfully, task_type: {response.get('task_type')}")  # 记录响应生成成功

        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录结构化请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/ask",
                "status_code": 200,
                "process_time": process_time
            })
        )
        return response  # 返回问答结果
    except HTTPException as e:  # 捕获 HTTP 异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/ask",
                "status_code": e.status_code,
                "process_time": process_time
            })
        )
        raise  # 直接重新抛出 HTTP 异常
    except Exception as e:  # 捕获其他异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error processing question: {str(e)}")  # 记录错误日志
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/ask",
                "status_code": 500,
                "process_time": process_time
            })
        )
        # 不返回具体错误信息，避免泄露内部实现细节
        raise HTTPException(status_code=500, detail="问答处理失败")  # 返回 500 错误

@router.post("/ask/stream")  # 装饰器，注册 POST /ask/stream 路由
async def ask_question_stream(request: ChatRequest):  # 异步流式问答接口
    """
    流式问答接口 (Server-Sent Events) - 使用 RouterAgent
    """
    start_time = time.time()  # 记录请求开始时间

    async def event_generator():  # 定义异步生成器函数（生成器是 Python 特有概念，使用 yield 逐步产出数据，类似 Java 中的 Flux/Flowable）
        try:  # 开始异常处理
            logger.info("AI request processing; content omitted")

            # 处理身份相关问题
            lower_question = request.question.lower()  # 转为小写
            identity_keywords = ["我是谁", "我叫什么", "我的名字", "我的身份"]  # 身份关键词列表
            if any(keyword in lower_question for keyword in identity_keywords) and request.username:  # 检查是否为身份问题且有用户名
                logger.info("AI request processing; content omitted")
                answer = f"你是 {request.username}，是本系统的注册用户。"  # 生成身份回答
                # 流式返回身份回答
                for char in answer:  # 逐字符遍历回答文本
                    yield f"data: {json.dumps({'type': 'token', 'content': char})}\n\n"  # yield 是 Python 生成器的关键字，每次产出一个 SSE 事件（类似 Java Flux 的 next() 信号）
                yield f"data: {json.dumps({'type': 'end', 'content': answer, 'task_type': 'chitchat'})}\n\n"  # 发送结束事件
                return  # 提前返回，结束生成器（类似 Java 中的 return）

            # 使用 RouterAgent 进行流式任务路由
            for event_data in router_agent.route_stream(  # 遍历路由 Agent 的流式输出
                input_text=request.question,  # 用户问题
                context=request.context,  # 上下文
                username=request.username,  # 用户名
                is_admin=request.is_admin  # 是否管理员
            ):
                yield f"data: {event_data}\n\n"  # 将每个事件以 SSE 格式产出（SSE 格式要求每条消息以 "data: " 开头，两个换行符结尾）

            process_time = time.time() - start_time  # 计算处理耗时
            logger.info(  # 记录请求日志
                json.dumps({
                    "method": "POST",
                    "path": "/api/ask/stream",
                    "status_code": 200,
                    "process_time": process_time
                })
            )

        except Exception as e:  # 捕获异常
            process_time = time.time() - start_time  # 计算处理耗时
            logger.error(f"Error in streaming question: {str(e)}")  # 记录错误日志
            logger.info(  # 记录请求日志
                json.dumps({
                    "method": "POST",
                    "path": "/api/ask/stream",
                    "status_code": 500,
                    "process_time": process_time
                })
            )
            yield f"data: {json.dumps({'type': 'error', 'content': '流式问答处理失败'})}\n\n"  # 通过 SSE 发送错误事件

    return StreamingResponse(  # 返回流式响应对象（类似 Java 中的 ResponseEntity<Flux<String>>）
        event_generator(),  # 传入异步生成器作为响应体
        media_type="text/event-stream",  # SSE 的 MIME 类型
        headers={  # 设置响应头
            "Cache-Control": "no-cache",  # 禁用缓存，确保实时推送
            "Connection": "keep-alive",  # 保持长连接
            "X-Accel-Buffering": "no"  # 禁用Nginx缓冲
        }
    )

@router.post("/delete")  # 装饰器，注册 POST /delete 路由
async def delete_document(request: ParseRequest):  # 异步删除文档接口
    """
    删除文档的向量索引
    """
    start_time = time.time()  # 记录请求开始时间
    try:  # 开始异常处理
        if request.doc_id:  # 检查是否提供了文档 ID
            logger.info(f"Deleting document with doc_id: {request.doc_id}")  # 记录删除日志
            vector_store.delete_document(request.doc_id)  # 调用向量存储的删除方法

            process_time = time.time() - start_time  # 计算处理耗时
            logger.info(  # 记录请求日志
                json.dumps({
                    "method": "POST",
                    "path": "/api/delete",
                    "status_code": 200,
                    "process_time": process_time
                })
            )
            return {"status": "success", "message": f"Document {request.doc_id} deleted"}  # 返回成功响应
        else:  # 未提供文档 ID
             logger.warning("doc_id is required")  # 记录警告
             raise HTTPException(status_code=400, detail="doc_id is required")  # 抛出 400 错误
    except HTTPException as e:  # 捕获 HTTP 异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/delete",
                "status_code": e.status_code,
                "process_time": process_time
            })
        )
        raise  # 重新抛出 HTTP 异常
    except Exception as e:  # 捕获其他异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error deleting document: {str(e)}")  # 记录错误日志
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/delete",
                "status_code": 500,
                "process_time": process_time
            })
        )
        # 不返回具体错误信息，避免泄露内部实现细节
        raise HTTPException(status_code=500, detail="文档删除失败")  # 返回 500 错误

@router.post("/summary")  # 装饰器，注册 POST /summary 路由
async def generate_summary(request: SummaryRequest):  # 异步生成摘要接口
    """
    生成会话标题
    """
    start_time = time.time()  # 记录请求开始时间
    try:  # 开始异常处理
        title = llm_service.generate_title(request.question)  # 调用 LLM 服务生成会话标题
        logger.info(f"Generated summary: {title}")  # 记录生成的标题

        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/summary",
                "status_code": 200,
                "process_time": process_time
            })
        )
        return {"title": title}  # 返回生成的标题
    except HTTPException as e:  # 捕获 HTTP 异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/summary",
                "status_code": e.status_code,
                "process_time": process_time
            })
        )
        raise  # 重新抛出 HTTP 异常
    except Exception as e:  # 捕获其他异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error generating summary: {str(e)}")  # 记录错误日志
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/summary",
                "status_code": 500,
                "process_time": process_time
            })
        )
        # 不返回具体错误信息，避免泄露内部实现细节
        raise HTTPException(status_code=500, detail="标题生成失败")  # 返回 500 错误

@router.get("/vector-store/stats")  # 装饰器，注册 GET /vector-store/stats 路由
async def get_vector_store_stats():  # 异步获取向量库统计信息接口
    """
    获取向量库统计信息
    """
    start_time = time.time()  # 记录请求开始时间
    try:  # 开始异常处理
        stats = vector_store.get_stats()  # 调用向量存储管理器获取统计信息

        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "GET",
                "path": "/api/vector-store/stats",
                "status_code": 200,
                "process_time": process_time
            })
        )
        return stats  # 返回统计信息
    except Exception as e:  # 捕获异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error getting vector store stats: {str(e)}")  # 记录错误日志
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "GET",
                "path": "/api/vector-store/stats",
                "status_code": 500,
                "process_time": process_time
            })
        )
        raise HTTPException(status_code=500, detail="获取向量库统计信息失败")  # 返回 500 错误

@router.post("/vector-store/migrate")  # 装饰器，注册 POST /vector-store/migrate 路由
async def migrate_to_milvus():  # 异步迁移数据到 Milvus 接口
    """
    将FAISS数据迁移到Milvus
    """
    start_time = time.time()  # 记录请求开始时间
    try:  # 开始异常处理
        if not vector_store.use_milvus:  # 检查当前是否配置使用 Milvus
            raise HTTPException(status_code=400, detail="当前未使用Milvus，无法迁移")  # 未配置则返回 400 错误

        success = vector_store.migrate_faiss_to_milvus()  # 执行 FAISS 到 Milvus 的数据迁移

        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/vector-store/migrate",
                "status_code": 200,
                "process_time": process_time
            })
        )

        if success:  # 迁移完全成功
            return {"status": "success", "message": "数据迁移成功"}  # 返回成功响应
        else:  # 迁移部分完成
            return {"status": "partial", "message": "迁移完成但可能有部分数据未迁移"}  # 返回部分成功响应

    except HTTPException as e:  # 捕获 HTTP 异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/vector-store/migrate",
                "status_code": e.status_code,
                "process_time": process_time
            })
        )
        raise  # 重新抛出 HTTP 异常
    except Exception as e:  # 捕获其他异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error migrating to Milvus: {str(e)}")  # 记录错误日志
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "POST",
                "path": "/api/vector-store/migrate",
                "status_code": 500,
                "process_time": process_time
            })
        )
        raise HTTPException(status_code=500, detail="数据迁移失败")  # 返回 500 错误

@router.delete("/vector-store/collection")  # 装饰器，注册 DELETE /vector-store/collection 路由
async def delete_vector_collection():  # 异步删除整个向量库接口
    """
    删除整个向量库（慎用）
    """
    start_time = time.time()  # 记录请求开始时间
    try:  # 开始异常处理
        # 添加确认机制（实际生产环境需要更严格的权限控制）
        vector_store.delete_collection()  # 调用向量存储管理器删除整个集合（危险操作）

        process_time = time.time() - start_time  # 计算处理耗时
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "DELETE",
                "path": "/api/vector-store/collection",
                "status_code": 200,
                "process_time": process_time
            })
        )
        return {"status": "success", "message": "向量库已删除"}  # 返回删除成功响应
    except Exception as e:  # 捕获异常
        process_time = time.time() - start_time  # 计算处理耗时
        logger.error(f"Error deleting vector collection: {str(e)}")  # 记录错误日志
        logger.info(  # 记录请求日志
            json.dumps({
                "method": "DELETE",
                "path": "/api/vector-store/collection",
                "status_code": 500,
                "process_time": process_time
            })
        )
        raise HTTPException(status_code=500, detail="删除向量库失败")  # 返回 500 错误
