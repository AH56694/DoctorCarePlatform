# DoctorCarePlatform 医护陪伴平台

DoctorCarePlatform 是一个面向患者、家属、护理人员和平台管理员的智能医疗陪护与护理匹配平台。项目采用单仓库组织方式，包含 React 前端、FastAPI 业务后端、独立的 Python 智能问诊与知识检索服务，以及由 Docker Compose 管理的 MySQL、Redis、MinIO、Nginx 等基础设施。

## 上线准备与迭代规范

当前已实现业务接口鉴权、前端页面拆分、招聘推荐、受限问诊 Agent Loop，以及生产配置和 CI 检查定义。真实业务上线前仍需完成敏感数据保护、真实短信和身份接入、附件链路、医学评审及部署验收；仓库包含部署配置不代表已经完成生产上线。

流程总览中的统计、招聘动态和提醒使用明确标注的示例数据；Neo4j / GraphRAG 仍为设计方案。已有历史数据库风险及清理状态见下方检查报告。

- [企业级审计与整改报告](docs/企业级审计与整改报告.md)：已修复问题、验证结果、上线阻断项与后续迭代顺序。
- [生产部署与运维手册](docs/生产部署与运维手册.md)：生产配置、MySQL 迁移、管理员初始化、健康检查及恢复流程。
- [开发与贡献规范](CONTRIBUTING.md)：测试、依赖锁定、接口边界和数据库变更约定。
- [AI 问诊决策闭环](python-service/docs/agent-loop.md)：已实现的 Agent Loop、追问恢复、证据校验与调用预算。
- [医疗知识图谱设计方案](AI问诊医疗知识图谱详细设计方案.md)：GraphRAG 的设计评审稿，尚未接入运行链路。
- [远程仓库推送检查](docs/远程仓库推送检查.md)：历史数据库风险、当前文件清理及仍待处理的历史记录。

## 服务组成

| 目录 | 作用 | 主要技术 |
| --- | --- | --- |
| `frontend` | 前端控制台，覆盖登录注册、身份资料、招聘匹配、护理沟通、智能问诊、审核与知识库管理 | React 19, TypeScript, Vite, lucide-react |
| `backend` | 主业务接口服务，负责账号身份、资料认证、招聘/应聘/邀请、聊天、评价、短信、管理后台和智能问诊网关 | FastAPI, SQLAlchemy, PyMySQL, Redis, httpx |
| `python-service` | 智能问诊与知识检索服务，负责知识入库、向量检索、智能体编排、流式问答、工具调用与运行轨迹 | FastAPI, LangChain, FAISS/Milvus, Redis, MySQL |
| `infra` | Nginx 反向代理和 MySQL 初始化脚本 | Nginx, MySQL 8.4 |
| `scripts` | 本地混合启动、安装和停止脚本 | PowerShell |
| `tests` / `python-service/tests` | 认证与权限边界、网关、推荐、问诊循环和 MySQL 集成测试 | pytest |

前端入口为 `frontend/src/main.tsx`；账号、招聘、问诊、总览和共享外壳位于 `frontend/src/features`，请求、会话和流式消息处理位于 `frontend/src/lib`。前端回归测试位于 `frontend/tests`。

## 总体架构

```mermaid
flowchart LR
    User["用户 / 管理员"] --> Browser["浏览器"]
    Browser --> Frontend["frontend\nReact + Vite"]
    Browser --> Nginx["Nginx\n统一入口 :8080"]
    Nginx --> Frontend
    Nginx --> Backend["backend\nFastAPI 业务服务 :8000"]

    Frontend -->|/api/v1/*| Backend
    Backend -->|RAG_SERVICE_URL| PythonService["python-service\nAI/RAG 服务 :8300"]
    Backend -->|SQLAlchemy| MySQL[("MySQL\n doctor_care_platform")]
    Backend --> Redis[("Redis\n消息缓存与登录限流")]
    Backend -.-> MinIO[("MinIO\n附件链路待完善")]
    Backend -.-> SMS["SMS 适配器\n真实发送待接入"]

    PythonService -->|知识数据/会话记忆恢复| MySQL
    PythonService -->|会话记忆| Redis
    PythonService --> VectorStore[("FAISS 本地索引\n或 Milvus")]
    PythonService --> LLM["Ollama / OpenAI-compatible / DashScope\n按环境变量降级"]
```

