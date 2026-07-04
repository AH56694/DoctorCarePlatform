# DoctorCarePlatform 工作流程与功能构图

本文档根据当前项目代码整理，主要覆盖：

- `frontend`: React + TypeScript 控制台
- `backend`: FastAPI 主业务服务
- `python-service`: AI / RAG 智能问诊与知识库服务
- `infra`: Nginx、MySQL、Redis、MinIO 等基础设施

## 1. 系统总体架构

```mermaid
flowchart LR
    User["用户/管理员"] --> Browser["浏览器"]
    Browser --> Frontend["frontend\nReact + Vite"]

    Frontend -->|/api/v1/*| Backend["backend\nFastAPI 业务服务"]
    Frontend -->|生产环境入口| Nginx["nginx\n统一入口 8080"]
    Nginx --> Frontend
    Nginx --> Backend
    Nginx --> PythonService["python-service\nAI/RAG 服务"]

    Backend -->|SQLAlchemy / PyMySQL| MainDB[("MySQL doctor_care_platform\n后端业务表")]
    Backend -->|RAG_SERVICE_URL| PythonService
    Backend -->|短信通知| Aliyun["阿里云短信"]
    Backend -->|缓存/会话预留| Redis[("Redis")]
    Backend -->|文件对象预留| MinIO[("MinIO")]

    PythonService -->|向量检索| VectorStore[("FAISS 本地索引\n或 Milvus")]
    PythonService -->|兼容知识表/日志| MainDB
    PythonService -->|LLM 调用| LLM["DeepSeek/OpenAI 兼容\n或 DashScope/Qwen"]
    PythonService -->|工具调用| Tools["工具注册中心\n知识检索/重排/OCR/记忆/摘要"]
```

## 2. 前端功能构图

```mermaid
flowchart TB
    App["DoctorCarePlatform 前端"] --> Auth["登录/注册\nAuthGate"]
    Auth --> Shell["登录后控制台 Shell"]

    Shell --> Overview["流程总览\nOverview"]
    Shell --> Accounts["我的信息\nAccountsIdentity"]
    Shell --> Jobs["招聘页面\nJobs"]
    Shell --> Profiles["应聘发布\nProfiles"]
    Shell --> CareChat["聊天沟通\nCareChat"]
    Shell --> Consultation["智能问诊\nConsultation"]
    Shell --> Verification["审核管理\nVerification\n管理员可见"]
    Shell --> Knowledge["知识库\nKnowledge\n管理员可见"]

    Accounts --> AccountsAPI["/api/v1/accounts/*"]
    Jobs --> JobsAPI["/api/v1/jobs/*"]
    Profiles --> ProfilesAPI["/api/v1/profiles/*"]
    CareChat --> ChatAPI["/api/v1/conversations/*"]
    Consultation --> AiAPI["/api/v1/ai/chat/stream"]
    Verification --> AdminAPI["/api/v1/admin/*"]
    Knowledge --> KnowledgeAPI["/api/v1/admin/knowledge-items"]

    AccountsAPI --> Backend["FastAPI backend"]
    JobsAPI --> Backend
    ProfilesAPI --> Backend
    ChatAPI --> Backend
    AiAPI --> Backend
    AdminAPI --> Backend
    KnowledgeAPI --> Backend
```

## 3. 用户身份与主业务流程

