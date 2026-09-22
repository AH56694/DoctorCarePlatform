# DoctorCarePlatform Python AI 微服务

本服务是 [DoctorCarePlatform](../README.md) 的内部 AI 服务，负责文档解析、知识入库、向量检索、问诊决策与会话记忆。业务后端负责终端用户鉴权、对象归属和问诊消息持久化；浏览器通过业务后端调用本服务。

普通用户的 `/api/agent/run` 和 `/api/agent/run/stream` 已接入受限 **Agent Loop**。管理员请求和旧 `/api/ask` 接口仍使用原有工作流。完整流程、停止条件及模型评测方式见 [问诊决策闭环](docs/agent-loop.md)。

## 目录结构

| 路径 | 作用 |
| --- | --- |
| `main.py` / `service_security.py` | FastAPI 入口、服务令牌校验和存活/就绪检查 |
| `api/` | 普通问答、Agent 运行及知识入库接口 |
| `agent/` | 患者信息整理、模型决策、执行循环、状态与记忆管理 |
| `core/` | 模型适配、结构化输出、文档解析、向量检索和调用预算 |
| `tools/` / `workflows/` | 注册工具及兼容工作流 |
| `tests/` | 问诊循环、接口、引用、记忆与服务权限回归测试 |
| `requirements.txt` / `requirements.lock` | 本地开发依赖输入 / Linux Python 3.11 部署锁文件 |

## 本地开发

以下命令从 **DoctorCarePlatform 仓库根目录** 执行。Windows 安装脚本使用 Python **3.12** 和根目录 `.venv`；生产镜像与 CI 使用 Python **3.11**。不要沿用旧文档中的 Python 3.10 或单独的 `venv/` 安装方式。

```powershell
.\scripts\install-local.ps1 -SkipFrontend
if (-not (Test-Path python-service/.env)) {
  Copy-Item python-service/.env.example python-service/.env
}
.\.venv\Scripts\python.exe .\python-service\download_model.py
```

下载脚本将 Embedding 保存到 `python-service/models/bge-small-zh-v1.5`，并更新已有 AI `.env` 中的模型路径；脚本询问重排模型时可跳过。模型目录被 Git 忽略，首次下载需要网络，已有完整权重可直接复用。

编辑 `python-service/.env`，确认本地向量方案使用以下配置，并把模板中的示例 API Key 清空或替换为真实值：

```dotenv
EMBEDDING_MODEL=local
LOCAL_EMBEDDING_MODEL_PATH=./models/bge-small-zh-v1.5
USE_MILVUS=false
VECTOR_STORE_COLLECTION_NAME=doctorcare_medical_knowledge
RAG_SERVICE_TOKEN=development-service-token
DASHSCOPE_API_KEY=
```

