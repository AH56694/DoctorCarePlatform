# DoctorCarePlatform 医护陪伴平台

DoctorCarePlatform 是一个面向患者、家属、护理人员和平台管理员的智能医疗陪护与护理匹配平台。项目采用单仓库组织方式，包含 React 前端、FastAPI 业务后端、独立的 Python 智能问诊与知识检索服务，以及由 Docker Compose 管理的 MySQL、Redis、MinIO、Nginx 等基础设施。

## 上线准备与迭代规范

本轮安全与工程整改已落库；真实业务上线前仍需完成敏感数据保护、真实短信和身份接入、附件链路、医学评审及部署验收。

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
| `tests` / `python-service/tests` | 后端网关、认证、知识检索客户端与智能问诊服务单元测试 | pytest |

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
    Backend --> Redis[("Redis\n缓存/会话预留")]
    Backend --> MinIO[("MinIO\n文件对象预留")]
    Backend --> SMS["SMS 适配器\n真实发送待接入"]

    PythonService -->|知识兼容表/运行日志| MySQL
    PythonService -->|会话记忆| Redis
    PythonService --> VectorStore[("FAISS 本地索引\n或 Milvus")]
    PythonService --> LLM["Ollama / OpenAI-compatible / DashScope\n按环境变量降级"]
```

更完整的业务流、智能问诊调用链和数据模型图见 [项目流程与架构图.md](项目流程与架构图.md)，可编辑架构图见 [系统架构.drawio](系统架构.drawio)。

## 快速启动

复制 `.env.example` 为 `.env` 仅在需要覆盖默认演示配置、接入真实模型密钥或短信服务时使用。

使用 Docker Compose 启动完整环境：

```powershell
docker compose up --build
```

默认端口：

| 服务 | 地址 |
| --- | --- |
| Nginx 统一入口 | `http://127.0.0.1:8080` |
| Docker 前端 | `http://127.0.0.1:3000` |
| 本地开发前端 | `http://127.0.0.1:5173` |
| 后端接口文档 | `http://127.0.0.1:8000/docs` |
| 智能问诊服务接口文档 | `http://127.0.0.1:8300/docs` |
| MinIO 管理控制台 | `http://127.0.0.1:9001` |

如果 Docker Hub 拉取 `python:3.11-slim` 或 `node:22-alpine` 不稳定，可以使用本地混合启动方式。该方式使用本机 Python/Node 运行应用，只通过 Docker 启动 Redis、MinIO、MySQL：

```powershell
.\scripts\install-local.ps1
.\scripts\start-local.ps1
```

仅在开发演示环境初始化表结构时使用下列脚本；它不是生产迁移工具，不能用来升级已有真实业务数据：

```powershell
.\scripts\init-mysql.ps1
```

停止本地混合启动的服务：

```powershell
.\scripts\stop-local.ps1
```

启动脚本遇到端口占用会停止并提示处理；停止脚本只结束它记录的本项目进程，使用 `-WhatIf` 可预览，使用 `-KeepInfra` 可保留基础设施。旧版脚本启动的进程需在原终端手动停止。自定义内部服务令牌时，在启动前设置 `RAG_SERVICE_TOKEN` 环境变量，供两个服务共同继承。

## 手动开发命令

后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

AI/RAG 服务：

```powershell
cd python-service
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8300
```

前端：

```powershell
cd frontend
npm ci --cache .\.npm-cache
npm --cache .\.npm-cache run dev
npm --cache .\.npm-cache run build
```