```mermaid
flowchart TD
    Start["进入平台"] --> HasAccount{"已有账号?"}
    HasAccount -->|否| Register["手机号/密码注册\n选择初始身份"]
    HasAccount -->|是| Login["登录"]
    Register --> Account["账号创建\nusers + user_roles"]
    Login --> Account

    Account --> Role{"当前身份"}
    Role -->|病人/家属| PatientProfile["维护病人实名资料\npatient_profiles"]
    Role -->|护理方| CaregiverProfile["维护护理简历\ncaregiver_profiles"]
    Role -->|管理员| AdminConsole["进入审核与知识库后台"]

    PatientProfile --> PatientActions["病人侧能力"]
    PatientActions --> PublishJob["发布护理招聘\njob_postings"]
    PatientActions --> BrowseCaregivers["浏览可用护理方\ncaregiver_profiles"]
    PatientActions --> InviteCaregiver["邀请护理方\ninvitations"]
    PatientActions --> AiConsult["智能问诊\nai_sessions + ai_messages"]
    PatientActions --> Chat["护理沟通\nconversations + messages"]
    PatientActions --> Review["服务评价\nreviews"]

    CaregiverProfile --> Certification["上传资质证书\ncertifications"]
    Certification --> ReviewQueue["等待管理员审核"]
    ReviewQueue -->|通过| CaregiverActions["护理方能力"]
    ReviewQueue -->|拒绝| FixProfile["修改资料后重新提交"]

    CaregiverActions --> FindJobs["查看招聘"]
    CaregiverActions --> ApplyJob["提交应聘\napplications"]
    CaregiverActions --> RespondInvite["响应邀请\ninvitations"]
    CaregiverActions --> SetAvailable["设置接单状态"]
    CaregiverActions --> Chat

    AdminConsole --> UserManage["用户状态管理"]
    AdminConsole --> CertReview["证书审核"]
    AdminConsole --> ModelConfig["AI 模型配置"]
    AdminConsole --> KnowledgeManage["知识库维护"]
    AdminConsole --> AdminLogs["操作日志"]
```

## 4. 护理招聘与匹配流程

```mermaid
flowchart TD
    Patient["病人/家属"] --> CreateJob["创建招聘岗位\nPOST /api/v1/jobs"]
    CreateJob --> JobList["岗位列表\nGET /api/v1/jobs"]

    Caregiver["护理方"] --> BrowseJobs["浏览岗位"]
    BrowseJobs --> SubmitApplication["投递应聘\nPOST /api/v1/jobs/{job_id}/applications"]
    SubmitApplication --> Application["applications.status = submitted"]

    Patient --> ReviewApplication["审核应聘\nPOST /api/v1/jobs/applications/{id}/review"]
    ReviewApplication --> Decision{"是否接受?"}
    Decision -->|拒绝| Reject["application.status = rejected"]
    Decision -->|接受| MatchByApply["application.status = accepted\njob.status = matched"]

    Patient --> BrowseAvailable["查看可用护理方\nGET /api/v1/jobs/caregivers/available"]
    BrowseAvailable --> SendInvitation["发送邀请\nPOST /api/v1/jobs/invitations"]
    SendInvitation --> Invitation["invitations.status = pending"]
    Invitation --> CaregiverRespond["护理方响应\nPOST /api/v1/jobs/invitations/{id}/respond"]
    CaregiverRespond --> InviteDecision{"是否接受?"}
    InviteDecision -->|拒绝| InviteReject["invitation.status = rejected"]
    InviteDecision -->|接受| MatchByInvite["invitation.status = accepted\njob.status = matched"]

    MatchByApply --> Conversation["自动创建沟通会话\nconversations"]
    MatchByInvite --> Conversation
    Conversation --> Messages["发送消息\nmessages"]
    Conversation --> Review["服务完成后评价\nreviews"]
    Review --> Rating["刷新护理方评分\ncaregiver_profiles.rating_avg"]

    MatchByApply --> Sms["创建短信通知记录\nsms_notifications"]
    MatchByInvite --> Sms
```

## 5. 智能问诊处理流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as 前端 Consultation
    participant B as backend /api/v1/ai/chat/stream
    participant R as RagServiceClient
    participant A as python-service Agent
    participant T as 工具注册中心
    participant V as 向量库/知识库
    participant L as LLM
    participant DB as 业务数据库

    U->>F: 输入问诊内容/上传附件
    F->>B: POST /api/v1/ai/chat/stream
    B->>R: 转换附件和问诊 payload
    R->>A: POST /api/agent/run/stream
    A->>A: 输入安全校验
    A->>A: 意图识别与步骤规划
    A-->>B: SSE: routed / step_started
    A->>T: memory_read / question_rewrite
    T->>L: 必要时调用 LLM 改写问题
    A->>T: knowledge_search / rerank
    T->>V: 检索知识片段
    V-->>T: 返回候选片段
    T-->>A: 返回检索结果与引用来源
    A->>L: answer_generation
    L-->>A: 生成回答
    A-->>B: SSE: token / sources / complete
    B->>R: 查询 run 状态和 tool_calls
    B->>DB: 写入 ai_sessions / ai_messages
    B-->>F: SSE: final response
    F-->>U: 展示回答、引用、步骤、工具调用轨迹