更完整的业务流、智能问诊调用链和数据模型图见 [项目流程与架构图.md](项目流程与架构图.md)，可编辑架构图见 [系统架构.drawio](系统架构.drawio)。

## 快速启动

以下命令从仓库根目录执行，适用于开发环境。Windows 安装脚本使用 Python **3.12**，前端开发与 CI 使用 Node.js **22**；生产镜像和 Python CI 使用 Python **3.11**。Python 3.10 不属于当前运行基线，代码使用了 `asyncio.timeout` 等 Python 3.11 能力。

需要先安装并启动 Docker Desktop / Docker Compose。模型权重、向量索引和真实配置不随 Git 分发。

### Windows 本地混合运行

应用运行在本机，MySQL、Redis 和 MinIO 运行在 Docker 中：

```powershell
.\scripts\install-local.ps1
# 首次使用本地 Embedding 时下载；脚本会询问是否额外下载重排模型，可跳过。
.\.venv\Scripts\python.exe .\python-service\download_model.py
.\scripts\start-local.ps1
```

启动脚本使用 `python-service/models/bge-small-zh-v1.5`、本地 FAISS 和 `127.0.0.1` 上的数据库/缓存。未准备权重时，首次向量操作可能尝试联网下载，`/health` 成功并不代表模型可用。

`start-local.ps1` 默认会启动基础设施并调用开发建表脚本。已有独立数据库和缓存时，先完成对应初始化，再使用 `-SkipInfra`；该启动脚本不能用来迁移生产数据。默认 MySQL 端口为 **3306**，自定义连接使用启动前设置的 `MYSQL_*` 进程环境变量。

若使用兼容模型服务，在启动前设置 `OPENAI_COMPATIBLE_BASE_URL`、`OPENAI_COMPATIBLE_API_KEY`、`OPENAI_COMPATIBLE_MODEL` 和 `LLM_FALLBACK_PROVIDERS`；启动脚本会把这些进程变量传给 AI 服务。Ollama 必须另行启动并准备对应模型。仅准备 Embedding 权重还不能生成问诊答案。

停止服务：

```powershell
.\scripts\stop-local.ps1
```

启动脚本遇到端口占用会停止并提示处理；停止脚本只结束它记录的本项目进程，使用 `-WhatIf` 可预览，使用 `-KeepInfra` 可保留基础设施。默认后台运行，日志位于 `.local-logs/`；需要可见终端时使用启动参数 `-Visible`。

### Docker 开发环境

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose config --quiet
docker compose up --build -d
```

开发 Compose 默认使用本地 Embedding，但没有挂载宿主机模型目录；容器第一次初始化向量库时可能需要联网下载权重。离线使用时必须额外配置模型目录的只读挂载。开发 Compose 已透传 `DASHSCOPE_API_KEY`，需要使用 DashScope 时可将真实配置写入被忽略的根目录 `.env`。

当前开发 Compose **没有透传** `OPENAI_COMPATIBLE_*`、`OLLAMA_*` 和 `LLM_FALLBACK_PROVIDERS`，单独在根目录 `.env` 添加它们不会注入容器；使用这些提供方需要扩展 Compose 的 `environment`。容器内的 `127.0.0.1` 指容器自身，不是宿主机 Ollama 服务。

新建的开发 MySQL 数据卷会加载 `infra/mysql/doctor_care_platform_schema.sql`。`scripts/init-mysql.ps1` 也是开发建表工具，不能用于升级已有真实业务数据库。

### 开发访问地址

| 服务 | 地址 |
| --- | --- |
| Nginx 统一入口 | `http://127.0.0.1:8080` |
| Docker 前端 | `http://127.0.0.1:3000` |
| 本地开发前端 | `http://127.0.0.1:5173` |
| 后端接口文档 | `http://127.0.0.1:8000/docs` |
| 智能问诊服务存活检查 | `http://127.0.0.1:8300/health` |
| AI 接口文档（需服务令牌） | `http://127.0.0.1:8300/docs` |
| MinIO 管理控制台 | `http://127.0.0.1:9001` |