测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
cd python-service
..\.venv\Scripts\python.exe -m pytest tests -q
cd ..\frontend
npm test
npm run build
```

本地安装脚本包含 `requirements-dev.txt` 中的测试工具。生产镜像使用 Linux/Python 3.11 的带哈希锁文件，更新方式见贡献规范。

## 核心能力

- 账号与身份：手机号注册/登录，多角色切换，患者/护理人员资料维护，护理资质提交与审核。
- 护理匹配：患者发布护理招聘，护理人员应聘，患者定向邀请，匹配后自动建立沟通会话。
- 个性化招聘推荐：原护理人员列表接口内置 PyTorch 隐式反馈推荐，首次使用在合格候选池内随机探索，后续依据筛选、查看、沟通、邀请和审核行为调整顺序。
- 沟通与评价：护理会话、消息发送、服务评价、护理人员评分刷新。
- 智能问诊：前端流式问答，后端保存 AI 会话与消息，Python 服务返回答案、引用来源、步骤和工具调用轨迹。
- 管理后台：用户状态、证书审核、AI 模型配置、内容巡检、知识库入库/删除和管理日志。
- 知识库：后台保存 `ai_knowledge_chunks` 业务记录，并同步调用 Python 服务写入 FAISS/Milvus 与兼容知识表。
- 短信通知：记录通知及重试状态；真实供应商适配器尚未完成，配置密钥不会产生实际发送，接口明确返回失败或演练状态。

## 关键接口

后端业务接口：

- `GET /health`
- `GET /api/v1/dashboard/summary`
- `POST /api/v1/accounts/register`
- `POST /api/v1/accounts/login`
- `PUT /api/v1/accounts/{user_id}/profiles/patient`
- `PUT /api/v1/accounts/{user_id}/profiles/caregiver`
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

## PyTorch 招聘推荐

招聘推荐不增加新的前端业务接口，继续使用：

```text
GET /api/v1/jobs/caregivers/available
```

列表接口支持可选的 `patient_id`、`job_id`、`city`、`keyword` 和
`min_experience` 参数。护理详情、沟通、邀请和应聘审核等原有接口会记录推荐反馈。
模型缺失或用户尚无训练向量时，系统自动使用实时行为相似度和随机探索排序。

本地项目 MySQL 映射到 `3307` 时，可以一次性生成演示数据并训练模型：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\bootstrap-recommendation.ps1
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
  --database-url "mysql+pymysql://root:change-me@127.0.0.1:3307/doctor_care_platform?charset=utf8mb4"
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
| `EMBEDDING_MODEL`, `LOCAL_EMBEDDING_MODEL_PATH` | Embedding 模型选择与本地路径 |
| `LLM_FALLBACK_PROVIDERS` | Python 服务 LLM 降级顺序，默认 `ollama,openai_compatible,retrieval` |
| `MEMORY_*`, `LLM_*_MAX_CHARS` | 会话压缩、持久化恢复和提示词各层上下文预算 |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | 本地 Ollama 模型配置 |
| `OPENAI_COMPATIBLE_BASE_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL` | OpenAI-compatible 模型配置 |
| `DASHSCOPE_API_KEY`, `DASHSCOPE_MODEL` | DashScope/Qwen 配置 |
| `ALIYUN_SMS_*` | 阿里云短信配置 |

## 生产注意事项

- 新 MySQL 数据库使用 `.\.venv\Scripts\python.exe -m alembic -c alembic.mysql.ini upgrade head`。已有数据库必须先比对结构、备份并验收专项迁移；不能使用历史 PostgreSQL 迁移链，也不能直接盖章跳过检查。详见生产运维手册。
- 前端所有受保护请求必须携带登录返回的 Bearer Token；失效令牌需要重新登录。
- 为 MySQL 配置独立账号、最小权限、备份与恢复策略。
- 为模型 API key、短信密钥、数据库密码启用生产级密钥管理。
- 为医疗知识来源建立授权、版本、审计和更新流程。
- 对 AI 问答增加医学安全评测、风险提示和人工介入策略。
- 为 Nginx、后端、AI 服务、数据库和对象存储接入日志、监控和告警。
- MinIO 当前主要作为文件对象能力预留；真实附件上传链路上线前需要补齐鉴权、生命周期和病毒/内容安全扫描。
