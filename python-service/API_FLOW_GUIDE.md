# AI 知识库系统 - 接口调用流程梳理

> 面向有 Java 基础的 Python 初学者，详细说明每个 API 接口从入口到响应的完整链路。

---

## 目录

1. [项目结构概览](#项目结构概览)
2. [应用启动流程 (main.py)](#应用启动流程)
3. [API 接口流程](#api-接口流程)
   - [POST /api/ask - 问答接口](#1-post-apiask---问答接口主链路)
   - [POST /api/ask/stream - 流式问答](#2-post-apiaskstream---流式问答)
   - [POST /api/parse - 文档解析](#3-post-apiparse---文档解析)
   - [POST /api/delete - 删除文档](#4-post-apidelete---删除文档)
   - [POST /api/summary - 生成会话标题](#5-post-apisummary---生成会话标题)
   - [POST /api/agent/run - Agent 执行](#6-post-apiagentrun---agent-执行)
   - [POST /api/agent/run/stream - 流式 Agent 执行](#7-post-apiagentrunstream---流式-agent-执行)
   - [GET /api/vector-store/stats - 向量库统计](#8-get-apivector-storestats)
   - [POST /api/vector-store/migrate - 数据迁移](#9-post-apivector-storemigrate)
   - [DELETE /api/vector-store/collection - 删除向量库](#10-delete-apivector-storecollection)
   - [GET /api/agent/tools - 列出工具](#11-get-apiagenttools)
   - [GET /api/agent/stats - 任务统计](#12-get-apiagentstats)
4. [核心子系统流程](#核心子系统流程)
   - [意图分类流程](#意图分类流程-intentclassifier)
   - [路由 Agent 分发流程](#路由-agent-分发流程-routeragent)
   - [知识问答三级链路](#知识问答三级链路-knowledgeqaagent)
   - [闲聊 Agent 流程](#闲聊-agent-流程-chitchatagent)
   - [管理助手 Agent 流程](#管理助手-agent-流程-admincopilotagent)
   - [知识巡检 Agent 流程](#知识巡检-agent-流程-inspectionagent)
   - [推理 Agent 流程](#推理-agent-流程-reasoningagent)
   - [运营分析 Agent 流程](#运营分析-agent-流程-opsagent)
5. [工具系统流程](#工具系统流程)
6. [数据流向图](#数据流向图)
7. [Java 开发者 Python 速查](#java-开发者-python-速查)

---

## 项目结构概览

```
python-service/
├── main.py                 # 应用入口（类似 Java 的 Application.java / Main.java）
├── api/                    # API 路由层（类似 Java Spring 的 @RestController）
│   ├── routes.py           # 主要接口：ask, parse, delete, summary
│   └── agent_routes.py     # Agent 接口：agent/run, agent/stats
├── middleware/              # 中间件（类似 Java Spring 的 Filter/Interceptor）
│   └── middlewares.py       # 接口耗时统计中间件
├── core/                   # 核心基础设施（类似 Java 的 service/util 层）
│   ├── config.py           # 统一配置管理（类似 Spring 的 application.yml）
│   ├── llm.py              # LLM 大模型服务（调用通义千问 API）
│   ├── mysql_client.py     # MySQL 数据库客户端
│   ├── redis_client.py     # Redis 缓存客户端（存储会话记忆）
│   ├── vector_store.py     # 向量存储（Milvus/FAISS，存储文档向量）
│   ├── parser.py           # 文档解析器（PDF/Word/图片 OCR）
│   ├── text_splitter.py    # 文本切分器（把长文档切成小段）
│   └── reranker.py         # 重排序器（对检索结果重新排序）
├── intent/                 # 意图识别（类似 Java 的策略模式 + 工厂模式）
│   └── classifier.py       # 意图分类器（判断用户是闲聊还是知识问答）
├── agent/                  # Agent 编排系统（类似 Java 的工作流引擎）
│   ├── state.py            # 状态管理（类似 Java 的状态机）
│   ├── events.py           # 事件系统（类似 Java 的 EventBus / 观察者模式）
│   ├── planner.py          # 任务规划器（决定执行哪些步骤）
│   ├── executor.py         # 步骤执行器（执行具体步骤）
│   ├── orchestrator.py     # 编排器（协调规划、执行、事件）
│   ├── memory_agent.py     # 记忆管理（读写对话历史和用户画像）
│   └── policies.py         # 策略管理（重试、降级、安全守卫等）
├── tools/                  # 工具系统（类似 Java 的插件机制）
│   ├── base.py             # 工具基类（类似 Java 的 abstract class）
│   ├── registry.py         # 工具注册器（单例模式，类似 Spring 的 IOC 容器）
│   ├── knowledge_search.py # 知识库检索工具
│   ├── memory_read.py      # 会话记忆读取工具
│   ├── memory_write.py     # 会话记忆写入工具
│   ├── question_rewrite.py # 问题改写工具
│   ├── rerank.py           # 重排序工具
│   ├── doc_summary.py      # 文档摘要工具
│   ├── ocr_extract.py      # OCR 提取工具
│   ├── execution.py        # 工具执行跟踪器
│   └── citation.py         # 引用整合器
└── workflows/              # 工作流 Agent（类似 Java 的 Service 层，处理不同业务）
    ├── router_agent.py     # 路由 Agent（根据意图分发到不同 Agent）
    ├── knowledge_qa_agent.py   # 知识问答 Agent
    ├── chitchat_agent.py       # 闲聊 Agent
    ├── admin_copilot_agent.py  # 管理助手 Agent
    ├── inspection_agent.py     # 知识巡检 Agent
    ├── reasoning_agent.py      # 推理 Agent（复杂问题）
    ├── retrieval_agent.py      # 检索 Agent
    └── ops_agent.py            # 运营分析 Agent
```

---

## 应用启动流程

**文件**: [main.py](main.py)

```
启动命令: python main.py
         ↓
    加载 .env 环境变量
         ↓
    创建 FastAPI 应用实例 (类似 SpringBoot 启动)
         ↓
    注册中间件:
    ├── TimingMiddleware  → 接口耗时统计（类似 Spring 的 Interceptor）
    └── CORSMiddleware    → 跨域配置（类似 @CrossOrigin）
         ↓
    注册路由:
    ├── /api/* → routes.py      (主要接口)
    ├── /api/* → agent_routes.py (Agent 接口)
    ├── /      → 根路径健康检查
    └── /health → 详细健康检查
         ↓
    import tools  → 触发工具注册（类似 @PostConstruct）
         ↓
    uvicorn.run() → 启动 HTTP 服务器 (监听 127.0.0.1:8000)
```

**Java 类比**:
- `FastAPI()` ≈ `SpringApplication.run()`
- `app.add_middleware()` ≈ 注册 Filter
- `app.include_router()` ≈ `@ComponentScan` 扫描 Controller
- `uvicorn.run()` ≈ `Tomcat` 服务器

---

## API 接口流程

### 1. POST /api/ask - 问答接口（主链路）

**文件**: [api/routes.py](api/routes.py) → `ask_question()`

这是最核心的接口，用户提问时的完整调用链路：

```
前端 POST /api/ask
    请求体: { question: "什么是一级封锁协议?", context: "", conversation_id: "xxx", username: "张三" }
         │
         ↓
    ┌─ [1] 身份问题判断 ──────────────────────────────────────────┐
    │   检查是否包含 "我是谁" / "我叫什么" / "我的名字" / "我的身份"  │
    │   且 username 不为空                                          │
    │                                                               │
    │   如果是 → 直接返回 "你是 张三，是本系统的注册用户。"          │
    │   跳过后续所有步骤                                             │
    └───────────────────────────────────────────────────────────────┘
         │ (不是身份问题)
         ↓
    [2] RouterAgent.route()  ← 路由 Agent，决定走哪条处理链路
         │
         ↓ (详见下方 路由 Agent 分发流程)
         │
    返回: { answer: "...", sources: [...], task_type: "knowledge_qa" }
```

### 2. POST /api/ask/stream - 流式问答

**文件**: [api/routes.py](api/routes.py) → `ask_question_stream()`

```
前端 POST /api/ask/stream
         │
         ↓
    ┌─ [1] 身份问题判断（同上）────────────────────────────┐
    │   如果是 → 逐字流式返回身份回答                        │
    │   yield: data: {"type": "token", "content": "你"}     │
    │   yield: data: {"type": "token", "content": "是"}     │
    │   ...                                                  │
    │   yield: data: {"type": "end", ...}                    │
    └──────────────────────────────────────────────────────┘
         │ (不是身份问题)
         ↓
    [2] RouterAgent.route_stream()
         │
         ↓
    返回 SSE (Server-Sent Events) 流:
    data: {"type": "routed", "task_type": "knowledge_qa"}
    data: {"type": "token", "content": "一"}
    data: {"type": "token", "content": "级"}
    ...
    data: {"type": "end", "content": {"answer": "...", "sources": [...]}}

    【Java 类比】SSE ≈ 响应式流 (Flux/Flowable)，不是 WebSocket
```

### 3. POST /api/parse - 文档解析

**文件**: [api/routes.py](api/routes.py) → `parse_document()`

```
前端 POST /api/parse
    请求体: { file_path: "/path/to/doc.pdf", doc_id: 123 }
         │
         ↓
    [1] 判断路径是 URL 还是本地文件
        ├── http:// 或 https:// → 是 URL
        └── 其他 → 检查本地文件是否存在
            └── 不存在 → 返回 404 "文件不存在"
         │
         ↓
    [2] DocumentParser.parse()  ← 解析文档
        │
        ├── .pdf  → PyPDFLoader 加载
        ├── .docx → Docx2txtLoader 加载
        ├── .txt  → TextLoader 加载
        ├── .md   → TextLoader 加载
        ├── 图片  → OCR 文字识别 (Tesseract)
        │   ├── 预处理：灰度化 → 缩放 → 多语言尝试
        │   ├── 尝试中文+英文 → 纯中文 → 纯英文 → 繁体中文
        │   └── 全部失败 → "图片中未识别到文字"
        └── 其他 → 返回 500 "不支持的文件类型"
         │
         ↓
    [3] 为每个 chunk 添加 metadata (doc_id, source)
         │
         ↓
    [4] vector_store.add_documents()  ← 存入向量数据库
        ├── Milvus 模式 → 存入 Milvus 向量库
        └── FAISS 模式  → 存入本地 FAISS 索引
         │
         ↓
    [5] mysql_client.insert_chunks()  ← 存入 MySQL 数据库
         │
         ↓
    返回: { status: "success", chunks_count: 25 }
```

### 4. POST /api/delete - 删除文档

```
前端 POST /api/delete
    请求体: { doc_id: 123, file_path: "..." }
         │
         ↓
    [1] 检查 doc_id 是否存在
        └── 不存在 → 返回 400
         │
         ↓
    [2] vector_store.delete_document(123)
        ├── Milvus → 执行 delete 表达式删除
        └── FAISS  → 遍历 docstore 找到对应 ID 删除
         │
         ↓
    返回: { status: "success", message: "Document 123 deleted" }
```

### 5. POST /api/summary - 生成会话标题

```
前端 POST /api/summary
    请求体: { question: "什么是一级封锁协议" }
         │
         ↓
    [1] LLMService.generate_title()
        ├── 构建 Prompt："请生成简短标题，10字以内"
        ├── 调用通义千问 API
        └── 返回标题文本
         │
         ↓
    返回: { title: "一级封锁协议" }
```

### 6. POST /api/agent/run - Agent 执行

**文件**: [api/agent_routes.py](api/agent_routes.py) → `run_agent()`

```
前端 POST /api/agent/run
    请求体: { input: "什么是一级封锁协议?", run_id: "xxx", trace_id: "xxx", is_admin: false }
         │
         ↓
    [1] RouterAgent.route()  ← 同 /api/ask 的路由逻辑
         │
         ↓
    [2] 记录任务统计 (task_stats)
         │
         ↓
    返回: {
        run_id: "xxx",
        trace_id: "xxx",
        status: "completed",
        answer: "...",
        sources: [...],
        task_type: "knowledge_qa",
        steps: [],
        tool_calls: []
    }
```

### 7. POST /api/agent/run/stream - 流式 Agent 执行

```
前端 POST /api/agent/run/stream
         │
         ↓
    [1] RouterAgent.route_stream()
         │
         ↓
    返回 SSE 流（同 /api/ask/stream）
```

### 8. GET /api/vector-store/stats

```
前端 GET /api/vector-store/stats
         │
         ↓
    vector_store.get_stats()
    ├── Milvus → 返回行数、分区数
    └── FAISS  → 返回文档数量
         │
         ↓
    返回: { using_milvus: true, row_count: 1000, ... }
```

### 9. POST /api/vector-store/migrate

```
前端 POST /api/vector-store/migrate
         │
         ↓
    [1] 检查是否使用 Milvus
        └── 不是 → 返回 400
         │
         ↓
    [2] 加载 FAISS 索引
         │
         ↓
    [3] 提取所有文档 → 添加到 Milvus
         │
         ↓
    [4] 备份原 FAISS 数据
         │
         ↓
    返回: { status: "success", message: "数据迁移成功" }
```

### 10. DELETE /api/vector-store/collection

```
前端 DELETE /api/vector-store/collection
         │
         ↓
    vector_store.delete_collection()
    ├── Milvus → utility.drop_collection()
    └── FAISS  → shutil.rmtree() + 重置为 None
         │
         ↓
    返回: { status: "success", message: "向量库已删除" }
```

### 11. GET /api/agent/tools

```
前端 GET /api/agent/tools
         │
         ↓
    tool_registry.get_all_tools() → 遍历所有注册工具
         │
         ↓
    返回: { tools: [{ name, description, input_schema, ... }, ...] }
```

### 12. GET /api/agent/stats

```
前端 GET /api/agent/stats
         │
         ↓
    [1] 遍历 task_stats 字典，计算各类型统计
    [2] 计算总数、成功率、平均耗时
    [3] 获取关键词统计
         │
         ↓
    返回: {
        task_stats: [{ task_type, total, success, failed, success_rate, avg_duration_ms }],
        summary: { total, success, failed, overall_success_rate },
        keyword_stats: { chitchat_keywords: 50, knowledge_qa_keywords: 100, ... }
    }
```

---

## 核心子系统流程

### 意图分类流程 (IntentClassifier)

**文件**: [intent/classifier.py](intent/classifier.py)

```
用户输入: "什么是一级封锁协议?"
         │
         ↓
    IntentClassifier.classify(input_text, is_admin=False)
         │
    ┌────┴─────┐
    │ 尝试 LLM │ ← 优先使用大模型判断意图
    │ 分类     │
    └────┬─────┘
         │
    ┌────┴──────────────┐
    │                   │
    成功                失败/不可用
    │                   │
    ↓                   ↓
    返回 LLM 结果    回退到关键词匹配（Fallback）
                        │
                        ↓
                 _classify_with_keywords()
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    身份查询优先    管理员模式优先    普通模式
         │              │              │
    "我是谁"等    检查 admin_keywords  检查各类关键词得分
         │              │              │
    → IDENTITY_QUERY  → ADMIN_OP     计算各分类得分:
         │              │             - chitchat_score
         │              │             - knowledge_score
         │              │             - admin_score
         │              │             - inspection_score
         │              │             - emotion_score
         │              │              │
         │              │         根据得分和文本长度
         │              │         选择最终意图
         │              │              │
         └──────────────┴──────────────┘
                        │
                        ↓
    IntentResult:
    {
        intent: IntentType.KNOWLEDGE_QA,  # 意图类型
        confidence: 0.95,                  # 置信度
        reasoning: "命中3个知识关键词"     # 判断理由
    }
```

**意图类型 (IntentType)**:
| 意图 | 说明 | 对应 Agent |
|------|------|-----------|
| `CHITCHAT` | 闲聊、问候、日常对话 | ChitChatAgent |
| `KNOWLEDGE_QA` | 技术问题、知识问答 | KnowledgeQAAgent |
| `ADMIN_OPERATION` | 后台管理、统计分析 | AdminCopilotAgent |
| `KNOWLEDGE_INSPECTION` | 知识巡检、质量检查 | InspectionAgent |
| `IDENTITY_QUERY` | 身份查询 | ChitChatAgent |
| `UNKNOWN` | 无法确定 | KnowledgeQAAgent |

---

### 路由 Agent 分发流程 (RouterAgent)

**文件**: [workflows/router_agent.py](workflows/router_agent.py)

```
RouterAgent.route(input_text, conversation_id, user_id, context, is_admin)
         │
         ↓
    [1] classify_task(input_text, is_admin)
        │
        ├── IntentClassifier.classify() → 得到 IntentType
        ├── IntentType → TaskType 映射
        │
        └── 复杂度判断 classify_complexity()
            │
            ├── 包含 "对比/比较/优缺点/区别" + 长度>15 → "complex"
            ├── 包含代词 "它/这个/那个" 或 长度<10     → "medium"
            └── 其他                                    → "simple"
            │
            如果 TaskType 是 KNOWLEDGE_QA 且复杂度是 complex → 升级为 REASONING
         │
         ↓
    [2] 根据 TaskType 分发到对应 Agent
         │
         ├── CHITCHAT              → ChitChatAgent.chat()
         ├── KNOWLEDGE_QA          → KnowledgeQAAgent.ask()
         ├── ADMIN_COPILOT         → AdminCopilotAgent.handle()
         ├── KNOWLEDGE_INSPECTION  → InspectionAgent.inspect()
         ├── REASONING             → ReasoningAgent.reason()
         └── UNKNOWN               → KnowledgeQAAgent.ask()（默认走知识问答）
         │
         ↓
    返回: { answer, sources, has_sources, task_type }
```

---

### 知识问答三级链路 (KnowledgeQAAgent)

**文件**: [workflows/knowledge_qa_agent.py](workflows/knowledge_qa_agent.py)

```
KnowledgeQAAgent.ask(question, conversation_id, user_id, context)
         │
         ↓
    [1] 读取会话记忆
        conversation_memory_read 工具 → Redis 获取最近对话
         │
         ↓
    [2] 合并上下文: 用户传入的 context + 会话记忆
         │
         ↓
    [3] 判断复杂度，选择链路:
         │
    ┌────┴──────────────────────────────────────────────────┐
    │                                                         │
    L1 简化链路 (80%请求, ~2-3s)        L2 标准链路 (15%请求, ~5-8s)
    │                                    │
    ↓                                    ↓
    _ask_l1()                          _ask_l2()
    │                                    │
    [1] 直接向量检索                    [1] RetrievalAgent.retrieve()
        vector_store.search()              │
        k=5, 不使用 rerank               ├── 问题改写（LLM）
    │                                    │   "它是什么?" → "一级封锁协议是什么?"
    [2] 如果没找到文档                   │
        ├── 有上下文 → LLM 直接回答     ├── 向量检索（多召回）
        └── 没上下文 → "知识库中未找到"  │   k=15, 获取更多候选
    │                                    │
    [3] LLM 生成回答                    ├── 重排序（Rerank）
        get_answer(question, docs)        │   按相关性重新排序，取 top 5
    │                                    │
    [4] 构建引用来源                    │
    │                                    [2] LLM 生成回答
    [5] 保存到会话记忆                      get_answer(question, reranked_docs)
    │                                    │
    ↓                                    [3] 整合引用 (Citation)
    返回结果                             │
                                         [4] 保存到会话记忆
                                         │
                                         ↓
                                         返回结果
```

**注意**: L3 推理链路由 RouterAgent 直接分发到 ReasoningAgent，不经过 KnowledgeQAAgent。

---

### 闲聊 Agent 流程 (ChitChatAgent)

**文件**: [workflows/chitchat_agent.py](workflows/chitchat_agent.py)

```
ChitChatAgent.chat(question, conversation_id, user_id, context)
         │
         ↓
    [1] 读取会话记忆 (如果 conversation_id 存在)
         │
         ↓
    [2] _generate_chitchat_response()
         │
    ┌────┴───────────────────────────────────┐
    │                                          │
    简单规则匹配 (<1ms)                    需要 LLM 生成
    │                                          │
    ├── "你好/hi"  → 固定问候语              ├── "你知道X吗" → LLM 回复
    ├── "谢谢"     → 固定感谢语              ├── 天气/时间类 → LLM 回复
    ├── "你是谁"   → 固定身份介绍            ├── 讲笑话     → LLM 生成笑话
    └── ...                                    ├── 情感类     → LLM 共情回复
                                               └── 其他       → LLM 通用回复
                                               │
                                               ↓
                                           _llm_chitchat()
                                           构建友好聊天的 Prompt
                                           调用通义千问生成回复
                                               │
    ┌──────────────────────────────────────────┘
    │
    ↓
    [3] 保存到会话记忆
         │
         ↓
    返回: { answer: "...", sources: [], has_sources: false, task_type: "chitchat" }
```

---

### 管理助手 Agent 流程 (AdminCopilotAgent)

**文件**: [workflows/admin_copilot_agent.py](workflows/admin_copilot_agent.py)

```
AdminCopilotAgent.handle(question, ...)
         │
         ↓
    [1] _parse_operation(question) → 解析操作类型
        │
        ├── "知识缺口/未命中"        → knowledge_gap
        ├── "运营报告/全报告"        → full_ops_report
        ├── "用户/活跃度"            → user_activity
        ├── "统计/报表/数据"         → stats
        ├── "知识/巡检/检查"         → knowledge_inspection
        ├── "热门问题"               → hot_questions
        ├── "增长趋势"               → knowledge_growth
        ├── "成功率"                 → agent_success_rate
        ├── "工具调用/失败"           → tool_call_failures
        └── 默认                     → stats
         │
         ↓
    [2] _execute_operation(operation, question)
         │
         ├── stats            → _get_stats()              → 查 MySQL 各表数量
         ├── knowledge_inspection → InspectionAgent.inspect("full")
         ├── knowledge_gap    → OpsAgent.analyze("knowledge_gap")
         ├── user_activity    → OpsAgent.analyze("user_activity")
         ├── full_ops_report  → OpsAgent.analyze("full_report")
         ├── hot_questions    → OpsAgent.analyze("hot_questions")
         ├── knowledge_growth → OpsAgent.analyze("knowledge_growth")
         ├── agent_success_rate → OpsAgent.analyze("agent_success_rate")
         └── tool_call_failures → OpsAgent.analyze("tool_call_failures")
         │
         ↓
    返回: { answer: "📊 统计信息...", sources: [], task_type: "admin_copilot" }
```

---

### 知识巡检 Agent 流程 (InspectionAgent)

**文件**: [workflows/inspection_agent.py](workflows/inspection_agent.py)

```
InspectionAgent.inspect(inspection_type, ...)
         │
    ┌────┴──────────────────────────────────────────────┐
    │                                                     │
    inspection_type:                                      │
    │                                                     │
    ├── "duplicate"   → _check_duplicate_docs()           │
    │   查询: 相同标题的文档对                              │
    │   SQL: SELECT ... JOIN ON title 相同且 id 不同       │
    │                                                     │
    ├── "low_quality" → _check_low_quality_chunks()       │
    │   查询: 内容 < 50字 或 > 5000字 的片段                │
    │   SQL: WHERE LENGTH(content) < 50 OR > 5000         │
    │                                                     │
    ├── "stale"       → _check_stale_knowledge()          │
    │   查询: 30天以上未更新的文档                           │
    │   SQL: WHERE updated_at < DATE_SUB(NOW(), 30 DAY)   │
    │                                                     │
    ├── "unpopular"   → _check_unpopular_docs()           │
    │   查询: 7天内无访问记录的文档                          │
    │   SQL: HAVING view_count = 0                        │
    │                                                     │
    └── "full"        → _run_full_inspection()            │
        依次执行以上四项，汇总报告                            │
    │                                                     │
    └─────────────────────────────────────────────────────┘
         │
         ↓
    返回: { answer: "巡检报告...", data: { ... }, task_type: "knowledge_inspection" }
```

---

### 推理 Agent 流程 (ReasoningAgent)

**文件**: [workflows/reasoning_agent.py](workflows/reasoning_agent.py)

```
ReasoningAgent.reason(question, context, conversation_id)
         │
         ↓
    [1] _decompose_question() → 问题分解
        │
        │  "对比 MySQL 和 PostgreSQL 的索引机制"
        │         ↓
        │  LLM 分解为:
        │  ["MySQL 的索引机制是什么？",
        │   "PostgreSQL 的索引机制是什么？",
        │   "两者的区别和优缺点？"]
        │
         ↓
    [2] 逐个子问题: 检索 + 推理
        for sub_question in sub_questions:
            │
            ├── vector_store.search(sub_question) → 检索相关文档
            │
            └── _reason_sub_question() → LLM 对每个子问题给出回答
                输入: 子问题 + 检索到的文档 + 上下文
                输出: 子问题的回答
         │
         ↓
    [3] _synthesize_answer() → 汇总生成最终答案
        │
        │  输入: 原始问题 + 所有子问题的推理结果
        │  LLM 综合分析 → 输出完整答案
        │
         ↓
    [4] 保存到会话记忆
         │
         ↓
    返回: {
        answer: "最终答案...",
        reasoning_steps: [{ sub_question, sources, reasoning }, ...],
        sources: [...],
        task_type: "reasoning"
    }
```

---

### 运营分析 Agent 流程 (OpsAgent)

**文件**: [workflows/ops_agent.py](workflows/ops_agent.py)

```
OpsAgent.analyze(analysis_type, **kwargs)
         │
    ┌────┴──────────────────────────────────────┐
    │                                             │
    ├── knowledge_gap                             │
    │   查 qa_unanswered 表 → 分析未命中问题       │
    │   按次数分级: 高(>5) / 中(2-5) / 低(1)       │
    │   生成补充建议                               │
    │                                             │
    ├── qa_trend                                  │
    │   查 qa_log 表 → 近7天问答数量趋势            │
    │                                             │
    ├── user_activity                             │
    │   查 qa_log 表 → 近7天活跃用户排行            │
    │                                             │
    ├── full_report                               │
    │   执行以上三项 → 整合运营建议                  │
    │                                             │
    ├── hot_questions (period: day/week)          │
    │   查 qa_log 表 → 热门问题排行                 │
    │                                             │
    ├── knowledge_growth (period: week/month)     │
    │   查 knowledge_doc 表 → 文档增长趋势          │
    │                                             │
    ├── agent_success_rate (period: week/month)   │
    │   查 agent_run 表 → 成功率分析                │
    │                                             │
    └── tool_call_failures                        │
        查 tool_call 表 → 工具失败排行              │
    │                                             │
    └─────────────────────────────────────────────┘
         │
         ↓
    返回: { success: true, answer: "分析报告...", data: { ... } }
```

---

## 工具系统流程

### 工具注册

**文件**: [tools/__init__.py](tools/__init__.py)

```
应用启动时:
         │
         ↓
    import tools → 触发 register_all_tools()
         │
         ↓
    创建工具实例并注册到 ToolRegistry:
    ├── QuestionRewriteTool()    → "question_rewrite"
    ├── KnowledgeSearchTool()    → "knowledge_search"
    ├── RerankTool()             → "rerank"
    ├── ConversationMemoryReadTool()  → "conversation_memory_read"
    ├── ConversationMemoryWriteTool() → "conversation_memory_write"
    ├── DocSummaryTool()         → "doc_summary"
    └── OCRExtractTool()         → "ocr_extract"
```

### 工具调用流程

**文件**: [tools/registry.py](tools/registry.py)

```
tool_registry.invoke_tool("knowledge_search", {"query": "...", "top_k": 5})
         │
         ↓
    [1] 获取工具实例 → tool = self._tools["knowledge_search"]
         │
         ↓
    [2] 验证输入参数 → tool.validate_input(parameters)
         │
         ↓
    [3] 开始工具调用跟踪 → tool_execution_tracker.start_tool_call()
         │
         ↓
    [4] 执行工具（带超时和重试）
        │
        │  with ThreadPoolExecutor(max_workers=1) as executor:
        │      future = executor.submit(tool.execute, parameters)
        │      result = future.result(timeout=timeout_sec)
        │
        │  超时 → 抛出 TimeoutError
        │  异常 → 重试 (最多 max_retries 次)
         │
         ↓
    [5] 完成工具调用跟踪 → tool_execution_tracker.complete_tool_call()
         │
         ↓
    返回: { documents: [...], scores: [...], count: 5 }
```

**Java 类比**:
- `ToolRegistry` ≈ 单例的 `Map<String, Tool>` + `@Service` 注册
- `tool.execute()` ≈ 策略模式中具体策略的执行方法
- `ThreadPoolExecutor` ≈ Java 的 `ExecutorService`

---

## 数据流向图

### 问答主流程数据流

```
用户提问
    │
    ↓
┌─────────┐    ┌──────────────┐    ┌──────────────┐
│ FastAPI  │───→│ RouterAgent  │───→│ IntentClass- │
│ routes   │    │ (路由分发)    │    │ ifier (意图)  │
└─────────┘    └──────┬───────┘    └──────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────┐
        │             │             │              │
        ↓             ↓             ↓              ↓
  ┌───────────┐ ┌──────────┐ ┌──────────┐  ┌──────────┐
  │ ChitChat  │ │Knowledge │ │ Admin    │  │Inspection│
  │ Agent     │ │QA Agent  │ │ Copilot  │  │ Agent    │
  └─────┬─────┘ └────┬─────┘ └────┬─────┘  └────┬─────┘
        │            │            │              │
        │     ┌──────┴──────┐     │              │
        │     │             │     │              │
        │     ↓             ↓     │              │
        │  ┌───────┐  ┌────────┐  │              │
        │  │Vector │  │Retriev-│  │              │
        │  │Store  │  │alAgent │  │              │
        │  │(检索) │  │(检索)  │  │              │
        │  └───┬───┘  └───┬────┘  │              │
        │      │          │       │              │
        │      ↓          ↓       ↓              ↓
        │  ┌──────────────────────────────────────────┐
        │  │              LLM Service                  │
        │  │         (通义千问 API 调用)                │
        │  └───────────────────┬──────────────────────┘
        │                      │
        ↓                      ↓
  ┌─────────────────────────────────────┐
  │            生成回答                    │
  └─────────────────┬───────────────────┘
                    │
                    ↓
              ┌───────────┐
              │  返回响应   │
              └───────────┘
```

### 存储层

```
                    ┌─────────────────┐
                    │   Redis         │
                    │ (会话记忆存储)   │
                    │                 │
                    │ Key 格式:       │
                    │ conversation:   │
                    │ {id}:messages   │
                    │                 │
                    │ 过期时间: 24h   │
                    └─────────────────┘

                    ┌─────────────────┐
                    │   Milvus/FAISS  │
                    │ (向量数据库)     │
                    │                 │
                    │ 存储文档向量化   │
                    │ 后的 embedding  │
                    │                 │
                    │ 支持相似度搜索   │
                    └─────────────────┘

                    ┌─────────────────┐
                    │   MySQL         │
                    │ (关系数据库)     │
                    │                 │
                    │ knowledge_doc   │ ← 文档信息
                    │ knowledge_chunk │ ← 文档片段
                    │ qa_log          │ ← 问答日志
                    │ qa_unanswered   │ ← 未命中问题
                    │ user_memory     │ ← 用户记忆/画像
                    │ user            │ ← 用户表
                    └─────────────────┘
```

---

## Java 开发者 Python 速查

| Java 概念 | Python 对应 | 说明 |
|-----------|-------------|------|
| `class` | `class` | Python 也用 class，但支持多继承 |
| `interface` | `ABC` + `@abstractmethod` | 抽象基类，用 `abc` 模块实现 |
| `this` | `self` | Python 显式写出 self 作为第一个参数 |
| `null` | `None` | Python 的空值 |
| `@Autowired` | 构造函数直接创建实例 | Python 没有 IoC 容器，直接 `XXService()` |
| `@RestController` | `@router.post("/path")` | FastAPI 用装饰器定义路由 |
| `@PathVariable` | 函数参数直接写 | FastAPI 自动解析路径参数 |
| `@RequestBody` | 函数参数声明类型 | FastAPI 用 Pydantic BaseModel |
| `Optional<T>` | `Optional[T]` | Python 也有 Optional，来自 typing 模块 |
| `Map<K,V>` | `Dict[K, V]` | Python 的字典类型 |
| `List<T>` | `List[T]` | Python 的列表类型 |
| `extends` | `class Child(Parent)` | Python 用括号表示继承 |
| `implements` | `class Child(Interface)` | 同上，写在括号里 |
| `@Override` | 直接重写方法 | Python 不需要注解 |
| `synchronized` | `threading.Lock()` | Python 用锁对象 |
| `Singleton` | `__new__` 或模块级变量 | Python 有多种单例实现方式 |
| `new Object()` | `Object()` | Python 不用 new 关键字 |
| `String.format()` | `f"{variable}"` | Python 的 f-string 格式化 |
| `instanceof` | `isinstance(obj, Class)` | Python 类型检查 |
| `getter/setter` | `@property` | Python 用属性装饰器 |
| `enum` | `class Xxx(Enum)` | Python 用 Enum 类 |
| `try-catch-finally` | `try-except-finally` | 异常处理语法不同 |
| `throw` | `raise` | Python 抛异常用 raise |
| `Stream.collect()` | 列表推导式 `[x for x in list if ...]` | Python 的函数式操作 |
| `Thread` / `ExecutorService` | `threading` / `concurrent.futures` | Python 多线程 |

---

*文档生成时间: 2026-05-27*