这些地址对应开发配置，宿主端口绑定 `127.0.0.1`。AI 的 `/docs`、`/openapi.json` 和 `/ready` 都需要 `X-Service-Token`，直接从浏览器地址栏访问会返回 401；调试方式见 [AI 服务 README](python-service/README.md)。生产环境关闭两个服务的接口文档。

### 配置从哪里读取

| 场景 | 配置来源 |
| --- | --- |
| 开发 Compose | 根目录 `.env` / 进程变量参与 Compose 插值，只有 `environment` 中声明的变量会传入容器 |
| 手动运行后端 | 进程变量及工作目录下的 `.env`；根目录模板中的 `mysql`、`redis`、`python-service` 是容器 DNS 名，本机运行需改为实际主机地址 |
| 手动运行 AI 服务 | 进程变量及 `python-service/.env`，模板为 `python-service/.env.example` |
| 本地启动脚本 | 给两个子进程注入数据库、缓存、模型路径和服务令牌等配置；脚本注入的值优先于 `.env` |
| 生产 Compose | 显式使用 `--env-file .env.production -f docker-compose.production.yml`，连接预先准备的私有 MySQL / Redis，并挂载 Embedding 权重 |

`RAG_SERVICE_TOKEN` 在两个服务中必须一致。根目录模板中保留的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 当前不用于配置问诊 `LLMService`；实际使用 `DASHSCOPE_*` 或 `OPENAI_COMPATIBLE_*` 等上述变量。管理端模型配置记录也不等同于运行进程已经切换模型。

## 手动开发命令

在独立终端中分别启动。后端以下连接为开发默认示例，按实际数据库配置替换：

```powershell
$env:DATABASE_URL = "mysql+pymysql://root:change-me@127.0.0.1:3306/doctor_care_platform?charset=utf8mb4"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:RAG_SERVICE_URL = "http://127.0.0.1:8300"
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

AI/RAG 服务：

```powershell
Push-Location python-service
$env:EMBEDDING_MODEL = "local"
$env:LOCAL_EMBEDDING_MODEL_PATH = "./models/bge-small-zh-v1.5"
$env:USE_MILVUS = "false"
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8300
Pop-Location
```

前端：

```powershell
npm --prefix frontend ci --cache .\.npm-cache
npm --prefix frontend run dev
```

提交前验证（均从根目录执行，不依赖上一个代码块的目录切换）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest python-service/tests -q
.\.venv\Scripts\python.exe -m ruff check backend python-service tests --select E9,F63,F7,F82
npm --prefix frontend test
npm --prefix frontend run build
.\scripts\tests\test-local-processes.ps1
```

本地安装脚本包含 `requirements-dev.txt` 中的测试工具。生产镜像使用 Linux/Python 3.11 的带哈希锁文件，更新方式见贡献规范。

未设置隔离的 `TEST_MYSQL_URL` 时，MySQL 集成测试会跳过；单元测试通过不代表数据库迁移、真实模型效果或生产环境已经验收。[CI 配置](.github/workflows/ci.yml) 包含后端、AI、前端、MySQL 和 Windows 启停脚本检查，实际运行结果以仓库 Actions 为准。