```

## 6. AI Agent 内部步骤图

```mermaid
flowchart TD
    Input["用户输入"] --> Validate["策略校验\npolicies.validate_input"]
    Validate --> Intent["意图识别\nIntentClassifier"]
    Intent --> Route{"任务类型"}

    Route -->|chitchat| Chitchat["闲聊/普通回答"]
    Route -->|identity_query| Identity["身份回答"]
    Route -->|knowledge_qa| KnowledgeQA["知识问答链路"]
    Route -->|admin_operation| AdminAgent["管理操作链路"]
    Route -->|其他| DefaultQA["默认知识问答链路"]

    KnowledgeQA --> HasConversation{"有 conversation_id?"}
    HasConversation -->|是| MemoryRead["memory_read"]
    HasConversation -->|否| Rewrite["question_rewrite"]
    MemoryRead --> Rewrite
    Rewrite --> NeedClarify{"问题过短或模糊?"}
    NeedClarify -->|是| Clarify["clarification"]
    NeedClarify -->|否| Search["knowledge_search"]
    Clarify --> Search
    Search --> Evaluate["result_evaluation"]
    Evaluate --> Generate["answer_generation"]
    Generate --> MemoryWrite{"需要写入记忆?"}
    MemoryWrite -->|是| SaveMemory["memory_write"]
    MemoryWrite -->|否| Output["返回 answer + sources"]
    SaveMemory --> Output

    Chitchat --> Generate
    Identity --> Output
    AdminAgent --> Output
    DefaultQA --> Rewrite
```

## 7. 管理员知识库维护流程

```mermaid
flowchart TD
    Admin["管理员"] --> KnowledgePage["前端知识库页面"]
    KnowledgePage --> ChooseCollection["选择知识分类\n症状问诊/用药咨询/报告解读/护理方法/招聘流程"]
    ChooseCollection --> Upload{"上传方式"}
    Upload -->|手动文本| TextContent["填写标题和知识内容"]
    Upload -->|文件上传| FileContent["读取文件为 Base64\n文本文件同步提取内容"]

    TextContent --> BackendCreate["POST /api/v1/admin/knowledge-items"]
    FileContent --> BackendCreate
    BackendCreate --> SaveBusiness["backend 保存 ai_knowledge_chunks 记录"]
    SaveBusiness --> Ingest["调用 python-service\nPOST /api/v1/knowledge/ingest"]
    Ingest --> Split{"内容来源"}
    Split -->|文本| TextSplit["RecursiveCharacterTextSplitter\n切分为知识片段"]
    Split -->|文件| ParseFile["DocumentParser 解析文件"]
    TextSplit --> VectorWrite["写入 FAISS/Milvus 向量库"]
    ParseFile --> VectorWrite
    VectorWrite --> MysqlChunks["兼容写入 MySQL knowledge_chunk"]
    MysqlChunks --> ReturnCount["返回 chunks_count"]
    ReturnCount --> MarkIndexed["backend 更新 rag_status/rag_chunk_count"]

    KnowledgePage --> Delete["删除知识"]
    Delete --> BackendDelete["DELETE /api/v1/admin/knowledge-items/{id}"]
    BackendDelete --> RagDelete["DELETE /api/v1/knowledge/{doc_id}"]
    RagDelete --> RemoveVector["删除向量库片段和 MySQL chunk"]
    BackendDelete --> RemoveBusiness["删除业务库知识记录"]
