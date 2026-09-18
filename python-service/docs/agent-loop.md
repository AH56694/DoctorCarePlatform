# AI 问诊决策闭环

普通用户的 `/api/agent/run` 与 `/api/agent/run/stream` 现在共用同一个受限循环。
前端和业务网关的接口地址不变。管理员工作流和旧 `/api/ask` 兼容接口仍使用原有路由，
不应通过它们验收新的问诊闭环。

## 执行过程

1. 检查当前输入中的紧急风险提示；命中保守规则时直接给出就医提示，不等待模型或检索。
2. 读取会话历史，提取用户明确陈述的事实。事实保留 `field/value/quote/turn`；
   AI 回复及历史摘要不直接充当患者事实。未知信息保持缺失，模型补充的事实必须能回溯到用户原文。
3. 对个人问诊优先补充年龄、症状持续时间及模型识别的关键缺失项。一般医学科普无需强制收集患者资料。
4. 模型读取患者信息、最新证据、缺失问题和已执行查询，选择 `search`、`ask_user`、`answer` 或 `escalate`。
5. `search` 只执行已有 `knowledge_search` 工具。每轮新结果重新做语义评估，包含来源、相关性、
   问题覆盖、适用条件和冲突。检索分数与片段数量不再单独证明证据充分。
6. 模型可以根据评估反馈选择新的查询。初次检索之外默认最多补充两次，规范化后重复的查询直接停止。
7. 回答使用带来源 ID 的结论列表生成，再独立核对引用和安全性。全部结论通过后才返回正文和最终引用。
   未通过验证的草稿不会进入 SSE、步骤输出或状态查询的响应。
8. 将最终答复或追问写入会话记忆。追问保留 `waiting` 状态并结束当前 HTTP 请求。

这里没有执行模型提供的 Python、SQL 或任意工具名。模型决策经过 Pydantic 严格校验，
未知动作、额外字段、错误类型或非 JSON 输出都不会被执行。追问从允许的患者信息字段生成，
不会直接展示模型未验证的自由文本建议。

## 追问和恢复

继续使用相同 `conversation_id` 提交用户回复，服务读取会话记录后重新整理事实并开启下一轮运行。
每次请求使用新的 `run_id`；不是重新执行旧的暂停线程。业务后端仍负责持久保存消息，
Redis 过期时沿用现有的 MySQL 会话恢复机制。

独立调用 AI 服务时必须提供稳定的会话 ID，或通过 `context` 传递 `用户: ...` 标记的历史。
没有历史就无法恢复前一轮信息。运行轨迹仍是进程内数据，不提供跨进程的步骤检查点恢复。

## 模型与检索

患者信息提取、决策、证据评估、回答生成和回答校验统一调用 `LLMService.generate_structured()`。
沿用 DashScope → 配置的 Ollama / 兼容服务 → 保守降级的提供方顺序。
支持文本模型返回 JSON，再在服务内执行 Schema 校验；不依赖原生工具调用接口。

没有可用模型、模型无法稳定输出符合 Schema 的 JSON 或证据核查失败时，服务会追问或说明资料不足，
不会把通用降级文本解释成工具指令，也不会绕过检查给出诊疗结论。

此次未更换模型权重、未进行微调、未增加模型下载或第三方依赖。原有向量检索和重排继续使用；
可通过现有 `RERANKER_TYPE=bge` 与 `simple` 做对照评估，BGE 所需权重应事先准备。
提高循环次数不能补偿知识库缺失或模型不支持稳定结构化输出。

## 配置

本地服务读取 `python-service/.env` 或进程环境变量；Docker Compose 的两套配置均转发以下变量。
变更配置或代码后重启 AI 服务生效，业务网关的同步超时仍为 90 秒。

| 变量 | 默认值 | 含义 |
| --- | --- | --- |
| `AGENT_MAX_SEARCHES` | 3 | 每轮请求最多检索次数，配置范围 1–5 |
| `AGENT_MAX_DECISIONS` | 6 | 每轮决策次数，配置范围 1–12 |
| `AGENT_MAX_STEPS` | 24 | 包括评估、决策、记忆等在内的步骤上限，配置范围 4–40 |
| `AGENT_TIMEOUT_SECONDS` | 80 | 整轮等待预算，最多 85 秒 |
| `AGENT_STEP_TIMEOUT_SECONDS` | 20 | 单步等待预算，最多 45 秒 |

模型和工具工作由最多 8 个共享后台工作线程执行，不在 FastAPI 事件循环中阻塞其他请求。
超时后丢弃该步骤的私有状态，迟到结果不会覆盖最终结果。Python 无法强制杀死正在运行的线程，
已发出的远程调用可能继续消耗时间或计费，记忆写入也可能迟到；工作槽会一直保留到实际调用退出，
不会无限堆积后台请求。各外部服务仍需配置自身连接及读取超时。

## 响应与可观察性

原有 `answer/sources/steps/tool_calls/intermediate_conclusions` 保留。
AI 服务增加或明确 `status`、`requires_input`、`stop_reason`。常见停止原因：

- `answered`：答案和引用通过校验。
- `needs_user_input`：已返回追问，状态为 `waiting`。
- `urgent_risk`：需要优先就医评估。
- `insufficient_evidence` / `answer_without_evidence`：证据不足。
- `repeated_query` / `repeated_answer`：避免无进展循环。
- `search_limit` / `decision_limit` / `step_limit` / `timeout`：预算耗尽，返回保守说明。

`completed` 表示本轮流程结束，不等同于已经得出医学结论；需要结合 `stop_reason` 判断。
服务异常使用 `failed`，不会再被统一标记为成功。流式接口保留 `step_started`、
`step_completed`、`sources`、`token`、`end` 和 `complete` 事件；正文在校验结束后分块发出，
不是模型生成过程中的实时 token 流，以避免向用户提前展示未验证内容。

## 验证与后续模型评测

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pytest python-service/tests -q
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check backend python-service tests --select E9,F63,F7,F82
```

`test_agent_loop.py` 用受控模型结果检验真实循环和动作边界，`test_agent_api_loop.py` 检验真实路由的同步、
SSE 和等待状态契约。用例覆盖二次检索反馈、短症状输入、追问续接、无模型、无来源、证据冲突、
伪造来源 ID、草稿拦截、次数限制、取消和迟到结果隔离。

这些测试证明程序控制流，不代表临床效果验收。风险规则只是保守分流起点，不能完整识别所有急症。
下一阶段应使用医学审核的脱敏问诊集对比模型：记录风险漏判、追问完整性、证据支持率、
工具决策成功率、每轮调用次数、延迟和费用。训练集与验收集分离；只在评测显示明确收益后调整
检索阈值、模型选择或进行 SFT/LoRA。模型自评并不保证事实正确，来源质量和医学审核仍是必要输入。