前端 `build` 会执行 TypeScript 检查、导出离线 `overview.html` 和 Vite 构建。导出页使用示例数据，可通过 `npm --prefix frontend run export:overview` 单独生成，生成文件已被 Git 忽略。

## 核心能力

- 账号与身份：手机号注册/登录，多角色切换，患者/护理人员资料维护，护理资质提交与审核。
- 护理匹配：患者发布护理招聘，护理人员应聘，患者定向邀请，匹配后自动建立沟通会话。
- 个性化招聘推荐：原护理人员列表接口内置 PyTorch 隐式反馈推荐，首次使用在合格候选池内随机探索，后续依据筛选、查看、沟通、邀请和审核行为调整顺序。
- 沟通与评价：护理会话、消息发送、服务评价、护理人员评分刷新。
- 智能问诊：普通用户进入受限 Agent Loop，后端保存 AI 会话与消息，Python 服务返回经校验的答案、引用来源、步骤和工具调用轨迹。
- 管理后台：用户状态、证书审核、AI 模型配置、内容巡检、知识库入库/删除和管理日志。
- 知识库：后台保存 `ai_knowledge_chunks` 业务记录，并同步调用 Python 服务写入 FAISS/Milvus 与兼容知识表。
- 短信通知：记录通知及重试状态；真实供应商适配器尚未完成，配置密钥不会产生实际发送，接口明确返回失败或演练状态。

## AI 问诊 Agent Loop

普通用户请求经后端 `/api/v1/ai/chat` 或 `/api/v1/ai/chat/stream` 转到 AI 服务 `/api/agent/run` 或 `/api/agent/run/stream`，同步与 SSE 接口共用同一执行循环：

1. 检查紧急风险信号，读取会话历史，提取能回溯到用户原文的患者信息。
2. 模型根据缺失信息和最新证据选择 `search`、`ask_user`、`answer` 或 `escalate`。
3. 对检索结果做相关性、覆盖和冲突评估，必要时修改查询继续检索；分数高不等于证据充分。
4. 回答按结论关联来源，再独立核验；通过后才分块输出正文，未通过的草稿不会提前展示。
5. 追问返回 `waiting`；用户沿用同一会话回复后开启新一轮运行。无可用模型或证据不足时返回追问或保守说明。

默认每轮最多 **3 次检索、6 次决策、24 个步骤**，整轮等待预算 **80 秒**，单步 **20 秒**。超时后丢弃迟到结果，但不能强行终止已经发出的远程模型请求。SSE 展示步骤事件和验证后的正文分块，不是直接透传模型的生成 token。

管理员工作流和旧 `/api/ask` 接口仍走原有路由。运行状态和工具轨迹保存在进程内，不提供跨进程的步骤恢复；部署暂按单个 AI 实例。当前未更换模型权重或进行微调，医学效果仍需独立评测。完整配置及边界见 [Agent Loop 说明](python-service/docs/agent-loop.md)。

## 关键接口

后端业务接口（受保护接口需要登录 Bearer Token，并校验角色及对象归属）：

- `GET /health`
- `GET /ready`
- `GET /api/v1/dashboard/summary`
- `POST /api/v1/accounts/register`
- `POST /api/v1/accounts/login`
- `PUT /api/v1/accounts/{user_id}/profiles/patient`
- `PUT /api/v1/accounts/{user_id}/profiles/caregiver`
- `POST /api/v1/accounts/{user_id}/profiles/{profile_role}/identity-review`
- `POST /api/v1/jobs`
- `POST /api/v1/jobs/{job_id}/applications`
- `POST /api/v1/jobs/applications/{application_id}/review`
- `POST /api/v1/jobs/invitations`
- `POST /api/v1/jobs/invitations/{invitation_id}/respond`
- `POST /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/reviews`
- `POST /api/v1/ai/chat`
- `POST /api/v1/ai/chat/stream`
- `POST /api/v1/admin/knowledge-items`
- `DELETE /api/v1/admin/knowledge-items/{item_id}`