上面的服务令牌仅用于本地开发，必须与业务后端一致。MySQL / Redis 应已准备好，`MYSQL_*`、`REDIS_URL` 使用实际连接地址；开发建表与完整平台启动见 [项目 README](../README.md#快速启动)。Milvus 是可选路径，不随默认开发 Compose 启动。

在独立终端运行 AI 服务：

```powershell
Push-Location python-service
..\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8300
Pop-Location
```

在 PyCharm 中打开整个 `DoctorCarePlatform` 项目，解释器选择根目录 `.venv\Scripts\python.exe`；运行配置选择模块 `uvicorn`，参数为 `main:app --reload --host 127.0.0.1 --port 8300`，工作目录设置为 `python-service`。AI 服务端口为 **8300**，业务后端端口为 **8000**。

## 模型与配置来源

- 服务入口读取 `python-service/.env`，已有进程环境变量优先。仅修改根目录 `.env` 不等于给本服务配置了模型。
- 本地 Embedding 负责向量化，不负责生成答案。生成链路优先尝试可用的 DashScope，然后按 `LLM_FALLBACK_PROVIDERS` 使用 Ollama / 兼容接口；默认顺序为 `ollama,openai_compatible,retrieval`。
- 使用兼容接口时配置 `OPENAI_COMPATIBLE_BASE_URL`、`OPENAI_COMPATIBLE_API_KEY` 和 `OPENAI_COMPATIBLE_MODEL`；使用 Ollama 时，另行启动服务并准备 `OLLAMA_MODEL` 指定的模型。
- 旧的 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 不用于当前 `LLMService` 的运行配置。管理端保存模型配置记录也不会自动替换本进程实例。
- Agent Loop 要求模型返回符合 Schema 的 JSON，并核验答案依据。模型不可用或证据不足时会追问或返回保守说明，不能把检索兜底当作已生成且核验成功的医学答案。
- 本地 `start-local.ps1` 会覆盖部分 AI `.env` 配置，尤其模型目录、向量库、数据库、缓存和模型降级变量；使用该脚本时按项目 README 设置启动前的进程环境变量。

默认开发 Compose 只透传其中部分模型配置，且没有挂载宿主机权重；完整差异见 [项目配置说明](../README.md#配置从哪里读取)。生产 Compose 使用独立配置和权重挂载，不能直接复用开发启动命令。

## 内部接口与鉴权

只有 `/` 和 `/health` 无需令牌。其余接口，包括 `/ready`、开发用 `/docs` 和 `/openapi.json`，都要求 `X-Service-Token`。浏览器地址栏不会自动附加该请求头，直接打开 Swagger 地址会返回 401；使用能够为文档、Schema 和 API 请求附加该头的调试客户端。

| 接口 | 用途 |
| --- | --- |
| `GET /health` | 进程存活，不检查全部外部依赖 |
| `GET /ready` | 初始化向量库/Embedding，失败时返回 503；不证明生成模型可用 |
| `POST /api/agent/run` / `/api/agent/run/stream` | 普通问诊闭环，分别返回 JSON / SSE |
| `GET /api/agent/run/{run_id}` | 当前进程中的运行状态 |
| `GET /api/agent/run/{run_id}/steps` / `/tool-calls` | 当前运行的步骤与工具轨迹 |
| `POST /api/v1/knowledge/ingest` | 知识文本或文件内容入库 |
| `DELETE /api/v1/knowledge/{doc_id}` | 删除知识内容 |
| `POST /api/ask` / `/api/ask/stream` | 旧工作流兼容接口，不用于验收新的问诊闭环 |

本地请求示例（令牌要与实际服务配置一致；“你好”只验证路由连接，不验证检索效果）：

```powershell
$serviceToken = $env:RAG_SERVICE_TOKEN
if (-not $serviceToken) { $serviceToken = "development-service-token" }
$headers = @{ "X-Service-Token" = $serviceToken }
Invoke-RestMethod http://127.0.0.1:8300/health
Invoke-RestMethod http://127.0.0.1:8300/ready -Headers $headers
$body = @{ input = "你好"; conversation_id = "readme-demo" } | ConvertTo-Json -Compress
Invoke-RestMethod http://127.0.0.1:8300/api/agent/run `
  -Method Post -Headers $headers -ContentType "application/json; charset=utf-8" `
  -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

API 返回 `status`、`requires_input`、`stop_reason` 以及原有答案和引用字段。追问为 `waiting`，下一次请求沿用 `conversation_id` 并使用新的运行 ID；`completed` 只表示当前流程结束，不保证已经得出医学结论。SSE 正文在校验完成后分块发送，未验证草稿不会提前输出。

## 循环预算与运行边界

| 变量 | 默认值 |
| --- | ---: |
| `AGENT_MAX_SEARCHES` | 3 |
| `AGENT_MAX_DECISIONS` | 6 |
| `AGENT_MAX_STEPS` | 24 |
| `AGENT_TIMEOUT_SECONDS` | 80 秒 |
| `AGENT_STEP_TIMEOUT_SECONDS` | 20 秒 |

超时会隔离迟到结果，无法强行取消已发出的远程模型请求。运行状态和工具轨迹位于进程内，重启后不能查询旧运行或恢复旧步骤；同一会话下一轮通过历史消息重建上下文。当前 FAISS 和内存状态按单实例部署，不应直接增加 AI worker 数来扩容。

生产设置 `APP_ENV=production`，内部令牌须为至少 32 字符的非示例值；API 文档关闭，基于服务器路径的 `/api/parse` 禁用。生产准备和就绪检查见 [部署运维手册](../docs/生产部署与运维手册.md)。

## 验证

从仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest python-service/tests -q
.\.venv\Scripts\python.exe -m ruff check backend python-service tests --select E9,F63,F7,F82
```

测试使用受控模型和工具输出验证流程、接口、引用及预算边界；不等同于真实模型或临床效果验收。本次问诊闭环没有进行模型微调，GraphRAG 也尚未接入。