```

## 8. 核心数据关系图

```mermaid
erDiagram
    users ||--o{ user_roles : has
    users ||--o| patient_profiles : has
    users ||--o| caregiver_profiles : has
    caregiver_profiles ||--o{ certifications : owns

    users ||--o{ job_postings : employer
    job_postings ||--o{ applications : receives
    users ||--o{ applications : caregiver
    users ||--o{ invitations : patient
    users ||--o{ invitations : caregiver
    job_postings ||--o{ invitations : related

    users ||--o{ conversations : owner
    conversations ||--o{ messages : contains
    conversations ||--o{ reviews : reviewed
    users ||--o{ reviews : reviewer
    users ||--o{ reviews : reviewee

    users ||--o{ ai_sessions : owns
    ai_sessions ||--o{ ai_messages : contains
    ai_sessions ||--o{ medical_cases : linked
    users ||--o{ medical_cases : patient_owner

    users ||--o{ sms_notifications : receives
    users ||--o{ admin_logs : admin

    ai_model_configs ||--o{ ai_messages : config_context
    ai_knowledge_chunks ||--o{ ai_semantic_cache : cache_context
```

## 9. 后端 API 模块地图

```mermaid
flowchart LR
    Backend["/api/v1"] --> Accounts["accounts\n注册/登录/身份/资料/证书"]
    Backend --> Dashboard["dashboard\n平台概览"]
    Backend --> Jobs["jobs\n招聘/应聘/邀请/匹配"]
    Backend --> Profiles["profiles\n病人主页/护理简历"]
    Backend --> Conversations["conversations\n会话/消息"]
    Backend --> Reviews["reviews\n评价/信任摘要"]
    Backend --> AI["ai\n智能问诊网关"]
    Backend --> Admin["admin\n审核/内容/知识库/模型配置/日志"]
    Backend --> SMS["sms\n短信场景/通知/重试"]

    AI --> PythonGateway["RagServiceClient"]
    Admin --> PythonKnowledge["知识入库/删除调用 RAG 服务"]
    Jobs --> SmsService["匹配后创建短信通知"]
    Reviews --> RatingRefresh["刷新护理评分"]
```

## 10. python-service API 模块地图

```mermaid
flowchart LR
    PythonService["python-service"] --> LegacyAPI["/api\n传统 RAG API"]
    PythonService --> AgentAPI["/api/agent\nAgent 执行 API"]
    PythonService --> IntegrationAPI["/api/v1\n业务集成 API"]

    LegacyAPI --> Parse["POST /parse\n解析文档入库"]
    LegacyAPI --> Ask["POST /ask\n普通问答"]
    LegacyAPI --> AskStream["POST /ask/stream\n流式问答"]
    LegacyAPI --> Summary["POST /summary\n标题摘要"]
    LegacyAPI --> VectorOps["vector-store stats/migrate/delete"]

    AgentAPI --> Run["POST /agent/run\n同步执行"]
    AgentAPI --> RunStream["POST /agent/run/stream\nSSE 执行"]
    AgentAPI --> RunStatus["GET /agent/run/{run_id}\n状态"]
    AgentAPI --> Steps["GET /agent/run/{run_id}/steps\n步骤"]
    AgentAPI --> ToolCalls["GET /agent/run/{run_id}/tool-calls\n工具调用"]
    AgentAPI --> Tools["GET /agent/tools\n工具列表"]

    IntegrationAPI --> Ingest["POST /knowledge/ingest\n知识入库"]
    IntegrationAPI --> Delete["DELETE /knowledge/{doc_id}\n知识删除"]
```

## 11. 阅读建议

如果你想最快理解项目，可以按这个顺序看：

1. 先看“系统总体架构”，明确三个服务如何协作。
2. 再看“用户身份与主业务流程”，理解病人、护理方、管理员三类角色。
3. 接着看“护理招聘与匹配流程”，这是平台业务闭环。
4. 然后看“智能问诊处理流程”和“AI Agent 内部步骤图”，理解 AI 问诊链路。
5. 最后看“核心数据关系图”和 API 模块地图，回到代码时更容易定位文件。