Python 智能问诊与知识检索接口：

除 `/` 和 `/health` 外均为内部接口，需要 `X-Service-Token`。生产环境禁用 `/api/parse` 和接口文档，不直接面向浏览器开放。

- `GET /health`
- `GET /ready`
- `POST /api/ask`
- `POST /api/ask/stream`
- `POST /api/parse`
- `POST /api/summary`
- `POST /api/agent/run`
- `POST /api/agent/run/stream`
- `GET /api/agent/run/{run_id}`
- `GET /api/agent/run/{run_id}/steps`
- `GET /api/agent/run/{run_id}/tool-calls`
- `GET /api/agent/tools`
- `POST /api/v1/knowledge/ingest`
- `DELETE /api/v1/knowledge/{doc_id}`

## 数据库

主库为 MySQL 数据库 `doctor_care_platform`。后端业务表和 Python AI 服务兼容表共用同一个数据库。

后端业务表包括：

- `users`, `user_roles`
- `patient_profiles`, `caregiver_profiles`, `certifications`
- `job_postings`, `applications`, `invitations`, `recruitment_interactions`
- `conversations`, `messages`
- `ai_sessions`, `ai_messages`, `medical_cases`
- `ai_model_configs`, `ai_knowledge_chunks`, `ai_semantic_cache`
- `reviews`, `sms_notifications`, `admin_logs`

Python AI 服务兼容表包括：

- `knowledge_doc`, `knowledge_chunk`
- `qa_log`, `qa_unanswered`
- `user_memory`
- `agent_run`, `tool_call`
- `doc_view_logs`

上述为已有表结构，不代表所有工作流都完整写入这些表。尤其普通问诊的运行状态和工具轨迹当前在内存中维护，不能依赖 `agent_run` / `tool_call` 实现运行恢复。

## PyTorch 招聘推荐

招聘推荐不增加新的前端业务接口，继续使用：

```text
GET /api/v1/jobs/caregivers/available
```

列表接口要求患者身份登录，支持可选的 `patient_id`、`job_id`、`city`、`keyword` 和
`min_experience` 参数。`patient_id` 如有传入必须等于当前用户，`job_id` 必须属于本人。护理详情、沟通、邀请和应聘审核等原有接口会记录推荐反馈。
模型缺失或用户尚无训练向量时，系统自动使用实时行为相似度和随机探索排序。

仅对已初始化的开发数据库生成演示数据并训练模型。当前 Compose 默认端口为 `3306`；下面显式传入连接，避免使用脚本保留的 `3307` 默认值：

```powershell
.\scripts\bootstrap-recommendation.ps1 `
  -DatabaseUrl "mysql+pymysql://root:change-me@127.0.0.1:3306/doctor_care_platform?charset=utf8mb4"
```

默认生成 12 名演示患者、60 名演示护理人员、招聘岗位、应聘记录和推荐行为，
模型输出到忽略版本控制的 `.local-models/recruitment_recommender.pt`。

演示账号：

```text
患者手机号：13990000000 ～ 13990000011
护理手机号：13880000000 ～ 13880000059
统一密码：demo123456
```

需要单独重新训练时：

```powershell
.\.venv\Scripts\python.exe .\scripts\train-recruitment-recommender.py `
  --database-url "mysql+pymysql://root:change-me@127.0.0.1:3306/doctor_care_platform?charset=utf8mb4"
```

## 重要配置

| 变量 | 说明 |
| --- | --- |
| `APP_ENV` | 运行环境；设为 `production`/`prod` 时启用生产密钥与示例密码阻断检查 |
| `DATABASE_URL` | 后端 SQLAlchemy 数据库连接 |
| `AUTH_SECRET_KEY` | JWT 签名密钥；生产环境至少 32 个字符，禁止使用开发默认值 |
| `AUTH_TOKEN_EXPIRE_MINUTES` | 登录访问令牌有效期，默认 120 分钟 |
| `AUTH_ISSUER` | JWT 签发方，默认 `doctor-care-platform` |
| `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USERNAME`, `MYSQL_PASSWORD` | Python 服务访问 MySQL |
| `REDIS_URL` | 后端和 Python 服务 Redis 连接 |
| `RAG_SERVICE_URL` | 后端调用 Python 服务的基础地址 |
| `RAG_SERVICE_TOKEN` | 两服务共享的内部调用秘密；生产至少 32 字符且须与 JWT 密钥不同 |
| `USE_MILVUS` | `false` 时使用 FAISS 持久化目录，`true` 时使用 Milvus |
| `VECTOR_STORE_PERSIST_DIR` | FAISS 索引持久化目录 |
| `VECTOR_STORE_COLLECTION_NAME` | 向量集合名称 |
| `VECTOR_STORE_METRIC_TYPE` | 向量分数度量，默认 `COSINE`；`L2` 会转换为统一相似度 |
| `EMBEDDING_MODEL`, `LOCAL_EMBEDDING_MODEL_PATH` | AI 进程的 Embedding 模型选择与本地路径；开发 Compose 通过 `PYTHON_SERVICE_EMBEDDING_MODEL` 映射模型选择 |
| `LLM_FALLBACK_PROVIDERS` | DashScope 不可用后的提供方顺序，默认 `ollama,openai_compatible,retrieval`；须按上述部署方式实际注入进程 |
| `AGENT_MAX_SEARCHES`, `AGENT_MAX_DECISIONS`, `AGENT_MAX_STEPS` | 问诊循环次数上限，默认分别为 `3`、`6`、`24` |
| `AGENT_TIMEOUT_SECONDS`, `AGENT_STEP_TIMEOUT_SECONDS` | 整轮与单步等待预算，默认 `80`、`20` 秒 |
| `MEMORY_*`, `LLM_*_MAX_CHARS` | 会话压缩、持久化恢复和提示词各层上下文预算 |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | 本地 Ollama 模型配置 |
| `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL` | OpenAI-compatible 模型配置 |
| `DASHSCOPE_API_KEY`, `DASHSCOPE_MODEL` | DashScope/Qwen 配置 |
| `ALIYUN_SMS_*` | 阿里云短信配置 |

## 生产注意事项

- 使用独立的 `docker-compose.production.yml` 和 `.env.production`，并准备外部私有 MySQL / Redis、Embedding 模型目录与 HTTPS 入口；它不包含开发 Compose 中的数据库和缓存容器。完整迁移、启动及管理员初始化步骤见 [生产部署与运维手册](docs/生产部署与运维手册.md)。
- `/health` 只表示存活；后端 `/ready` 检查数据库、生产 Redis 和迁移版本，AI `/ready` 检查模型初始化且需要服务令牌，均不代表医学效果验收。
- 新 MySQL 数据库使用 `.\.venv\Scripts\python.exe -m alembic -c alembic.mysql.ini upgrade head`。已有数据库必须先比对结构、备份并验收专项迁移；不能使用历史 PostgreSQL 迁移链，也不能直接盖章跳过检查。详见生产运维手册。
- 前端所有受保护请求必须携带登录返回的 Bearer Token；失效令牌需要重新登录。
- 为 MySQL 配置独立账号、最小权限、备份与恢复策略。
- 为模型 API key、短信密钥、数据库密码启用生产级密钥管理。
- 为医疗知识来源建立授权、版本、审计和更新流程。
- 对 AI 问答增加医学安全评测、风险提示和人工介入策略。
- 为 Nginx、后端、AI 服务、数据库和对象存储接入日志、监控和告警。
- MinIO 当前主要作为文件对象能力预留；真实附件上传链路上线前需要补齐鉴权、生命周期和病毒/内容安全扫描。
