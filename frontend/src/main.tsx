import { StrictMode, type ReactNode, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { useCallback } from "react";
import { useEffect } from "react";
import {
  Activity,
  BadgeCheck,
  Bell,
  BookOpenCheck,
  BriefcaseMedical,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Database,
  FileHeart,
  Handshake,
  HeartPulse,
  IdCard,
  LayoutDashboard,
  Loader2,
  LogOut,
  MessageSquareText,
  RefreshCw,
  Search,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  Trash2,
  UploadCloud,
  UserCheck,
  UserPlus
} from "lucide-react";
import "./styles.css";

type View = "overview" | "accounts" | "consultation" | "jobs" | "profiles" | "chat" | "verification" | "knowledge";

type Metric = {
  label: string;
  value: string;
  detail: string;
  tone: "green" | "amber" | "blue" | "rose";
};

type ChatResponse = {
  answer: string;
  intent: {
    category: string;
    subcategory: string;
    confidence: number;
  };
  cache_hit_level: string;
  citations: CitationSource[];
  task_type?: string;
  run_id?: string | null;
  trace_id?: string | null;
  session_id?: string | null;
  steps?: Array<Record<string, unknown>>;
  tool_calls?: Array<Record<string, unknown>>;
  intermediate_conclusions?: Array<Record<string, unknown>>;
};

type CitationSource = {
  title?: string;
  doc?: string;
  source?: string;
  source_url?: string;
  doc_id?: string | number;
  snippet?: string;
  content?: string;
  page?: string | number;
  chunk_index?: string | number;
  hit_count?: number;
};

type AiSessionHistory = {
  id: string;
  user_id?: string | null;
  title: string;
  risk_flag: string;
  summary: string;
  created_at?: string | null;
  updated_at?: string | null;
};

type AiConversationMessage = {
  id: string;
  session_id?: string | null;
  sender: "user" | "ai" | string;
  content: string;
  intent_category?: string;
  intent_subcategory?: string;
  intent_confidence?: number;
  cache_hit_level?: string;
  metadata_json?: Record<string, unknown>;
  created_at?: string | null;
};

type StreamProcessEvent = {
  id: string;
  type: "status" | "tool" | "sources" | "error";
  label: string;
  detail: string;
  status?: string;
};

type AiFlowItem = {
  id: string;
  type: "status" | "tool" | "sources" | "error";
  label: string;
  detail: string;
  status: string;
};

type JobPosting = {
  id: string;
  employer_id: string;
  patient_id?: string | null;
  title: string;
  city: string;
  care_type: string;
  care_level: string;
  location: string;
  budget_cents: number;
  status: string;
  special_requirements: string;
  description: string;
};

type JobApplication = {
  id: string;
  job_id: string;
  caregiver_id: string;
  status: string;
  cover_letter: string;
};

type AvailableCaregiver = {
  user_id: string;
  real_name: string;
  bio: string;
  service_city: string;
  experience_years: number;
  rating_avg: number;
  is_available: boolean;
};

type Invitation = {
  id: string;
  patient_id: string;
  caregiver_id: string;
  job_id?: string | null;
  status: string;
  message: string;
};

type MatchResult = {
  status: string;
  conversation?: {
    id: string;
    title: string;
    source_type: string;
  } | null;
};

type PatientHomepage = {
  user_id: string;
  display_name: string;
  real_name: string;
  id_verified: boolean;
  verification_status: string;
  basic_info: Record<string, unknown>;
  rating_avg: number;
  review_count: number;
  recent_reviews: Array<{
    id: string;
    reviewer_id: string;
    score: number;
    comment: string;
  }>;
  public_cases: Array<{
    id: string;
    summary: string;
    public_summary: string;
    visibility: string;
  }>;
  job_history: Array<{
    id: string;
    title: string;
    city: string;
    care_type: string;
    location: string;
    budget_cents: number;
    status: string;
  }>;
};

type CaregiverResume = {
  user_id: string;
  display_name: string;
  real_name: string;
  id_verified: boolean;
  verification_status: string;
  bio: string;
  is_available: boolean;
  experience_years: number;
  service_city: string;
  rating_avg: number;
  review_count: number;
  certifications: Array<{
    id: string;
    certificate_type: string;
    description: string;
    review_status: string;
  }>;
  recent_reviews: Array<{
    id: string;
    reviewer_id: string;
    score: number;
    comment: string;
  }>;
};

type ServiceReview = {
  id: string;
  conversation_id: string;
  reviewer_id: string;
  reviewee_id: string;
  score: number;
  tags: Array<string>;
  comment: string;
};

type AdminSummary = {
  users: number;
  active_jobs: number;
  pending_certifications: number;
  ai_sessions: number;
  risk_alerts: number;
  sms_notifications: number;
  reviews: number;
};

type AdminUser = {
  id: string;
  phone: string;
  display_name: string;
  status: string;
  active_role: string;
};

type AdminCertification = {
  id: string;
  caregiver_user_id: string;
  caregiver_name: string;
  certificate_type: string;
  file_url: string;
  description: string;
  review_status: string;
  review_note: string;
};

type AdminAiModelConfig = {
  id: string;
  provider: string;
  model_name: string;
  base_url: string;
  api_key_ref: string;
  temperature: number;
  max_tokens: number;
  is_active: boolean;
};

type AdminLog = {
  id: string;
  action: string;
  target_type: string;
  target_id: string;
  target: string;
  created_at?: string | null;
};

type AdminKnowledgeItem = {
  id: string;
  collection: string;
  category: string;
  subcategory: string;
  title: string;
  content: string;
  file_name: string;
  file_type: string;
  rag_doc_id?: number | null;
  rag_status: string;
  rag_chunk_count: number;
  created_at?: string | null;
};

type RoleName = "patient" | "caregiver" | "admin";

type AccountRead = {
  id: string;
  phone: string;
  display_name: string;
  status: string;
  active_role: RoleName;
  roles: Array<{
    id: string;
    role: RoleName;
    is_active: boolean;
    verification_status: string;
  }>;
  patient_profile?: {
    real_name: string;
    id_verified: boolean;
    verification_status: string;
    basic_info: Record<string, unknown>;
  } | null;
  caregiver_profile?: {
    real_name: string;
    id_verified: boolean;
    verification_status: string;
    bio: string;
    is_available: boolean;
    experience_years: number;
    service_city: string;
    rating_avg: number;
  } | null;
  certifications: Array<{
    id: string;
    certificate_type: string;
    file_url: string;
    description: string;
    review_status: string;
    review_note: string;
  }>;
};

type AuthResponse = {
  access_token: string;
  token_type: string;
  account: AccountRead;
};

type AiAttachment = {
  file_name: string;
  file_type: string;
  content: string;
};

type CareConversation = {
  id: string;
  owner_id: string;
  participant_a?: string | null;
  participant_b?: string | null;
  kind: string;
  source_type: string;
  source_id?: string | null;
  title: string;
  created_at?: string | null;
  updated_at?: string | null;
};

type CareMessage = {
  id: string;
  conversation_id: string;
  sender_id?: string | null;
  sender_type: string;
  body: string;
  content: string;
  attachment_url: string;
  attachment_type: string;
  created_at?: string | null;
};

const navItems: Array<{ id: View; label: string; icon: ReactNode; adminOnly?: boolean }> = [
  { id: "overview", label: "流程总览", icon: <LayoutDashboard size={18} /> },
  { id: "accounts", label: "我的信息", icon: <UserCheck size={18} /> },
  { id: "jobs", label: "招聘页面", icon: <BriefcaseMedical size={18} /> },
  { id: "profiles", label: "应聘发布", icon: <IdCard size={18} /> },
  { id: "chat", label: "聊天沟通", icon: <Handshake size={18} /> },
  { id: "consultation", label: "智能问诊", icon: <MessageSquareText size={18} /> },
  { id: "verification", label: "审核管理", icon: <UserCheck size={18} />, adminOnly: true },
  { id: "knowledge", label: "知识库", icon: <BookOpenCheck size={18} />, adminOnly: true }
];

const metrics: Metric[] = [
  { label: "智能问诊次数", value: "1,284", detail: "本周增长 18.6%", tone: "green" },
  { label: "护理招聘", value: "326", detail: "72 条等待匹配", tone: "blue" },
  { label: "审核队列", value: "41", detail: "12 条需优先处理", tone: "amber" },
  { label: "风险提醒", value: "8", detail: "已进入紧急处理流程", tone: "rose" }
];

const pipelines = [
  { label: "紧急风险过滤", value: 100, status: "运行中" },
  { label: "意图识别", value: 96, status: "正常" },
  { label: "知识检索", value: 91, status: "正常" },
  { label: "语义缓存", value: 74, status: "预热中" }
];

const consultationTrend = [
  { label: "周一", value: 86 },
  { label: "周二", value: 112 },
  { label: "周三", value: 98 },
  { label: "周四", value: 134 },
  { label: "周五", value: 156 },
  { label: "周六", value: 128 },
  { label: "周日", value: 172 }
];

const intentDistribution = [
  { label: "症状问诊", value: 34 },
  { label: "用药咨询", value: 24 },
  { label: "报告解读", value: 18 },
  { label: "护理方法", value: 15 },
  { label: "招聘流程", value: 9 }
];

const consultationQuality = [
  { label: "平均响应", value: "2.4 秒", detail: "较昨日减少 0.3 秒" },
  { label: "引用命中", value: "91%", detail: "知识库检索稳定" },
  { label: "高风险提醒", value: "8", detail: "已提示转人工或就医" }
];

const jobs = [
  {
    title: "术后陪护护理",
    city: "上海",
    patient: "髋部术后老人恢复期",
    budget: "480 元/天",
    status: "匹配中",
    applicants: 18
  },
  {
    title: "夜间病房陪护",
    city: "杭州",
    patient: "需要呼吸状态观察",
    budget: "360 元/天",
    status: "沟通中",
    applicants: 9
  },
  {
    title: "居家康复协助",
    city: "苏州",
    patient: "中风康复辅助",
    budget: "520 元/天",
    status: "已发布",
    applicants: 24
  }
];

const verifications = [
  { name: "林悦", role: "护理方", stage: "证书审核", score: 92 },
  { name: "陈浩", role: "护理助理", stage: "实名审核", score: 87 },
  { name: "王敏", role: "病人家属", stage: "手机号验证", score: 99 }
];

const collections = [
  { name: "症状问诊", key: "medical.symptom_inquiry", chunks: 1260, freshness: "已启用" },
  { name: "用药咨询", key: "medical.medication_consult", chunks: 860, freshness: "已启用" },
  { name: "报告解读", key: "medical.report_interpretation", chunks: 540, freshness: "已启用" },
  { name: "护理方法", key: "medical.care_method", chunks: 720, freshness: "已启用" },
  { name: "招聘流程", key: "platform.recruitment_process", chunks: 160, freshness: "已启用" }
];

const defaultKnowledgeCollection = "platform.general_knowledge";
const recentKnowledgePageSize = 3;
const allKnowledgePageSize = 5;


const identitySteps = [
  { title: "注册或登录", text: "支持手机号和密码进入系统。" },
  { title: "创建身份资料", text: "同一账号可分别维护病人和护理资料。" },
  { title: "切换当前身份", text: "当前身份决定可见的业务流程和资料上传通道。" },
  { title: "查看审核状态", text: "病人实名和护理证书会显示待审核、通过或驳回状态。" }
];

const identityProfiles = [
  { label: "病人身份", status: "实名资料待审核", detail: "可发布护理招聘、维护病例、邀请护理方、沟通并使用 智能问诊。" },
  { label: "护理身份", status: "证书资料待审核", detail: "可维护简历、上传证书、应聘岗位、接受邀请并管理接单状态。" },
  { label: "管理员审核", status: "审核队列可用", detail: "可审核护理证书、实名结果、平台内容和模型配置。" }
];

const currentSessionKey = "doctor-care-platform-current-session";

type StoredSession = {
  access_token?: string;
  account: AccountRead;
  saved_at: string;
};

function loadCurrentSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(currentSessionKey);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as Partial<StoredSession>;
    if (!parsed.account || typeof parsed.account.id !== "string" || typeof parsed.account.phone !== "string") {
      return null;
    }
    return parsed as StoredSession;
  } catch {
    return null;
  }
}

function saveCurrentSession(account: AccountRead, accessToken?: string) {
  const previous = loadCurrentSession();
  const session: StoredSession = {
    access_token: accessToken ?? previous?.access_token,
    account,
    saved_at: new Date().toISOString()
  };
  localStorage.setItem(currentSessionKey, JSON.stringify(session));
}

function clearCurrentSession() {
  localStorage.removeItem(currentSessionKey);
}

async function fetchAccountIdentity(userId: string): Promise<AccountRead> {
  const response = await fetch(`/api/v1/accounts/${encodeURIComponent(userId)}/identity`);
  if (!response.ok) {
    throw new Error(await response.text() || `接口返回 ${response.status}`);
  }
  return response.json() as Promise<AccountRead>;
}

function App() {
  const [account, setAccountState] = useState<AccountRead | null>(() => loadCurrentSession()?.account ?? null);
  const [restoringSession, setRestoringSession] = useState(() => Boolean(loadCurrentSession()?.account));
  const [activeView, setActiveView] = useState<View>("overview");
  const isAdmin = Boolean(account && isAdminAccount(account));
  const visibleNavItems = navItems.filter((item) => !item.adminOnly || isAdmin);
  const activeLabel = visibleNavItems.find((item) => item.id === activeView)?.label ?? "流程总览";

  const setAccount = useCallback((nextAccount: AccountRead) => {
    saveCurrentSession(nextAccount);
    setAccountState(nextAccount);
  }, []);

  function logout() {
    clearCurrentSession();
    setAccountState(null);
    setActiveView("overview");
  }

  function handleAuthenticated(result: AuthResponse) {
    saveCurrentSession(result.account, result.access_token);
    setAccountState(result.account);
  }

  useEffect(() => {
    if (!visibleNavItems.some((item) => item.id === activeView)) {
      setActiveView("overview");
    }
  }, [activeView, visibleNavItems]);

  useEffect(() => {
    const cachedAccount = loadCurrentSession()?.account;
    if (!cachedAccount) {
      setRestoringSession(false);
      return;
    }
    let cancelled = false;
    setRestoringSession(true);
    fetchAccountIdentity(cachedAccount.id)
      .then((freshAccount) => {
        if (cancelled) {
          return;
        }
        saveCurrentSession(freshAccount);
        setAccountState(freshAccount);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setAccountState(cachedAccount);
      })
      .finally(() => {
        if (!cancelled) {
          setRestoringSession(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!account) {
    if (restoringSession) {
      return (
        <main className="authShell">
          <section className="authPanel">
            <div className="authBrand brand">
              <div className="brandMark">
                <HeartPulse size={24} />
              </div>
              <div>
                <strong>DoctorCarePlatform</strong>
                <span>正在恢复登录状态</span>
              </div>
            </div>
          </section>
        </main>
      );
    }
    return <AuthGate onAuthenticated={handleAuthenticated} />;
  }

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">
            <HeartPulse size={24} />
          </div>
          <div>
            <strong>DoctorCarePlatform</strong>
            <span>医护陪护服务平台</span>
          </div>
        </div>

        <nav className="navList" aria-label="主导航">
          {visibleNavItems.map((item) => (
            <button
              className={activeView === item.id ? "active" : ""}
              key={item.id}
              onClick={() => setActiveView(item.id)}
              type="button"
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebarStatus">
          <span className="statusDot" />
          <div>
            <strong>{account.display_name || account.phone}</strong>
            <span>{isAdmin ? "管理员" : roleLabel(account.active_role)} / {statusLabel(account.status)}</span>
          </div>
        </div>
        <button className="logoutButton sidebarLogoutButton" onClick={logout} type="button">
          <LogOut size={18} />
          <span>退出登录</span>
        </button>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">医护陪护服务平台</p>
            <h1>{activeLabel}</h1>
          </div>
          <div className="topbarActions">
            <button className="iconButton" title="通知" type="button">
              <Bell size={19} />
            </button>
            <button className="iconButton" title="审核状态" type="button">
              <BadgeCheck size={19} />
            </button>
          </div>
        </header>

        {activeView === "overview" && <Overview />}
        {activeView === "accounts" && <AccountsIdentity account={account} setAccount={setAccount} />}
        {activeView === "consultation" && <Consultation account={account} />}
        {activeView === "jobs" && <Jobs account={account} onOpenChat={() => setActiveView("chat")} />}
        {activeView === "profiles" && <Profiles account={account} onOpenChat={() => setActiveView("chat")} />}
        {activeView === "chat" && <CareChat account={account} />}
        {activeView === "verification" && isAdmin && <Verification />}
        {activeView === "knowledge" && isAdmin && <Knowledge />}
      </section>
    </main>
  );
}

function roleLabel(role: RoleName) {
  if (role === "admin") {
    return "管理员";
  }
  return role === "patient" ? "病人" : "护理";
}

function statusLabel(status: string | undefined | null) {
  const labels: Record<string, string> = {
    completed: "已完成",
    success: "成功",
    running: "运行中",
    failed: "失败",
    active: "正常",
    disabled: "禁用",
    suspended: "暂停",
    pending: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
    submitted: "已提交",
    accepted: "已接受",
    published: "已发布",
    matched: "已匹配",
    closed: "已关闭",
    cancelled: "已取消",
    indexed: "已入库",
    draft: "草稿",
    public: "公开",
    private: "私密",
    summary_public: "摘要公开",
    demo: "演示",
    patient: "病人",
    caregiver: "护理"
  };
  return labels[status || ""] || status || "暂无";
}

function sourceTypeLabel(sourceType: string | undefined | null) {
  const labels: Record<string, string> = {
    job: "招聘",
    application: "应聘",
    invitation: "邀请",
    profile: "资料",
    direct: "直接沟通",
    smoke: "测试"
  };
  return labels[sourceType || ""] || sourceType || "直接沟通";
}

function knowledgeStatusLabel(status: string | undefined | null) {
  const labels: Record<string, string> = {
    pending: "后台解析中",
    indexing: "后台解析中",
    indexed: "已入库",
    failed: "解析失败"
  };
  return labels[status || ""] || statusLabel(status);
}

function isAdminAccount(account: AccountRead) {
  return account.phone.toLowerCase().startsWith("admin") || account.roles.some((role) => role.role === "admin");
}

type RememberedAccount = {
  phone: string;
  display_name: string;
};

const rememberedAccountsKey = "doctor-care-platform-remembered-accounts";

function loadRememberedAccounts(): RememberedAccount[] {
  try {
    const raw = localStorage.getItem(rememberedAccountsKey);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed
      .filter((item): item is RememberedAccount => typeof item?.phone === "string" && typeof item?.display_name === "string")
      .slice(0, 8);
  } catch {
    return [];
  }
}

function saveRememberedAccount(account: AccountRead) {
  const nextAccount: RememberedAccount = {
    phone: account.phone,
    display_name: account.display_name || account.phone
  };
  const next = [nextAccount, ...loadRememberedAccounts().filter((item) => item.phone !== account.phone)].slice(0, 8);
  localStorage.setItem(rememberedAccountsKey, JSON.stringify(next));
}

function AuthGate({ onAuthenticated }: { onAuthenticated: (result: AuthResponse) => void }) {
  const [authMode, setAuthMode] = useState<"register" | "login">("login");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [rememberAccount, setRememberAccount] = useState(true);
  const [rememberedAccounts, setRememberedAccounts] = useState<RememberedAccount[]>(() => loadRememberedAccounts());
  const [authForm, setAuthForm] = useState({
    phone: "",
    password: "",
    display_name: "",
    initial_role: "patient" as RoleName
  });

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  function handleAccountInput(phone: string) {
    const remembered = rememberedAccounts.find((item) => item.phone === phone);
    setAuthForm((current) => ({
      ...current,
      phone,
      display_name: authMode === "login" && remembered ? remembered.display_name || current.display_name : current.display_name
    }));
    setNotice("");
  }

  async function submitAuth() {
    setLoading(true);
    setNotice("");
    try {
      const path = authMode === "register" ? "/api/v1/accounts/register" : "/api/v1/accounts/login";
      const payload =
        authMode === "register"
          ? authForm
          : { phone: authForm.phone, password: authForm.password };
      const result = await requestJson<AuthResponse>(path, {
        method: "POST",
        body: JSON.stringify(payload)
      });
      if (authMode === "login" && rememberAccount) {
        saveRememberedAccount(result.account);
        setRememberedAccounts(loadRememberedAccounts());
      }
      onAuthenticated(result);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "登录或注册失败。");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="authShell">
      <section className="authPanel">
        <div className="brand authBrand">
          <div className="brandMark">
            <HeartPulse size={24} />
          </div>
          <div>
            <strong>DoctorCarePlatform</strong>
            <span>医护陪护服务平台</span>
          </div>
        </div>
        <h1>{authMode === "login" ? "登录平台" : "注册账号"}</h1>
        {notice && <p className="notice">{notice}</p>}
        <div className="formGrid authForm">
          <div className="accountField">
            <input
              list="rememberedAccountOptions"
              placeholder="手机号/账号"
              value={authForm.phone}
              onChange={(event) => handleAccountInput(event.target.value)}
            />
            <datalist id="rememberedAccountOptions">
              {rememberedAccounts.map((item) => (
                <option key={item.phone} label={item.display_name} value={item.phone} />
              ))}
            </datalist>
          </div>
          <input placeholder="密码" type="password" value={authForm.password} onChange={(event) => setAuthForm({ ...authForm, password: event.target.value })} />
          {authMode === "register" && (
            <>
              <input placeholder="昵称" value={authForm.display_name} onChange={(event) => setAuthForm({ ...authForm, display_name: event.target.value })} />
              <select value={authForm.initial_role} onChange={(event) => setAuthForm({ ...authForm, initial_role: event.target.value as RoleName })}>
                <option value="patient">病人身份</option>
                <option value="caregiver">护理身份</option>
              </select>
            </>
          )}
        </div>
        {authMode === "login" && (
          <label className="checkLine rememberLine">
            <input checked={rememberAccount} onChange={(event) => setRememberAccount(event.target.checked)} type="checkbox" />
            <span>记住账号，下次可从下拉列表快速选择</span>
          </label>
        )}
        <button className="primaryButton" disabled={loading || !authForm.phone.trim() || !authForm.password.trim()} onClick={submitAuth} type="button">
          {loading ? <Loader2 className="spin" size={18} /> : authMode === "register" ? <UserPlus size={18} /> : <Send size={18} />}
          <span>{authMode === "register" ? "创建账号并进入" : "登录系统"}</span>
        </button>
        <p className="authSwitchText">
          {authMode === "login" ? "还没有账号，" : "已有账号，"}
          <button
            onClick={() => {
              setAuthMode(authMode === "login" ? "register" : "login");
              setNotice("");
            }}
            type="button"
          >
            {authMode === "login" ? "现在去注册" : "返回登录"}
          </button>
        </p>
      </section>
    </main>
  );
}

function Overview() {
  return (
    <>
      <section className="metrics">
        {metrics.map((metric) => (
          <article className={`metric ${metric.tone}`} key={metric.label}>
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <small>{metric.detail}</small>
          </article>
        ))}
      </section>

      <section className="dashboardGrid">
        <article className="panel wide">
          <div className="panelHeader">
            <div>
              <h2>智能问诊趋势</h2>
              <p>展示近一周问诊量变化，便于管理员和业务方观察使用高峰。</p>
            </div>
            <Sparkles size={22} />
          </div>
          <div className="barChart" aria-label="智能问诊趋势图">
            {consultationTrend.map((item) => (
              <div className="barColumn" key={item.label}>
                <span>{item.value}</span>
                <div style={{ height: `${Math.max(24, item.value)}px` }} />
                <strong>{item.label}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader compact">
            <h2>问诊意图分布</h2>
            <Activity size={20} />
          </div>
          <div className="distributionList">
            {intentDistribution.map((item) => (
              <div className="distributionItem" key={item.label}>
                <div>
                  <strong>{item.label}</strong>
                  <span>{item.value}%</span>
                </div>
                <meter max="100" value={item.value} />
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader compact">
            <h2>问诊质量</h2>
            <CalendarClock size={20} />
          </div>
          <div className="qualityList">
            {consultationQuality.map((item) => (
              <div className="qualityItem" key={item.label}>
                <span>{item.label}</span>
                <strong>{item.value}</strong>
                <small>{item.detail}</small>
              </div>
            ))}
          </div>
        </article>
      </section>
    </>
  );
}


function AccountsIdentity({
  account,
  setAccount
}: {
  account: AccountRead;
  setAccount: (account: AccountRead) => void;
}) {
  const [notice, setNotice] = useState("");
  const [patientForm, setPatientForm] = useState({
    real_name: account.patient_profile?.real_name ?? "",
    id_number: "",
    age: String(account.patient_profile?.basic_info?.age ?? ""),
    care_need: String(account.patient_profile?.basic_info?.care_need ?? "")
  });
  const [caregiverForm, setCaregiverForm] = useState({
    real_name: account.caregiver_profile?.real_name ?? "",
    id_number: "",
    bio: account.caregiver_profile?.bio ?? "",
    service_city: account.caregiver_profile?.service_city ?? "",
    experience_years: account.caregiver_profile?.experience_years ?? 0,
    is_available: account.caregiver_profile?.is_available ?? true
  });
  const [certForm, setCertForm] = useState({
    certificate_type: "护理员资格证",
    file_url: "",
    description: ""
  });
  const [caseForm, setCaseForm] = useState({
    file_url: "",
    summary: "",
    description: ""
  });
  const [caseUploads, setCaseUploads] = useState<Array<{ file_url: string; summary: string; description: string }>>([]);

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function refreshIdentity(userId = account?.id) {
    if (!userId) {
      return;
    }
    setAccount(await requestJson<AccountRead>(`/api/v1/accounts/${userId}/identity`));
  }

  async function createRole(role: RoleName) {
    if (!account) {
      setNotice("请先注册或登录账号。");
      return;
    }
    try {
      const updated = await requestJson<AccountRead>(`/api/v1/accounts/${account.id}/roles`, {
        method: "POST",
        body: JSON.stringify({ role })
      });
      setAccount(updated);
      setNotice(`已开通${roleLabel(role)}身份。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "开通身份失败。");
    }
  }

  async function switchRole(role: RoleName) {
    if (!account) {
      setNotice("请先注册或登录账号。");
      return;
    }
    try {
      const updated = await requestJson<AccountRead>(`/api/v1/accounts/${account.id}/roles/switch`, {
        method: "POST",
        body: JSON.stringify({ role })
      });
      setAccount(updated);
      setNotice(`已切换为${roleLabel(role)}身份。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "切换身份失败。");
    }
  }

  async function savePatientProfile() {
    if (!account) {
      setNotice("请先注册或登录账号。");
      return;
    }
    try {
      const basic_info: Record<string, unknown> = {};
      if (patientForm.age) {
        basic_info.age = Number(patientForm.age);
      }
      if (patientForm.care_need) {
        basic_info.care_need = patientForm.care_need;
      }
      if (caseUploads.length) {
        basic_info.case_uploads = caseUploads;
      }
      const updated = await requestJson<AccountRead>(`/api/v1/accounts/${account.id}/profiles/patient`, {
        method: "PUT",
        body: JSON.stringify({
          real_name: patientForm.real_name,
          id_number: patientForm.id_number,
          basic_info
        })
      });
      setAccount(updated);
      setNotice("病人资料已保存。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "保存病人资料失败。");
    }
  }

  async function saveCaregiverProfile() {
    if (!account) {
      setNotice("请先注册或登录账号。");
      return;
    }
    try {
      const updated = await requestJson<AccountRead>(`/api/v1/accounts/${account.id}/profiles/caregiver`, {
        method: "PUT",
        body: JSON.stringify(caregiverForm)
      });
      setAccount(updated);
      setNotice("护理资料已保存。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "保存护理资料失败。");
    }
  }

  async function submitCertification() {
    if (!account) {
      setNotice("请先注册或登录账号。");
      return;
    }
    try {
      await requestJson(`/api/v1/accounts/${account.id}/certifications`, {
        method: "POST",
        body: JSON.stringify(certForm)
      });
      await refreshIdentity(account.id);
      setNotice("护理认证材料已提交，等待审核。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "提交护理认证失败。");
    }
  }

  function handleCertificateFile(files: FileList | null) {
    const file = files?.[0];
    if (!file) {
      return;
    }
    setCertForm({
      ...certForm,
      file_url: `local-upload://${file.name}`,
      description: certForm.description || `已选择文件：${file.name}`
    });
  }

  function handleCaseFile(files: FileList | null) {
    const file = files?.[0];
    if (!file) {
      return;
    }
    setCaseForm({
      ...caseForm,
      file_url: `local-upload://${file.name}`,
      description: caseForm.description || `已选择病例文件：${file.name}`
    });
  }

  async function submitCaseUpload() {
    if (!caseForm.file_url.trim() && !caseForm.summary.trim()) {
      setNotice("请先选择病例文件或填写病例摘要。");
      return;
    }
    const nextUploads = [
      {
        file_url: caseForm.file_url,
        summary: caseForm.summary,
        description: caseForm.description
      },
      ...caseUploads
    ];
    setCaseUploads(nextUploads);
    setCaseForm({ file_url: "", summary: "", description: "" });
    const basic_info: Record<string, unknown> = {
      ...(account.patient_profile?.basic_info ?? {}),
      case_uploads: nextUploads
    };
    if (patientForm.age) {
      basic_info.age = Number(patientForm.age);
    }
    if (patientForm.care_need) {
      basic_info.care_need = patientForm.care_need;
    }
    try {
      const updated = await requestJson<AccountRead>(`/api/v1/accounts/${account.id}/profiles/patient`, {
        method: "PUT",
        body: JSON.stringify({
          real_name: patientForm.real_name,
          id_number: patientForm.id_number,
          basic_info
        })
      });
      setAccount(updated);
      setNotice("病例资料已上传。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "上传病例资料失败。");
    }
  }

  const hasPatient = Boolean(account?.roles.some((item) => item.role === "patient"));
  const hasCaregiver = Boolean(account?.roles.some((item) => item.role === "caregiver"));
  const patientRole = account.roles.find((item) => item.role === "patient");
  const caregiverRole = account.roles.find((item) => item.role === "caregiver");
  const activeRole = account.active_role;

  return (
    <section className="profileCenterLayout">
      <article className="panel accountHero">
        <div className="panelHeader">
          <div>
            <h2>当前账号</h2>
            <p>在这里切换病人或护理身份，不同身份只显示对应资料通道。</p>
          </div>
          <UserCheck size={22} />
        </div>
        {notice && <p className="notice">{notice}</p>}
        <div className="accountCard">
          <div className="profileHeaderLine">
            <div className="profileAvatar">{(account.display_name || account.phone || "U").slice(0, 1)}</div>
            <div>
              <strong>{account.display_name || account.phone}</strong>
              <span>{account.phone}</span>
            </div>
            <span className="pill">{roleLabel(activeRole)}</span>
          </div>
          <div className="identitySlider" aria-label="身份切换">
            <button
              className={activeRole === "patient" ? "active" : ""}
              onClick={() => void (hasPatient ? switchRole("patient") : createRole("patient"))}
              type="button"
            >
              <span>病人</span>
              <small>{patientRole ? statusLabel(patientRole.verification_status) : "未开通"}</small>
            </button>
            <button
              className={activeRole === "caregiver" ? "active" : ""}
              onClick={() => void (hasCaregiver ? switchRole("caregiver") : createRole("caregiver"))}
              type="button"
            >
              <span>护理</span>
              <small>{caregiverRole ? statusLabel(caregiverRole.verification_status) : "未开通"}</small>
            </button>
            <span className={`sliderThumb ${activeRole === "caregiver" ? "caregiver" : ""}`} />
          </div>
          <div className="buttonRow">
            <button className="secondaryButton" disabled={hasPatient} onClick={() => void createRole("patient")} type="button">开通病人</button>
            <button className="secondaryButton" disabled={hasCaregiver} onClick={() => void createRole("caregiver")} type="button">开通护理</button>
          </div>
          <div className="profileFacts">
            <div>
              <span>用户ID</span>
              <strong>{account.id.slice(0, 8)}</strong>
            </div>
            <div>
              <span>病人审核</span>
              <strong>{account.patient_profile ? statusLabel(account.patient_profile.verification_status) : "未开通"}</strong>
            </div>
            <div>
              <span>护理审核</span>
              <strong>{account.caregiver_profile ? statusLabel(account.caregiver_profile.verification_status) : "未开通"}</strong>
            </div>
          </div>
        </div>
      </article>

      {activeRole === "patient" && (
        <article className="panel identityWorkbench">
          <div className="panelHeader compact">
            <h2>病人资料与病例上传</h2>
            <FileHeart size={20} />
          </div>
          <div className="formGrid">
            <input placeholder="真实姓名" value={patientForm.real_name} onChange={(event) => setPatientForm({ ...patientForm, real_name: event.target.value })} />
            <input placeholder="身份证号" value={patientForm.id_number} onChange={(event) => setPatientForm({ ...patientForm, id_number: event.target.value })} />
            <input placeholder="年龄" value={patientForm.age} onChange={(event) => setPatientForm({ ...patientForm, age: event.target.value })} />
            <input placeholder="护理需求" value={patientForm.care_need} onChange={(event) => setPatientForm({ ...patientForm, care_need: event.target.value })} />
          </div>
          <button className="secondaryButton" onClick={savePatientProfile} type="button">保存病人资料</button>
          <div className="formGrid certificateForm">
            <input placeholder="病例文件地址" value={caseForm.file_url} onChange={(event) => setCaseForm({ ...caseForm, file_url: event.target.value })} />
            <label className="uploadControl" htmlFor="caseFileUpload">
              <UploadCloud size={20} />
              <span>
                <strong>选择病例文件</strong>
                <small>{caseForm.file_url ? caseForm.file_url.replace("local-upload://", "") : "支持报告、病历、护理记录"}</small>
              </span>
              <input id="caseFileUpload" onChange={(event) => handleCaseFile(event.target.files)} type="file" />
            </label>
            <input placeholder="病例摘要" value={caseForm.summary} onChange={(event) => setCaseForm({ ...caseForm, summary: event.target.value })} />
            <input placeholder="病例说明" value={caseForm.description} onChange={(event) => setCaseForm({ ...caseForm, description: event.target.value })} />
          </div>
          <button className="primaryButton" onClick={submitCaseUpload} type="button">
            <Send size={18} />
            <span>上传病例资料</span>
          </button>
          <div className="miniList">
            <div className="miniItem">
              <div>
                <strong>{account.patient_profile?.real_name || "未填写病人资料"}</strong>
                <span>{statusLabel(account.patient_profile?.verification_status || "pending")} / 可发布招聘信息、维护病例并进行 智能问诊</span>
              </div>
            </div>
            {caseUploads.map((item, index) => (
              <div className="miniItem" key={`${item.file_url}-${index}`}>
                <div>
                  <strong>{item.summary || "病例资料"}</strong>
                  <span>{item.description || item.file_url || "无说明"}</span>
                </div>
              </div>
            ))}
          </div>
        </article>
      )}

      {activeRole === "caregiver" && (
        <article className="panel identityWorkbench">
          <div className="panelHeader compact">
            <h2>护理资料与证书上传</h2>
            <IdCard size={20} />
          </div>
          <div className="formGrid">
            <input placeholder="真实姓名" value={caregiverForm.real_name} onChange={(event) => setCaregiverForm({ ...caregiverForm, real_name: event.target.value })} />
            <input placeholder="身份证号" value={caregiverForm.id_number} onChange={(event) => setCaregiverForm({ ...caregiverForm, id_number: event.target.value })} />
            <input placeholder="服务城市" value={caregiverForm.service_city} onChange={(event) => setCaregiverForm({ ...caregiverForm, service_city: event.target.value })} />
            <input type="number" min="0" placeholder="经验年限" value={caregiverForm.experience_years} onChange={(event) => setCaregiverForm({ ...caregiverForm, experience_years: Number(event.target.value) })} />
          </div>
          <textarea placeholder="护理经验、擅长服务、可服务时间" value={caregiverForm.bio} onChange={(event) => setCaregiverForm({ ...caregiverForm, bio: event.target.value })} />
          <label className="checkLine">
            <input checked={caregiverForm.is_available} onChange={(event) => setCaregiverForm({ ...caregiverForm, is_available: event.target.checked })} type="checkbox" />
            <span>当前可接单</span>
          </label>
          <div className="buttonRow">
            <button className="secondaryButton" onClick={saveCaregiverProfile} type="button">保存护理资料</button>
          </div>
          <div className="formGrid certificateForm">
            <input placeholder="证书类型" value={certForm.certificate_type} onChange={(event) => setCertForm({ ...certForm, certificate_type: event.target.value })} />
            <input placeholder="证书文件地址" value={certForm.file_url} onChange={(event) => setCertForm({ ...certForm, file_url: event.target.value })} />
            <label className="uploadControl" htmlFor="certificateFileUpload">
              <UploadCloud size={20} />
              <span>
                <strong>选择证书文件</strong>
                <small>{certForm.file_url ? certForm.file_url.replace("local-upload://", "") : "上传护理证书、资质证明"}</small>
              </span>
              <input id="certificateFileUpload" onChange={(event) => handleCertificateFile(event.target.files)} type="file" />
            </label>
            <input placeholder="证书说明" value={certForm.description} onChange={(event) => setCertForm({ ...certForm, description: event.target.value })} />
          </div>
          <button className="primaryButton" onClick={submitCertification} type="button">
            <Send size={18} />
            <span>提交护理认证</span>
          </button>
          <div className="miniList">
            {account.certifications.map((certification) => (
              <div className="miniItem" key={certification.id}>
                <div>
                  <strong>{certification.certificate_type}</strong>
                  <span>{statusLabel(certification.review_status)} / {certification.description || certification.file_url || "无说明"}</span>
                </div>
              </div>
            ))}
            {!account.certifications.length && <p className="mutedText">暂无护理认证记录。</p>}
          </div>
        </article>
      )}
    </section>
  );
}
function Consultation({ account }: { account: AccountRead }) {
  const [message, setMessage] = useState("老人术后夜间疼痛明显，当前用药说明和护理记录见附件，请帮我判断需要重点观察什么。");
  const [attachments, setAttachments] = useState<AiAttachment[]>([]);
  const [response, setResponse] = useState<ChatResponse | null>(null);
  const [sessions, setSessions] = useState<AiSessionHistory[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<AiConversationMessage[]>([]);
  const [processEvents, setProcessEvents] = useState<StreamProcessEvent[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const result = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!result.ok) {
      const detail = await result.text();
      throw new Error(detail || `接口返回 ${result.status}`);
    }
    return result.json() as Promise<T>;
  }

  async function loadSessions(nextSelectedId?: string | null) {
    setHistoryLoading(true);
    try {
      const rows = await requestJson<AiSessionHistory[]>(`/api/v1/ai/sessions?user_id=${encodeURIComponent(account.id)}&limit=80`);
      setSessions(rows);
      const targetId = nextSelectedId ?? selectedSessionId ?? rows[0]?.id ?? null;
      setSelectedSessionId(targetId);
      if (targetId) {
        await loadSessionMessages(targetId);
      } else {
        setChatMessages([]);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载历史问诊失败。");
    } finally {
      setHistoryLoading(false);
    }
  }

  async function loadSessionMessages(sessionId: string) {
    try {
      const rows = await requestJson<AiConversationMessage[]>(
        `/api/v1/ai/sessions/${sessionId}/messages?user_id=${encodeURIComponent(account.id)}&limit=300`
      );
      setChatMessages(rows);
      const lastAiMessage = [...rows].reverse().find((item) => item.sender === "ai");
      if (lastAiMessage) {
        setResponse(responseFromStoredMessage(lastAiMessage));
      } else {
        setResponse(null);
      }
      setProcessEvents([]);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "加载问诊消息失败。");
    }
  }

  function startNewSession() {
    setSelectedSessionId(null);
    setChatMessages([]);
    setResponse(null);
    setProcessEvents([]);
    setError("");
    setMessage("");
    setAttachments([]);
  }

  useEffect(() => {
    void loadSessions();
  }, [account.id]);

  async function submitConsultation() {
    const outgoingText = message.trim();
    if (!outgoingText) {
      return;
    }
    setLoading(true);
    setError("");
    setProcessEvents([]);
    const pendingUserId = `pending-user-${Date.now()}`;
    const pendingAiId = `pending-ai-${Date.now()}`;
    setChatMessages((current) => [
      ...current,
      {
        id: pendingUserId,
        session_id: selectedSessionId,
        sender: "user",
        content: outgoingText,
        created_at: new Date().toISOString()
      },
      {
        id: pendingAiId,
        session_id: selectedSessionId,
        sender: "ai",
        content: "",
        intent_category: "medical_consult",
        intent_subcategory: "streaming",
        cache_hit_level: "streaming",
        created_at: new Date().toISOString()
      }
    ]);
    setResponse({
      answer: "",
      intent: { category: "medical_consult", subcategory: "streaming", confidence: 0 },
      cache_hit_level: "streaming",
      citations: [],
      tool_calls: [],
      steps: [],
      intermediate_conclusions: []
    });
    try {
      const result = await fetch("/api/v1/ai/chat/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: outgoingText,
          attachments,
          user_id: account.id,
          conversation_id: selectedSessionId
        })
      });
      if (!result.ok) {
        throw new Error(`接口返回 ${result.status}`);
      }
      if (!result.body) {
        throw new Error("浏览器不支持流式响应。");
      }
      await consumeConsultationStream(result.body, pendingAiId);
      setMessage("");
      setAttachments([]);
    } catch {
      const demoResponse = {
        answer:
          "演示回复：当前页面暂未连通本地后端，但问诊界面已经可用。请启动 8000 端口后端服务后获取真实回复。",
        intent: { category: "medical_consult", subcategory: "medication_consult", confidence: 0.95 },
        cache_hit_level: "demo",
        citations: [
          {
            title: "用药安全",
            snippet: "用药相关问题会进入用药咨询知识库检索。"
          }
        ]
      };
      setResponse(demoResponse);
      setChatMessages((current) => current.map((item) => item.id === pendingAiId ? {
        ...item,
        content: demoResponse.answer,
        intent_category: demoResponse.intent.category,
        intent_subcategory: demoResponse.intent.subcategory,
        cache_hit_level: demoResponse.cache_hit_level
      } : item));
      setProcessEvents([
        {
          id: "demo-status",
          type: "status",
          label: "演示模式",
          detail: "未连接到后端流式接口，显示内置示例。",
          status: "completed"
        }
      ]);
      setError("由于接口暂不可达，当前显示内置演示回复。");
    } finally {
      setLoading(false);
    }
  }

  async function consumeConsultationStream(body: ReadableStream<Uint8Array>, pendingAiId: string) {
    const reader = body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";
      events.forEach((event) => handleStreamChunk(event, pendingAiId));
    }

    if (buffer.trim()) {
      handleStreamChunk(buffer, pendingAiId);
    }
  }

  function handleStreamChunk(rawEvent: string, pendingAiId: string) {
    const payload = parseSsePayload(rawEvent);
    if (!payload) {
      return;
    }
    const type = String(payload.type || "");
    if (type === "token") {
      const content = String(payload.content || "");
      setResponse((current) => ({
        ...(current || {
          intent: { category: "medical_consult", subcategory: "streaming", confidence: 0 },
          cache_hit_level: "streaming",
          citations: []
        }),
        answer: `${current?.answer || ""}${content}`
      }));
      setChatMessages((current) => current.map((item) => item.id === pendingAiId ? { ...item, content: `${item.content || ""}${content}` } : item));
    } else if (type === "status") {
      const detail = String(payload.detail || "");
      appendProcessEvent({
        type: "status",
        label: String(payload.label || "正在处理"),
        detail,
        status: detail.includes("处理中") ? "running" : "completed"
      });
    } else if (type === "tool") {
      const toolCall = asRecord(payload.tool_call);
      const toolName = String(toolCall.tool_name || "tool");
      appendProcessEvent({
        type: "tool",
        label: toolLabel(toolName),
        detail: summarizeToolCall(toolCall),
        status: String(toolCall.status || "completed")
      });
      setResponse((current) => ({
        ...(current || emptyStreamingResponse()),
        tool_calls: [...(current?.tool_calls || []), toolCall]
      }));
    } else if (type === "sources") {
      const sources = Array.isArray(payload.sources) ? payload.sources as ChatResponse["citations"] : [];
      const documentCount = countCitationDocuments(sources);
      appendProcessEvent({
        type: "sources",
        label: "已找到参考来源",
        detail: documentCount ? `检索到 ${documentCount} 个知识库文档` : "未检索到明确来源",
        status: "completed"
      });
      setResponse((current) => ({
        ...(current || emptyStreamingResponse()),
        citations: sources
      }));
    } else if (type === "final") {
      const finalResponse = payload.response as ChatResponse | undefined;
      if (finalResponse) {
        setResponse(finalResponse);
        const finalSessionId = finalResponse.session_id || selectedSessionId;
        if (finalSessionId) {
          setSelectedSessionId(finalSessionId);
        }
        setChatMessages((current) => current.map((item) => item.id === pendingAiId ? {
          ...item,
          session_id: finalSessionId,
          content: finalResponse.answer,
          intent_category: finalResponse.intent.category,
          intent_subcategory: finalResponse.intent.subcategory,
          intent_confidence: finalResponse.intent.confidence,
          cache_hit_level: finalResponse.cache_hit_level,
          metadata_json: {
            citations: finalResponse.citations,
            task_type: finalResponse.task_type,
            run_id: finalResponse.run_id,
            trace_id: finalResponse.trace_id,
            tool_calls: finalResponse.tool_calls,
            steps: finalResponse.steps,
            intermediate_conclusions: finalResponse.intermediate_conclusions
          }
        } : item.session_id ? item : { ...item, session_id: finalSessionId }));
        void loadSessions(finalSessionId || null);
      }
    } else if (type === "error") {
      const message = String(payload.message || "流式问诊失败。");
      setError(message);
      appendProcessEvent({ type: "error", label: "问诊失败", detail: message, status: "failed" });
    }
  }

  function appendProcessEvent(event: Omit<StreamProcessEvent, "id">) {
    setProcessEvents((current) => [
      ...current,
      {
        ...event,
        id: typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `${event.type}-${Date.now()}-${Math.random()}`
      }
    ].filter((item, index, items) => {
      if (index === 0) {
        return true;
      }
      const previous = items[index - 1];
      return item.type !== previous.type || item.label !== previous.label || item.detail !== previous.detail;
    }).slice(-12));
  }

  const confidencePercent = useMemo(
    () => Math.round((response?.intent.confidence ?? 0) * 100),
    [response]
  );
  const selectedSession = sessions.find((item) => item.id === selectedSessionId);

  async function handleConsultationFiles(files: FileList | null) {
    if (!files?.length) {
      return;
    }
    const selected = await Promise.all(
      Array.from(files).slice(0, 4).map(async (file) => {
        const isReadableText =
          file.type.startsWith("text/") ||
          file.name.endsWith(".txt") ||
          file.name.endsWith(".md") ||
          file.name.endsWith(".csv") ||
          file.name.endsWith(".json");
        let content = "";
        if (isReadableText) {
          content = (await file.text()).slice(0, 12000);
        }
        return {
          file_name: file.name,
          file_type: file.type || "application/octet-stream",
          content
        };
      })
    );
    setAttachments(selected);
    setError(selected.some((item) => !item.content) ? "部分非文本文件仅提交文件名和类型；报告图片或文档后续可接对象存储或文字识别。" : "");
  }

  return (
    <section className="consultationLayout">
      <article className="panel aiHistoryPanel">
        <div className="panelHeader">
          <div>
            <h2>历史问诊</h2>
            <p>查看过往问诊对话，或开始新的 AI 问诊。</p>
          </div>
          <button className="iconButton" onClick={startNewSession} title="新建问诊" type="button">
            <MessageSquareText size={19} />
          </button>
        </div>
        <div className="miniList aiSessionList">
          {historyLoading && <p className="mutedText">正在加载历史问诊...</p>}
          {!historyLoading && sessions.map((session) => (
            <button
              className={`conversationTile ${selectedSessionId === session.id ? "active" : ""}`}
              key={session.id}
              onClick={() => {
                setSelectedSessionId(session.id);
                void loadSessionMessages(session.id);
              }}
              type="button"
            >
              <strong>{session.title || "未命名问诊"}</strong>
              <span>{session.summary || "暂无摘要"}</span>
              <small>{formatDateTime(session.updated_at || session.created_at)}</small>
            </button>
          ))}
          {!historyLoading && sessions.length === 0 && <p className="mutedText">暂无历史问诊。</p>}
        </div>
      </article>

      <article className="panel resultPanel aiChatPanel">
        <div className="panelHeader compact">
          <div>
            <h2>{selectedSession ? selectedSession.title || "智能问诊" : "新的智能问诊"}</h2>
            <p>{selectedSession ? "继续与 AI 讨论当前问诊。" : "输入问题后会创建一条新的问诊会话。"}</p>
          </div>
          <Stethoscope size={20} />
        </div>
        <div className="aiMessageList">
          {chatMessages.length ? chatMessages.map((item) => (
            <div className={`messageBubble ${item.sender === "user" ? "mine" : "aiBubble"}`} key={item.id}>
              <span>{item.sender === "user" ? "我" : "AI 问诊助手"} · {formatDateTime(item.created_at)}</span>
              {item.sender === "ai" ? <FormattedAnswer text={item.content} loading={loading && !item.content} /> : <p>{item.content}</p>}
            </div>
          )) : (
            <div className="emptyState compactEmpty">
              <MessageSquareText size={28} />
              <p>选择历史问诊或开始新的对话。</p>
            </div>
          )}
        </div>

        {response && (
          <>
            <ReferenceSources response={response} />
            <details className="collapsiblePanel streamProcess aiInsightPanel">
          <summary className="processHeader">
            <span>
              <Sparkles size={18} />
                <strong>{loading ? "AI 正在处理问诊" : "本轮 AI 调用流程"}</strong>
            </span>
            <ChevronDown size={18} />
          </summary>
            <div className="intentGrid">
              <div>
                <span>意图分类</span>
                <strong>{response.intent.category}</strong>
              </div>
              <div>
                <span>子分类</span>
                <strong>{response.intent.subcategory || "无"}</strong>
              </div>
              <div>
                <span>置信度</span>
                <strong>{confidencePercent}%</strong>
              </div>
              <div>
                <span>缓存</span>
                <strong>{response.cache_hit_level}</strong>
              </div>
            </div>
            <AiCallFlow response={response} processEvents={processEvents} loading={loading} />
          </details>
          </>
        )}

        <div className="aiComposer">
          <label className="fieldLabel" htmlFor="consultationInput">问诊内容</label>
          <textarea
            id="consultationInput"
            onChange={(event) => setMessage(event.target.value)}
            placeholder="继续描述症状、护理观察、用药疑问或检查摘要。"
            value={message}
          />
          <label className="uploadControl wideUpload" htmlFor="consultationFiles">
            <UploadCloud size={20} />
            <span>
              <strong>选择问诊文件</strong>
              <small>{attachments.length ? `已选择 ${attachments.length} 个文件` : "支持多选文本、检查摘要、护理记录"}</small>
            </span>
            <input id="consultationFiles" multiple onChange={(event) => void handleConsultationFiles(event.target.files)} type="file" />
          </label>
          <div className="attachmentList">
            {attachments.map((attachment) => (
              <span key={`${attachment.file_name}-${attachment.file_type}`}>
                {attachment.file_name} / {attachment.content ? `${attachment.content.length} 字` : "仅记录文件信息"}
              </span>
            ))}
          </div>
          <div className="buttonRow">
            <button className="primaryButton" disabled={loading || !message.trim()} onClick={submitConsultation}>
              {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
              <span>{loading ? "问诊中..." : selectedSessionId ? "继续发送" : "开始问诊"}</span>
            </button>
            <button
              className="secondaryButton"
              onClick={() => setMessage("护理人员如何预防术后长期卧床导致的压疮？")}
              type="button"
            >
              护理示例
            </button>
          </div>
        </div>
        {error && <p className="notice">{error}</p>}
      </article>
    </section>
  );

  function responseFromStoredMessage(messageItem: AiConversationMessage): ChatResponse {
    const metadata = asRecord(messageItem.metadata_json);
    const citations = Array.isArray(metadata.citations) ? metadata.citations as ChatResponse["citations"] : [];
    return {
      answer: messageItem.content,
      intent: {
        category: messageItem.intent_category || "medical_consult",
        subcategory: messageItem.intent_subcategory || "",
        confidence: messageItem.intent_confidence || 0
      },
      cache_hit_level: messageItem.cache_hit_level || "stored",
      citations,
      task_type: String(metadata.task_type || "knowledge_qa"),
      run_id: typeof metadata.run_id === "string" ? metadata.run_id : null,
      trace_id: typeof metadata.trace_id === "string" ? metadata.trace_id : null,
      session_id: messageItem.session_id || selectedSessionId,
      tool_calls: Array.isArray(metadata.tool_calls) ? metadata.tool_calls as Array<Record<string, unknown>> : [],
      steps: Array.isArray(metadata.steps) ? metadata.steps as Array<Record<string, unknown>> : [],
      intermediate_conclusions: Array.isArray(metadata.intermediate_conclusions)
        ? metadata.intermediate_conclusions as Array<Record<string, unknown>>
        : []
    };
  }
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "暂无时间";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

function emptyStreamingResponse(): ChatResponse {
  return {
    answer: "",
    intent: { category: "medical_consult", subcategory: "streaming", confidence: 0 },
    cache_hit_level: "streaming",
    citations: [],
    tool_calls: [],
    steps: [],
    intermediate_conclusions: []
  };
}

function parseSsePayload(rawEvent: string): Record<string, unknown> | null {
  const data = rawEvent
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n")
    .trim();
  if (!data) {
    return null;
  }
  try {
    const parsed = JSON.parse(data);
    return asRecord(parsed);
  } catch {
    return null;
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function ReferenceSources({ response }: { response: ChatResponse }) {
  const sources = collectCitationSources(response);

  return (
    <section className="referenceSourcesPanel" aria-label="参考知识库来源">
      <div className="referenceHeader">
        <span>
          <BookOpenCheck size={18} />
          <strong>参考知识库来源</strong>
        </span>
        <small>{sources.length ? `检索到 ${sources.length} 个文档` : "暂无明确来源"}</small>
      </div>
      {sources.length ? (
        <div className="citationList referenceCitationList">
          {sources.map((source, index) => (
            <div key={`${sourceTitle(source)}-${source.doc_id || ""}-${source.source || ""}-${index}`}>
              <strong>{sourceTitle(source)}</strong>
              <small>{sourceMeta(source)}</small>
              {source.source_url && <a href={source.source_url} rel="noreferrer" target="_blank">打开来源</a>}
            </div>
          ))}
        </div>
      ) : (
        <p className="mutedText referenceEmpty">本轮回复暂未返回明确的知识库文件来源。</p>
      )}
    </section>
  );
}

function collectCitationSources(response: ChatResponse): CitationSource[] {
  const candidates: CitationSource[] = [...(response.citations || [])];

  for (const step of response.steps || []) {
    const output = asRecord(step.output_data);
    candidates.push(...extractSourcesFromOutput(output));
  }

  for (const toolCall of response.tool_calls || []) {
    const output = asRecord(toolCall.output);
    candidates.push(...extractSourcesFromOutput(output));
  }

  return groupCitationDocuments(candidates.map(normalizeCitationSource)).slice(0, 12);
}

function groupCitationDocuments(sources: CitationSource[]): CitationSource[] {
  const grouped = new Map<string, CitationSource>();
  for (const source of sources) {
    const key = citationDocumentKey(source);
    const existing = grouped.get(key);
    if (existing) {
      existing.hit_count = (existing.hit_count || 1) + 1;
      if (!existing.source_url && source.source_url) {
        existing.source_url = source.source_url;
      }
      if (!existing.doc_id && source.doc_id) {
        existing.doc_id = source.doc_id;
      }
      continue;
    }
    grouped.set(key, {
      title: sourceTitle(source),
      doc: source.doc,
      source: source.source,
      source_url: source.source_url,
      doc_id: source.doc_id,
      hit_count: source.hit_count || 1
    });
  }
  return Array.from(grouped.values());
}

function citationDocumentKey(source: CitationSource) {
  return String(source.doc_id || source.doc || source.source || source.source_url || sourceTitle(source)).trim().toLowerCase();
}

function countCitationDocuments(sources: CitationSource[]) {
  return groupCitationDocuments(sources.map(normalizeCitationSource)).length;
}

function extractSourcesFromOutput(output: Record<string, unknown>): CitationSource[] {
  const sources = Array.isArray(output.sources) ? output.sources.map(asRecord) : [];
  const chunks = Array.isArray(output.chunks) ? output.chunks.map(asRecord) : [];
  const chunkSources = chunks.map((chunk) => {
    const metadata = asRecord(chunk.metadata);
    return {
      title: String(metadata.title || metadata.file_name || metadata.filename || metadata.source || "知识库文档"),
      doc: String(metadata.file_name || metadata.filename || metadata.title || metadata.source || ""),
      source: String(metadata.source || metadata.file_name || metadata.filename || ""),
      doc_id: metadata.doc_id as string | number | undefined,
      page: metadata.page_label as string | number | undefined || metadata.page as string | number | undefined,
      chunk_index: metadata.chunk_index as string | number | undefined,
      snippet: String(chunk.content || chunk.page_content || chunk.text || "")
    };
  });
  return [...sources, ...chunkSources];
}

function normalizeCitationSource(value: CitationSource | Record<string, unknown>): CitationSource {
  const source = asRecord(value);
  return {
    title: stringOrUndefined(source.title) || stringOrUndefined(source.doc) || stringOrUndefined(source.source),
    doc: stringOrUndefined(source.doc),
    source: stringOrUndefined(source.source),
    source_url: stringOrUndefined(source.source_url) || stringOrUndefined(source.url),
    doc_id: source.doc_id as string | number | undefined,
    snippet: stringOrUndefined(source.snippet) || stringOrUndefined(source.content),
    content: stringOrUndefined(source.content),
    page: source.page as string | number | undefined,
    chunk_index: source.chunk_index as string | number | undefined
  };
}

function stringOrUndefined(value: unknown) {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

function sourceTitle(source: CitationSource) {
  return source.title || source.doc || source.source || (source.doc_id ? `知识库文档 ${source.doc_id}` : "知识库文档");
}

function sourceMeta(source: CitationSource) {
  const parts = [];
  if (source.doc_id) {
    parts.push(`文档ID：${source.doc_id}`);
  }
  if (source.source && source.source !== sourceTitle(source)) {
    parts.push(source.source);
  }
  return parts.join(" / ") || "知识库检索来源";
}

function AiCallFlow({
  response,
  processEvents,
  loading
}: {
  response: ChatResponse;
  processEvents: StreamProcessEvent[];
  loading: boolean;
}) {
  const items = buildAiFlowItems(response, processEvents, loading);
  return (
    <div className="aiFlowSurface">
      <div className="aiRunMeta">
        <span>任务链路：{taskTypeLabel(response.task_type || "knowledge_qa")}</span>
        <span>运行：{response.run_id || "本地流式会话"}</span>
      </div>
      <div className="processTimeline aiCallTimeline">
        {items.map((event) => (
          <div className={`processEvent ${event.type} ${event.status}`} key={event.id}>
            <span>{flowIcon(event)}</span>
            <div>
              <strong>{event.label}</strong>
              {event.detail && <small>{event.detail}</small>}
            </div>
            <em>{flowStatusLabel(event.status)}</em>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildAiFlowItems(response: ChatResponse, processEvents: StreamProcessEvent[], loading: boolean): AiFlowItem[] {
  const liveItems = processEvents.map((event) => ({
    id: event.id,
    type: event.type,
    label: event.label,
    detail: event.detail,
    status: event.status || "completed"
  }));
  const derivedItems: AiFlowItem[] = [];

  (response.steps || []).forEach((step, index) => {
    const stepName = String(step.step_name || step.name || "unknown_step");
    const output = asRecord(step.output_data);
    derivedItems.push({
      id: `step-${index}-${stepName}`,
      type: stepName.includes("search") ? "tool" : "status",
      label: stepLabel(stepName),
      detail: summarizeStep(stepName, output),
      status: String(step.status || "completed")
    });
  });

  (response.tool_calls || []).forEach((toolCall, index) => {
    const toolName = String(toolCall.tool_name || "tool");
    derivedItems.push({
      id: `tool-${index}-${toolName}`,
      type: "tool",
      label: toolLabel(toolName),
      detail: summarizeToolCall(toolCall),
      status: String(toolCall.status || "completed")
    });
  });

  if (response.citations?.length) {
    const documentCount = countCitationDocuments(response.citations);
    derivedItems.push({
      id: "sources-final",
      type: "sources",
      label: "参考来源",
      detail: documentCount ? `${documentCount} 个知识库文档参与回答` : "未检索到明确来源",
      status: "completed"
    });
  }

  const items = liveItems.length ? [...liveItems, ...derivedItems] : derivedItems;
  const deduped = dedupeFlowItems(items);
  if (deduped.length) {
    return deduped;
  }
  return [{
    id: "waiting",
    type: "status",
    label: loading ? "等待 AI 服务响应" : "暂无可展示调用流程",
    detail: loading ? "正在连接问诊服务并准备接收流式事件" : "新的问诊开始后会显示实时调用步骤",
    status: loading ? "running" : "pending"
  }];
}

function dedupeFlowItems(items: AiFlowItem[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = `${item.type}:${item.label}:${item.detail}:${item.status}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  }).slice(-18);
}

function flowIcon(event: AiFlowItem) {
  if (event.status === "running") {
    return <Loader2 className="spin" size={15} />;
  }
  if (event.type === "tool") {
    return <Database size={15} />;
  }
  if (event.type === "sources") {
    return <Search size={15} />;
  }
  if (event.type === "error") {
    return <Activity size={15} />;
  }
  return <CheckCircle2 size={15} />;
}

function flowStatusLabel(status: string) {
  const labels: Record<string, string> = {
    running: "进行中",
    completed: "完成",
    success: "完成",
    failed: "失败",
    pending: "等待"
  };
  return labels[status] || statusLabel(status);
}

function stepLabel(stepName: string) {
  const labels: Record<string, string> = {
    memory_read: "读取历史对话",
    intent_recognition: "识别问诊意图",
    question_classification: "判断问题类型",
    question_rewrite: "改写检索问题",
    knowledge_search: "调用知识库检索",
    result_evaluation: "评估检索结果",
    answer_generation: "生成问诊回复",
    memory_write: "保存对话记忆",
    clarification: "判断是否需要追问"
  };
  return labels[stepName] || stepName.replaceAll("_", " ");
}

function taskTypeLabel(taskType: string) {
  const labels: Record<string, string> = {
    knowledge_qa: "知识库问答",
    reasoning: "医学推理",
    chitchat: "基础对话",
    admin_copilot: "管理助手",
    knowledge_inspection: "知识巡检"
  };
  return labels[taskType] || taskType;
}

function summarizeStep(stepName: string, output: Record<string, unknown>) {
  if (stepName === "memory_read") {
    return output.has_history ? "已读取当前问诊的上下文历史" : "当前会话暂无可用历史";
  }
  if (stepName === "question_rewrite") {
    return String(output.rewritten_question || "已完成检索问题整理");
  }
  if (stepName === "knowledge_search") {
    const documents = countCitationDocuments(extractSourcesFromOutput(output));
    return documents ? `检索到 ${documents} 个候选文档` : "未检索到候选文档";
  }
  if (stepName === "result_evaluation") {
    return output.is_sufficient === false ? "检索依据不足，后续回答会保守处理" : "检索依据通过评估";
  }
  if (stepName === "answer_generation") {
    return "已汇总上下文、知识库文档和问诊问题生成回复";
  }
  return "步骤已执行";
}

function FormattedAnswer({ text, loading }: { text: string; loading: boolean }) {
  const blocks = text.trim().split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  if (!blocks.length) {
    return <p className="answerText mutedText">{loading ? "正在组织问诊回复..." : "暂无回答内容。"}</p>;
  }
  return (
    <div className="answerText">
      {blocks.map((block, index) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const isBulletList = lines.length > 1 && lines.every((line) => /^[-*•]/.test(line));
        const isNumberedList = lines.length > 1 && lines.every((line) => /^\d+[.、]/.test(line));
        if (isBulletList) {
          return (
            <ul key={`${block}-${index}`}>
              {lines.map((line, lineIndex) => <li key={`${line}-${lineIndex}`}>{line.replace(/^[-*•]\s*/, "")}</li>)}
            </ul>
          );
        }
        if (isNumberedList) {
          return (
            <ol key={`${block}-${index}`}>
              {lines.map((line, lineIndex) => <li key={`${line}-${lineIndex}`}>{line.replace(/^\d+[.、]\s*/, "")}</li>)}
            </ol>
          );
        }
        return <p key={`${block}-${index}`}>{block}</p>;
      })}
    </div>
  );
}

function toolLabel(toolName: string) {
  const labels: Record<string, string> = {
    question_rewrite: "问题改写",
    knowledge_search: "知识库检索",
    rerank: "证据重排",
    conversation_memory_read: "读取对话记忆",
    conversation_memory_write: "写入对话记忆",
    doc_summary: "文档摘要",
    ocr_extract: "OCR 识别",
    answer_generation: "生成回答"
  };
  return labels[toolName] || toolName.replaceAll("_", " ");
}

function summarizeToolCall(toolCall: Record<string, unknown>) {
  const status = String(toolCall.status || "completed");
  const duration = typeof toolCall.duration_ms === "number" ? `，耗时 ${Math.round(toolCall.duration_ms)}ms` : "";
  const output = asRecord(toolCall.output);
  const count = Array.isArray(output.results) ? `，返回 ${output.results.length} 条结果` : "";
  return `${statusLabel(status)}${count}${duration}`;
}

function Jobs({ account, onOpenChat }: { account: AccountRead; onOpenChat: () => void }) {
  const [jobRows, setJobRows] = useState<JobPosting[]>([]);
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [caregivers, setCaregivers] = useState<AvailableCaregiver[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [jobForm, setJobForm] = useState({
    employer_id: "",
    title: "术后陪护护理",
    city: "上海",
    patient_gender: "女",
    patient_age: 68,
    patient_height_cm: 165,
    patient_weight_kg: 60,
    disease_type: "骨科术后",
    care_type: "术后护理",
    care_level: "日间陪护",
    location: "浦东新区",
    address_detail: "医院住院部 8 楼",
    salary_amount: 480,
    salary_unit: "天",
    care_start_date: "",
    care_end_date: "",
    care_start_time: "08:00",
    care_end_time: "18:00",
    budget_cents: 48000,
    description: "需要日间恢复观察和日常护理支持。",
    special_requirements: "需要有协助行动经验。"
  });
  const [applicationForm, setApplicationForm] = useState({ caregiver_id: "", cover_letter: "" });
  const [invitationForm, setInvitationForm] = useState({ patient_id: "", caregiver_id: "", message: "" });

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function refreshJobs() {
    setLoading(true);
    setNotice("");
    try {
      const [jobResult, caregiverResult, invitationResult] = await Promise.all([
        requestJson<JobPosting[]>("/api/v1/jobs?status=published"),
        requestJson<AvailableCaregiver[]>("/api/v1/jobs/caregivers/available"),
        requestJson<Invitation[]>("/api/v1/jobs/invitations")
      ]);
      setJobRows(jobResult);
      setCaregivers(caregiverResult);
      setInvitations(invitationResult);
      setSelectedJobId((current) => current || jobResult[0]?.id || "");
    } catch {
      setJobRows(
        jobs.map((job, index) => ({
          id: `demo-${index}`,
          employer_id: "demo-patient",
          title: job.title,
          city: job.city,
          care_type: "demo",
          care_level: job.status,
          location: job.patient,
          budget_cents: Number.parseInt(job.budget, 10) * 100 || 0,
          status: job.status.toLowerCase(),
          special_requirements: "",
          description: job.patient
        }))
      );
      setCaregivers([]);
      setInvitations([]);
      setNotice("由于后端接口暂不可达，当前显示演示数据。");
    } finally {
      setLoading(false);
    }
  }

  async function loadApplications(jobId = selectedJobId) {
    if (!jobId) {
      return;
    }
    try {
      setApplications(await requestJson<JobApplication[]>(`/api/v1/jobs/${jobId}/applications`));
      setSelectedJobId(jobId);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载应聘记录失败。");
    }
  }

  async function createJob() {
    setLoading(true);
    setNotice("");
    try {
      const salaryCents = Math.max(0, Number(jobForm.salary_amount) || 0) * 100;
      const patientDescription = [
        `病人性别：${jobForm.patient_gender || "未填写"}`,
        `年龄：${jobForm.patient_age || "未填写"} 岁`,
        `身高：${jobForm.patient_height_cm || "未填写"} cm`,
        `体重：${jobForm.patient_weight_kg || "未填写"} kg`,
        `病症/护理类型：${jobForm.disease_type || "未填写"} / ${jobForm.care_type || "未填写"}`,
        `地点：${jobForm.city || "未填写"} ${jobForm.location || ""} ${jobForm.address_detail || ""}`.trim(),
        `护理时间：${jobForm.care_start_date || "未填写"} 至 ${jobForm.care_end_date || "未填写"}，${jobForm.care_start_time || "未填写"} - ${jobForm.care_end_time || "未填写"}`,
        `薪资酬劳：${jobForm.salary_amount || 0} 元/${jobForm.salary_unit || "次"}`,
        `补充说明：${jobForm.description || "无"}`
      ].join("\n");
      const created = await requestJson<JobPosting>("/api/v1/jobs", {
        method: "POST",
        body: JSON.stringify({
          ...jobForm,
          location: `${jobForm.location} ${jobForm.address_detail}`.trim(),
          budget_cents: salaryCents,
          salary: {
            unit: jobForm.salary_unit,
            amount_cents: salaryCents,
            amount_yuan: Number(jobForm.salary_amount) || 0
          },
          schedule: {
            start_date: jobForm.care_start_date,
            end_date: jobForm.care_end_date,
            start_time: jobForm.care_start_time,
            end_time: jobForm.care_end_time
          },
          description: patientDescription,
          special_requirements: [
            `病人资料：${jobForm.patient_gender}，${jobForm.patient_age} 岁，${jobForm.patient_height_cm} cm，${jobForm.patient_weight_kg} kg`,
            `护理要求：${jobForm.special_requirements || "无"}`
          ].join("\n")
        })
      });
      setNotice(`招聘已发布：${created.title}`);
      await refreshJobs();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "发布招聘失败。");
    } finally {
      setLoading(false);
    }
  }

  async function applyForJob() {
    if (!selectedJobId || !applicationForm.caregiver_id.trim()) {
      setNotice("请选择招聘并填写护理方用户编号。");
      return;
    }
    try {
      const application = await requestJson<JobApplication>(`/api/v1/jobs/${selectedJobId}/applications`, {
        method: "POST",
        body: JSON.stringify(applicationForm)
      });
      setNotice(`应聘已提交：${application.id}`);
      await loadApplications(selectedJobId);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "提交应聘失败。");
    }
  }

  async function reviewApplication(applicationId: string, statusValue: "accepted" | "rejected") {
    try {
      const result = await requestJson<MatchResult>(`/api/v1/jobs/applications/${applicationId}/review`, {
        method: "POST",
        body: JSON.stringify({ status: statusValue })
      });
      setNotice(
        result.conversation
          ? `应聘已${statusValue === "accepted" ? "通过" : "拒绝"}；已创建会话：${result.conversation.id}`
          : `应聘已${statusValue === "accepted" ? "通过" : "拒绝"}。`
      );
      await Promise.all([refreshJobs(), loadApplications(selectedJobId)]);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "处理应聘失败。");
    }
  }

  async function createInvitation() {
    if (!invitationForm.patient_id.trim() || !invitationForm.caregiver_id.trim()) {
      setNotice("请填写病人和护理方用户编号 后再发送邀请。");
      return;
    }
    try {
      const invitation = await requestJson<Invitation>("/api/v1/jobs/invitations", {
        method: "POST",
        body: JSON.stringify({ ...invitationForm, job_id: selectedJobId || null })
      });
      setNotice(`邀请已发送：${invitation.id}`);
      await refreshJobs();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "发送邀请失败。");
    }
  }

  async function respondInvitation(invitationId: string, statusValue: "accepted" | "rejected") {
    try {
      const result = await requestJson<MatchResult>(`/api/v1/jobs/invitations/${invitationId}/respond`, {
        method: "POST",
        body: JSON.stringify({ status: statusValue })
      });
      setNotice(
        result.conversation
          ? `邀请已${statusValue === "accepted" ? "接受" : "拒绝"}；已创建会话：${result.conversation.id}`
          : `邀请已${statusValue === "accepted" ? "接受" : "拒绝"}。`
      );
      await refreshJobs();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "处理邀请失败。");
    }
  }

  async function openConversation(participantId: string, sourceType: string, sourceId?: string | null) {
    if (!participantId || participantId === account.id) {
      setNotice("请选择另一方用户后再发起沟通。");
      return;
    }
    try {
      const conversation = await requestJson<CareConversation>("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify({
          participant_a: account.id,
          participant_b: participantId,
          source_type: sourceType,
          source_id: sourceId || null,
          title: "招聘沟通"
        })
      });
      setNotice(`已创建沟通会话：${conversation.title || conversation.id}`);
      onOpenChat();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建沟通会话失败。");
    }
  }

  useEffect(() => {
    void refreshJobs();
  }, []);

  return (
    <section className="jobsLayout">
      <article className="panel wide">
        <div className="panelHeader">
          <div>
            <h2>招聘页面</h2>
            <p>病人方发布的护理招聘信息会在这里展示，护理方可以提交应聘，病人也可以主动邀请护理人员。</p>
          </div>
          <button className="iconButton" onClick={refreshJobs} title="刷新招聘" type="button">
            {loading ? <Loader2 className="spin" size={19} /> : <RefreshCw size={19} />}
          </button>
        </div>
        {notice && <p className="notice">{notice}</p>}
        <div className="tableLike">
          {jobRows.map((job) => (
            <article className={`rowCard selectable ${selectedJobId === job.id ? "selected" : ""}`} key={job.id}>
              <button className="rowSelect" onClick={() => void loadApplications(job.id)} type="button">
                <div>
                  <strong>{job.title}</strong>
                  <span>{job.city || "未填写城市"} / {job.location || job.description || "未填写地点"}</span>
                </div>
                <div>
                  <span>预算</span>
                  <strong>{Math.round(job.budget_cents / 100)} 元</strong>
                </div>
                <div>
                  <span>护理类型</span>
                  <strong>{job.care_type || job.care_level || "通用护理"}</strong>
                </div>
                <span className="pill">{statusLabel(job.status)}</span>
              </button>
              {job.employer_id !== account.id && (
                <button className="rowActionButton" onClick={() => void openConversation(job.employer_id, "job", job.id)} type="button">
                  沟通
                </button>
              )}
            </article>
          ))}
        </div>
      </article>

      <article className="panel">
        <div className="panelHeader compact">
          <h2>发布招聘</h2>
          <BriefcaseMedical size={20} />
        </div>
        <div className="formGrid jobPublishForm">
          <input placeholder="病人用户编号" value={jobForm.employer_id} onChange={(event) => setJobForm({ ...jobForm, employer_id: event.target.value })} />
          <input placeholder="招聘标题" value={jobForm.title} onChange={(event) => setJobForm({ ...jobForm, title: event.target.value })} />
          <select value={jobForm.patient_gender} onChange={(event) => setJobForm({ ...jobForm, patient_gender: event.target.value })}>
            <option value="女">病人性别：女</option>
            <option value="男">病人性别：男</option>
            <option value="其他">病人性别：其他</option>
          </select>
          <input type="number" min="0" placeholder="病人年龄" value={jobForm.patient_age} onChange={(event) => setJobForm({ ...jobForm, patient_age: Number(event.target.value) })} />
          <input type="number" min="0" placeholder="身高（厘米）" value={jobForm.patient_height_cm} onChange={(event) => setJobForm({ ...jobForm, patient_height_cm: Number(event.target.value) })} />
          <input type="number" min="0" placeholder="体重（公斤）" value={jobForm.patient_weight_kg} onChange={(event) => setJobForm({ ...jobForm, patient_weight_kg: Number(event.target.value) })} />
          <input placeholder="病症类型" value={jobForm.disease_type} onChange={(event) => setJobForm({ ...jobForm, disease_type: event.target.value })} />
          <input placeholder="护理类型" value={jobForm.care_type} onChange={(event) => setJobForm({ ...jobForm, care_type: event.target.value })} />
          <input placeholder="城市" value={jobForm.city} onChange={(event) => setJobForm({ ...jobForm, city: event.target.value })} />
          <input placeholder="位置区域" value={jobForm.location} onChange={(event) => setJobForm({ ...jobForm, location: event.target.value })} />
          <input placeholder="详细地点" value={jobForm.address_detail} onChange={(event) => setJobForm({ ...jobForm, address_detail: event.target.value })} />
          <input type="number" min="0" placeholder="薪资酬劳（元）" value={jobForm.salary_amount} onChange={(event) => setJobForm({ ...jobForm, salary_amount: Number(event.target.value), budget_cents: Number(event.target.value) * 100 })} />
          <select value={jobForm.salary_unit} onChange={(event) => setJobForm({ ...jobForm, salary_unit: event.target.value })}>
            <option value="小时">按小时</option>
            <option value="天">按天</option>
            <option value="周">按周</option>
            <option value="月">按月</option>
          </select>
          <input type="date" value={jobForm.care_start_date} onChange={(event) => setJobForm({ ...jobForm, care_start_date: event.target.value })} />
          <input type="date" value={jobForm.care_end_date} onChange={(event) => setJobForm({ ...jobForm, care_end_date: event.target.value })} />
          <input type="time" value={jobForm.care_start_time} onChange={(event) => setJobForm({ ...jobForm, care_start_time: event.target.value })} />
          <input type="time" value={jobForm.care_end_time} onChange={(event) => setJobForm({ ...jobForm, care_end_time: event.target.value })} />
        </div>
        <textarea placeholder="补充护理说明" value={jobForm.description} onChange={(event) => setJobForm({ ...jobForm, description: event.target.value })} />
        <textarea placeholder="特殊要求" value={jobForm.special_requirements} onChange={(event) => setJobForm({ ...jobForm, special_requirements: event.target.value })} />
        <button className="primaryButton" disabled={loading || !jobForm.employer_id.trim()} onClick={createJob} type="button">
          <Send size={18} />
          <span>发布</span>
        </button>
      </article>

      <article className="panel">
        <div className="panelHeader compact">
          <h2>应聘记录</h2>
          <ClipboardList size={20} />
        </div>
        <div className="formGrid">
          <input placeholder="护理方用户编号" value={applicationForm.caregiver_id} onChange={(event) => setApplicationForm({ ...applicationForm, caregiver_id: event.target.value })} />
          <input placeholder="应聘说明" value={applicationForm.cover_letter} onChange={(event) => setApplicationForm({ ...applicationForm, cover_letter: event.target.value })} />
        </div>
        <div className="buttonRow">
          <button className="secondaryButton" onClick={applyForJob} type="button">应聘</button>
          <button className="secondaryButton" onClick={() => void loadApplications()} type="button">加载</button>
        </div>
        <div className="miniList">
          {applications.map((application) => (
            <div className="miniItem" key={application.id}>
              <div>
                <strong>{application.caregiver_id}</strong>
                <span>{application.cover_letter || "暂无应聘说明"} / {statusLabel(application.status)}</span>
              </div>
              <div className="inlineActions">
                <button title="沟通" onClick={() => void openConversation(application.caregiver_id, "application", application.id)} type="button"><MessageSquareText size={17} /></button>
                <button title="通过" onClick={() => void reviewApplication(application.id, "accepted")} type="button"><CheckCircle2 size={17} /></button>
                <button title="拒绝" onClick={() => void reviewApplication(application.id, "rejected")} type="button"><ShieldCheck size={17} /></button>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="panel wide">
        <div className="panelHeader compact">
          <h2>邀请护理方</h2>
          <Handshake size={20} />
        </div>
        <div className="caregiverGrid">
          {caregivers.map((caregiver) => (
            <button
              className="caregiverTile"
              key={caregiver.user_id}
              onClick={() => setInvitationForm({ ...invitationForm, caregiver_id: caregiver.user_id })}
              type="button"
            >
              <strong>{caregiver.real_name || caregiver.user_id}</strong>
              <span>{caregiver.service_city || "不限城市"} / {caregiver.experience_years} 年经验 / {caregiver.rating_avg.toFixed(1)}</span>
              <small>{caregiver.bio || "可接单护理方"}</small>
            </button>
          ))}
        </div>
        <div className="formGrid inviteForm">
          <input placeholder="病人用户编号" value={invitationForm.patient_id} onChange={(event) => setInvitationForm({ ...invitationForm, patient_id: event.target.value })} />
          <input placeholder="护理方用户编号" value={invitationForm.caregiver_id} onChange={(event) => setInvitationForm({ ...invitationForm, caregiver_id: event.target.value })} />
          <input placeholder="邀请说明" value={invitationForm.message} onChange={(event) => setInvitationForm({ ...invitationForm, message: event.target.value })} />
          <button className="primaryButton compactButton" onClick={createInvitation} type="button">
            <Send size={18} />
            <span>邀请</span>
          </button>
        </div>
        <div className="miniList">
          {invitations.map((invitation) => (
            <div className="miniItem" key={invitation.id}>
              <div>
                <strong>{invitation.patient_id} → {invitation.caregiver_id}</strong>
                <span>{invitation.message || "暂无说明"} / {statusLabel(invitation.status)}</span>
              </div>
              <div className="inlineActions">
                <button title="沟通" onClick={() => void openConversation(invitation.caregiver_id, "invitation", invitation.id)} type="button"><MessageSquareText size={17} /></button>
                <button title="接受" onClick={() => void respondInvitation(invitation.id, "accepted")} type="button"><CheckCircle2 size={17} /></button>
                <button title="拒绝" onClick={() => void respondInvitation(invitation.id, "rejected")} type="button"><ShieldCheck size={17} /></button>
              </div>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function Profiles({ account, onOpenChat }: { account: AccountRead; onOpenChat: () => void }) {
  const [patientId, setPatientId] = useState("");
  const [caregiverId, setCaregiverId] = useState("");
  const [patient, setPatient] = useState<PatientHomepage | null>(null);
  const [caregiver, setCaregiver] = useState<CaregiverResume | null>(null);
  const [caregiverList, setCaregiverList] = useState<CaregiverResume[]>([]);
  const [cityFilter, setCityFilter] = useState("");
  const [availableOnly, setAvailableOnly] = useState(true);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [reviewForm, setReviewForm] = useState({
    conversation_id: "",
    reviewer_id: "",
    reviewee_id: "",
    score: 5,
    tags: "准时, 细心",
    comment: "服务可靠，沟通清晰。"
  });
  const [conversationReviews, setConversationReviews] = useState<ServiceReview[]>([]);

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function loadPatient() {
    if (!patientId.trim()) {
      setNotice("请输入病人用户编号。");
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      setPatient(await requestJson<PatientHomepage>(`/api/v1/profiles/patients/${patientId.trim()}`));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载病人主页失败。");
    } finally {
      setLoading(false);
    }
  }

  async function loadCaregiver(targetId = caregiverId) {
    if (!targetId.trim()) {
      setNotice("请输入护理方用户编号。");
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      const result = await requestJson<CaregiverResume>(`/api/v1/profiles/caregivers/${targetId.trim()}`);
      setCaregiver(result);
      setCaregiverId(result.user_id);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载护理主页失败。");
    } finally {
      setLoading(false);
    }
  }

  async function loadCaregiverList() {
    setLoading(true);
    setNotice("");
    const params = new URLSearchParams();
    params.set("available_only", String(availableOnly));
    if (cityFilter.trim()) {
      params.set("city", cityFilter.trim());
    }
    try {
      setCaregiverList(await requestJson<CaregiverResume[]>(`/api/v1/profiles/caregivers?${params.toString()}`));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载护理方列表失败。");
    } finally {
      setLoading(false);
    }
  }

  async function toggleAvailability() {
    if (!caregiver) {
      return;
    }
    try {
      const result = await requestJson<CaregiverResume>(`/api/v1/profiles/caregivers/${caregiver.user_id}/availability`, {
        method: "PATCH",
        body: JSON.stringify({ is_available: !caregiver.is_available })
      });
      setCaregiver(result);
      setNotice(`接单状态已更新：${result.is_available ? "可接单" : "服务中"}`);
      await loadCaregiverList();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "更新接单状态失败。");
    }
  }

  async function submitReview() {
    if (!reviewForm.conversation_id.trim() || !reviewForm.reviewer_id.trim() || !reviewForm.reviewee_id.trim()) {
      setNotice("请填写会话、评价人和被评价人 ID 后再提交评价。");
      return;
    }
    try {
      const review = await requestJson<ServiceReview>("/api/v1/reviews", {
        method: "POST",
        body: JSON.stringify({
          ...reviewForm,
          score: Number(reviewForm.score),
          tags: reviewForm.tags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean)
        })
      });
      setNotice(`评价已提交：${review.score}/5`);
      await loadConversationReviews(review.conversation_id);
      if (patient?.user_id === review.reviewee_id) {
        await loadPatient();
      }
      if (caregiver?.user_id === review.reviewee_id) {
        await loadCaregiver(review.reviewee_id);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "提交评价失败。");
    }
  }

  async function loadConversationReviews(conversationId = reviewForm.conversation_id) {
    if (!conversationId.trim()) {
      setNotice("请输入会话编号 后再加载评价。");
      return;
    }
    try {
      setConversationReviews(await requestJson<ServiceReview[]>(`/api/v1/reviews/conversations/${conversationId.trim()}`));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载会话评价失败。");
    }
  }

  async function openConversation(participantId: string) {
    if (!participantId || participantId === account.id) {
      setNotice("请选择另一方用户后再发起沟通。");
      return;
    }
    try {
      const conversation = await requestJson<CareConversation>("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify({
          participant_a: account.id,
          participant_b: participantId,
          source_type: "profile",
          source_id: null,
          title: "护理资料沟通"
        })
      });
      setNotice(`已创建沟通会话：${conversation.title || conversation.id}`);
      onOpenChat();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建沟通会话失败。");
    }
  }

  useEffect(() => {
    void loadCaregiverList();
  }, []);

  return (
    <section className="profilesLayout">
      <article className="panel profileHero">
        <div className="panelHeader">
          <div>
            <h2>用户信息：病人主页</h2>
            <p>展示病人实名状态、公开病例摘要、历史招聘和他人评价。</p>
          </div>
          <FileHeart size={22} />
        </div>
        <div className="formGrid profileSearch">
          <input placeholder="病人用户编号" value={patientId} onChange={(event) => setPatientId(event.target.value)} />
          <button className="primaryButton compactButton" onClick={loadPatient} type="button">
            {loading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            <span>加载</span>
          </button>
        </div>
        {patient ? (
          <div className="profileSurface">
            <div className="profileHeaderLine">
              <div className="profileAvatar">{(patient.real_name || patient.display_name || "P").slice(0, 1)}</div>
              <div>
                <strong>{patient.real_name || patient.display_name || patient.user_id}</strong>
                <span>{patient.id_verified ? "已认证病人" : statusLabel(patient.verification_status)}</span>
              </div>
            </div>
            <div className="profileFacts">
              <div>
                <span>评分</span>
                <strong>{patient.rating_avg.toFixed(1)}</strong>
              </div>
              <div>
                <span>评价数</span>
                <strong>{patient.review_count}</strong>
              </div>
              {Object.entries(patient.basic_info).slice(0, 4).map(([key, value]) => (
                <div key={key}>
                  <span>{key}</span>
                  <strong>{String(value)}</strong>
                </div>
              ))}
            </div>
            {Object.keys(patient.basic_info).length === 0 && <p className="mutedText">暂无公开基础信息。</p>}
            <h3>近期评价</h3>
            <div className="miniList">
              {patient.recent_reviews.map((review) => (
                <div className="miniItem" key={review.id}>
                  <div>
                    <strong>{review.score}/5 from {review.reviewer_id}</strong>
                    <span>{review.comment || "暂无评价内容"}</span>
                  </div>
                </div>
              ))}
              {patient.recent_reviews.length === 0 && <p className="mutedText">暂无收到的评价。</p>}
            </div>
            <h3>公开病例摘要</h3>
            <div className="miniList">
              {patient.public_cases.map((item) => (
                <div className="miniItem" key={item.id}>
                  <div>
                    <strong>{item.public_summary || item.summary || "病例摘要"}</strong>
                    <span>{statusLabel(item.visibility)}</span>
                  </div>
                </div>
              ))}
              {patient.public_cases.length === 0 && <p className="mutedText">暂无公开病例摘要。</p>}
            </div>
            <h3>招聘记录</h3>
            <div className="miniList">
              {patient.job_history.map((job) => (
                <div className="miniItem" key={job.id}>
                  <div>
                    <strong>{job.title}</strong>
                    <span>{job.city || "未填写城市"} / {statusLabel(job.status)} / {Math.round(job.budget_cents / 100)} 元</span>
                  </div>
                </div>
              ))}
              {patient.job_history.length === 0 && <p className="mutedText">暂无护理招聘记录。</p>}
            </div>
          </div>
        ) : (
          <div className="emptyState compactEmpty">
            <FileHeart size={26} />
            <p>输入病人用户编号 后可查看公开主页资料。</p>
          </div>
        )}
      </article>

      <article className="panel profileHero">
        <div className="panelHeader">
          <div>
            <h2>用户信息：护理主页</h2>
            <p>展示护理资料、接单状态、认证证书、评分和近期服务评价。</p>
          </div>
          <IdCard size={22} />
        </div>
        <div className="formGrid profileSearch">
          <input placeholder="护理方用户编号" value={caregiverId} onChange={(event) => setCaregiverId(event.target.value)} />
          <button className="primaryButton compactButton" onClick={() => void loadCaregiver()} type="button">
            {loading ? <Loader2 className="spin" size={18} /> : <Search size={18} />}
            <span>加载</span>
          </button>
        </div>
        {caregiver ? (
          <div className="profileSurface">
            <div className="profileHeaderLine">
              <div className="profileAvatar caregiverAvatar">{(caregiver.real_name || caregiver.display_name || "C").slice(0, 1)}</div>
              <div>
                <strong>{caregiver.real_name || caregiver.display_name || caregiver.user_id}</strong>
                <span>{caregiver.service_city || "不限城市"} / {caregiver.experience_years} 年经验</span>
              </div>
              <button className="secondaryButton availabilityButton" onClick={toggleAvailability} type="button">
                {caregiver.is_available ? "可接单" : "服务中"}
              </button>
              {caregiver.user_id !== account.id && (
                <button className="secondaryButton availabilityButton" onClick={() => void openConversation(caregiver.user_id)} type="button">
                  沟通
                </button>
              )}
            </div>
            <p className="profileBio">{caregiver.bio || "暂无护理简介。"}</p>
            <div className="profileFacts">
              <div>
                <span>评分</span>
                <strong>{caregiver.rating_avg.toFixed(1)}</strong>
              </div>
              <div>
                <span>评价数</span>
                <strong>{caregiver.review_count}</strong>
              </div>
              <div>
                <span>审核状态</span>
                <strong>{caregiver.id_verified ? "已认证" : statusLabel(caregiver.verification_status)}</strong>
              </div>
            </div>
            <h3>已通过证书</h3>
            <div className="miniList">
              {caregiver.certifications.map((certification) => (
                <div className="miniItem" key={certification.id}>
                  <div>
                    <strong>{certification.certificate_type}</strong>
                    <span>{certification.description || statusLabel(certification.review_status)}</span>
                  </div>
                </div>
              ))}
              {caregiver.certifications.length === 0 && <p className="mutedText">暂无已通过证书。</p>}
            </div>
            <h3>近期评价</h3>
            <div className="miniList">
              {caregiver.recent_reviews.map((review) => (
                <div className="miniItem" key={review.id}>
                  <div>
                    <strong>{review.score}/5 from {review.reviewer_id}</strong>
                    <span>{review.comment || "暂无评价内容"}</span>
                  </div>
                </div>
              ))}
              {caregiver.recent_reviews.length === 0 && <p className="mutedText">暂无服务评价。</p>}
            </div>
          </div>
        ) : (
          <div className="emptyState compactEmpty">
            <IdCard size={26} />
            <p>输入护理方用户编号 后可查看主页资料。</p>
          </div>
        )}
      </article>

      <article className="panel wide profileDirectory">
        <div className="panelHeader compact">
          <h2>应聘发布页面</h2>
          <button className="iconButton" onClick={loadCaregiverList} title="刷新护理方资料" type="button">
            {loading ? <Loader2 className="spin" size={19} /> : <RefreshCw size={19} />}
          </button>
        </div>
        {notice && <p className="notice">{notice}</p>}
        <div className="formGrid directoryFilters">
          <input placeholder="城市筛选" value={cityFilter} onChange={(event) => setCityFilter(event.target.value)} />
          <label className="checkLine">
            <input checked={availableOnly} onChange={(event) => setAvailableOnly(event.target.checked)} type="checkbox" />
            <span>只看可接单</span>
          </label>
        </div>
        <div className="caregiverGrid">
          {caregiverList.map((item) => (
            <button className="caregiverTile" key={item.user_id} onClick={() => void loadCaregiver(item.user_id)} type="button">
              <strong>{item.real_name || item.display_name || item.user_id}</strong>
              <span>{item.service_city || "不限城市"} / {item.experience_years} 年经验 / {item.rating_avg.toFixed(1)}</span>
              <small>{item.is_available ? "当前可接单" : "服务中"} / {item.bio || "暂无简介"}</small>
            </button>
          ))}
          {caregiverList.length === 0 && <p className="mutedText">暂无符合条件的护理方发布信息。</p>}
        </div>
      </article>

      <article className="panel wide reviewWorkbench">
        <div className="panelHeader compact">
          <h2>护理评分接口</h2>
          <CheckCircle2 size={20} />
        </div>
        <div className="formGrid reviewForm">
          <input placeholder="会话编号" value={reviewForm.conversation_id} onChange={(event) => setReviewForm({ ...reviewForm, conversation_id: event.target.value })} />
          <input placeholder="评价人用户编号" value={reviewForm.reviewer_id} onChange={(event) => setReviewForm({ ...reviewForm, reviewer_id: event.target.value })} />
          <input placeholder="被评价人用户编号" value={reviewForm.reviewee_id} onChange={(event) => setReviewForm({ ...reviewForm, reviewee_id: event.target.value })} />
          <input type="number" min="1" max="5" placeholder="评分" value={reviewForm.score} onChange={(event) => setReviewForm({ ...reviewForm, score: Number(event.target.value) })} />
          <input placeholder="标签，逗号分隔" value={reviewForm.tags} onChange={(event) => setReviewForm({ ...reviewForm, tags: event.target.value })} />
          <input placeholder="评价内容" value={reviewForm.comment} onChange={(event) => setReviewForm({ ...reviewForm, comment: event.target.value })} />
        </div>
        <div className="buttonRow">
          <button className="primaryButton" onClick={submitReview} type="button">
            <Send size={18} />
            <span>提交评价</span>
          </button>
          <button className="secondaryButton" onClick={() => void loadConversationReviews()} type="button">
            加载会话评价
          </button>
        </div>
        <div className="miniList">
          {conversationReviews.map((review) => (
            <div className="miniItem" key={review.id}>
              <div>
                <strong>{review.score}/5 {review.reviewer_id} → {review.reviewee_id}</strong>
                <span>{review.comment || "暂无评价内容"} / {review.tags.join(", ") || "暂无标签"}</span>
              </div>
            </div>
          ))}
          {conversationReviews.length === 0 && <p className="mutedText">加载已匹配会话后，可查看双方评价。</p>}
        </div>
      </article>
    </section>
  );
}

function CareChat({ account }: { account: AccountRead }) {
  const [conversations, setConversations] = useState<CareConversation[]>([]);
  const [messages, setMessages] = useState<CareMessage[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState("");
  const [messageBody, setMessageBody] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function loadConversations() {
    setLoading(true);
    setNotice("");
    try {
      const rows = await requestJson<CareConversation[]>(`/api/v1/conversations?user_id=${encodeURIComponent(account.id)}`);
      setConversations(rows);
      const nextId = selectedConversationId || rows[0]?.id || "";
      setSelectedConversationId(nextId);
      if (nextId) {
        await loadMessages(nextId);
      } else {
        setMessages([]);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载会话失败。");
    } finally {
      setLoading(false);
    }
  }

  async function loadMessages(conversationId: string) {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    try {
      setSelectedConversationId(conversationId);
      setMessages(
        await requestJson<CareMessage[]>(
          `/api/v1/conversations/${conversationId}/messages?user_id=${encodeURIComponent(account.id)}`
        )
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载消息失败。");
    }
  }

  async function sendMessage() {
    if (!selectedConversationId || !messageBody.trim()) {
      return;
    }
    try {
      await requestJson<CareMessage>(`/api/v1/conversations/${selectedConversationId}/messages`, {
        method: "POST",
        body: JSON.stringify({
          sender_id: account.id,
          body: messageBody.trim()
        })
      });
      setMessageBody("");
      await loadMessages(selectedConversationId);
      await loadConversations();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "发送消息失败。");
    }
  }

  useEffect(() => {
    void loadConversations();
  }, [account.id]);

  return (
    <section className="chatLayout">
      <article className="panel conversationPanel">
        <div className="panelHeader compact">
          <h2>我的会话</h2>
          <button className="iconButton" onClick={loadConversations} title="刷新会话" type="button">
            {loading ? <Loader2 className="spin" size={19} /> : <RefreshCw size={19} />}
          </button>
        </div>
        {notice && <p className="notice">{notice}</p>}
        <div className="miniList">
          {conversations.map((conversation) => (
            <button
              className={`conversationTile ${selectedConversationId === conversation.id ? "active" : ""}`}
              key={conversation.id}
              onClick={() => void loadMessages(conversation.id)}
              type="button"
            >
              <strong>{conversation.title || "护理沟通"}</strong>
              <span>{sourceTypeLabel(conversation.source_type)} / {conversation.updated_at || conversation.created_at || "暂无时间"}</span>
            </button>
          ))}
          {conversations.length === 0 && <p className="mutedText">暂无会话，可在招聘或应聘发布页面点击“沟通”创建。</p>}
        </div>
      </article>

      <article className="panel chatPanel">
        <div className="panelHeader compact">
          <h2>聊天窗口</h2>
          <MessageSquareText size={20} />
        </div>
        <div className="messageList">
          {messages.map((message) => (
            <div className={`messageBubble ${message.sender_id === account.id ? "mine" : ""}`} key={message.id}>
              <span>{message.sender_id === account.id ? "我" : message.sender_id}</span>
              <p>{message.body || message.content}</p>
            </div>
          ))}
          {messages.length === 0 && <p className="mutedText">选择会话后开始沟通。</p>}
        </div>
        <div className="chatComposer">
          <textarea
            placeholder="输入沟通内容"
            value={messageBody}
            onChange={(event) => setMessageBody(event.target.value)}
          />
          <button className="primaryButton" disabled={!selectedConversationId || !messageBody.trim()} onClick={sendMessage} type="button">
            <Send size={18} />
            <span>发送</span>
          </button>
        </div>
      </article>
    </section>
  );
}

function Verification() {
  const [summary, setSummary] = useState<AdminSummary | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [certifications, setCertifications] = useState<AdminCertification[]>([]);
  const [modelConfigs, setModelConfigs] = useState<AdminAiModelConfig[]>([]);
  const [logs, setLogs] = useState<AdminLog[]>([]);
  const [notice, setNotice] = useState("");
  const [userKeyword, setUserKeyword] = useState("");
  const [modelForm, setModelForm] = useState({
    provider: "deepseek",
    model_name: "deepseek-chat",
    base_url: "https://api.deepseek.com",
    api_key_ref: "LLM_API_KEY",
    temperature: 0.3,
    max_tokens: 2048
  });

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function refreshAdmin() {
    try {
      const params = userKeyword.trim() ? `?keyword=${encodeURIComponent(userKeyword.trim())}` : "";
      const [summaryResult, usersResult, certResult, configResult, logResult] = await Promise.all([
        requestJson<AdminSummary>("/api/v1/admin/summary"),
        requestJson<AdminUser[]>(`/api/v1/admin/users${params}`),
        requestJson<AdminCertification[]>("/api/v1/admin/certifications?status=pending"),
        requestJson<AdminAiModelConfig[]>("/api/v1/admin/ai-model-configs"),
        requestJson<AdminLog[]>("/api/v1/admin/logs?limit=20")
      ]);
      setSummary(summaryResult);
      setUsers(usersResult);
      setCertifications(certResult);
      setModelConfigs(configResult);
      setLogs(logResult);
      setNotice("");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载审核管理数据失败。");
    }
  }

  async function updateUserStatus(userId: string, statusValue: "active" | "disabled" | "suspended") {
    try {
      await requestJson<AdminUser>(`/api/v1/admin/users/${userId}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: statusValue, reason: "管理员后台更新" })
      });
      setNotice(`用户状态已更新：${statusValue}`);
      await refreshAdmin();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "更新用户状态失败。");
    }
  }

  async function reviewCertification(certificationId: string, review_status: "approved" | "rejected") {
    try {
      await requestJson<AdminCertification>(`/api/v1/admin/certifications/${certificationId}/review`, {
        method: "POST",
        body: JSON.stringify({ review_status, review_note: `管理员标记为 ${review_status}` })
      });
      setNotice(`证书已${review_status === "approved" ? "通过" : "拒绝"}。`);
      await refreshAdmin();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "审核证书失败。");
    }
  }

  async function createModelConfig() {
    try {
      await requestJson<AdminAiModelConfig>("/api/v1/admin/ai-model-configs", {
        method: "POST",
        body: JSON.stringify({ ...modelForm, is_active: false, parameters: {} })
      });
      setNotice("智能模型配置已创建。");
      await refreshAdmin();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "创建 智能模型配置失败。");
    }
  }

  async function activateModelConfig(configId: string) {
    try {
      await requestJson<AdminAiModelConfig>(`/api/v1/admin/ai-model-configs/${configId}/activate`, {
        method: "POST"
      });
      setNotice("智能模型配置已启用。");
      await refreshAdmin();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "启用 智能模型配置失败。");
    }
  }

  async function deleteModelConfig(configId: string) {
    try {
      await requestJson<void>(`/api/v1/admin/ai-model-configs/${configId}`, {
        method: "DELETE"
      });
      setNotice("智能模型配置已删除。");
      await refreshAdmin();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "删除智能模型配置失败。");
    }
  }

  useEffect(() => {
    void refreshAdmin();
  }, []);

  return (
    <section className="dashboardGrid">
      <article className="panel wide">
        <div className="panelHeader">
          <div>
            <h2>审核管理总览</h2>
            <p>用于处理用户状态、护理证书审核、智能模型配置和操作记录。</p>
          </div>
          <ShieldCheck size={22} />
        </div>
        {notice && <p className="notice">{notice}</p>}
        <div className="adminMetricGrid">
          {summary ? (
            Object.entries(summary).map(([key, value]) => (
              <div className="adminMetric" key={key}>
                <span>{key.replaceAll("_", " ")}</span>
                <strong>{value}</strong>
              </div>
            ))
          ) : (
            <p className="mutedText">正在加载审核管理数据...</p>
          )}
        </div>
      </article>

      <article className="panel">
        <div className="panelHeader compact">
          <h2>操作区</h2>
          <button className="iconButton" onClick={refreshAdmin} title="刷新审核管理数据" type="button">
            <RefreshCw size={19} />
          </button>
        </div>
        <div className="formGrid">
          <input placeholder="搜索用户" value={userKeyword} onChange={(event) => setUserKeyword(event.target.value)} />
          <button className="secondaryButton compactButton" onClick={refreshAdmin} type="button">搜索</button>
        </div>
        <ul className="eventList">
          <li>证书审核会写入管理员操作日志</li>
          <li>智能模型启用后仅保留一个有效配置</li>
          <li>审核结果会触发短信通知记录</li>
        </ul>
      </article>

      <article className="panel wide adminSection">
        <div className="panelHeader compact">
          <h2>用户管理</h2>
          <UserCheck size={20} />
        </div>
        <div className="miniList">
          {users.map((user) => (
            <div className="miniItem" key={user.id}>
              <div>
                <strong>{user.display_name || user.phone}</strong>
                <span>{user.phone} / {statusLabel(user.active_role)} / {statusLabel(user.status)}</span>
              </div>
              <div className="inlineActions">
                <button title="启用" onClick={() => void updateUserStatus(user.id, "active")} type="button"><CheckCircle2 size={17} /></button>
                <button title="暂停" onClick={() => void updateUserStatus(user.id, "suspended")} type="button"><ShieldCheck size={17} /></button>
              </div>
            </div>
          ))}
          {users.length === 0 && <p className="mutedText">暂无符合条件的用户。</p>}
        </div>
      </article>

      <article className="panel adminSection">
        <div className="panelHeader compact">
          <h2>证书审核队列</h2>
          <CheckCircle2 size={20} />
        </div>
        <div className="miniList">
          {certifications.map((certification) => (
            <div className="miniItem" key={certification.id}>
              <div>
                <strong>{certification.caregiver_name || certification.caregiver_user_id}</strong>
                <span>{certification.certificate_type} / {certification.description || statusLabel(certification.review_status)}</span>
              </div>
              <div className="inlineActions">
                <button title="通过" onClick={() => void reviewCertification(certification.id, "approved")} type="button"><CheckCircle2 size={17} /></button>
                <button title="拒绝" onClick={() => void reviewCertification(certification.id, "rejected")} type="button"><ShieldCheck size={17} /></button>
              </div>
            </div>
          ))}
          {certifications.length === 0 && <p className="mutedText">暂无待审核证书。</p>}
        </div>
      </article>

      <article className="panel adminSection">
        <div className="panelHeader compact">
          <h2>智能模型配置</h2>
          <Settings size={20} />
        </div>
        <div className="formGrid">
          <input placeholder="服务提供方" value={modelForm.provider} onChange={(event) => setModelForm({ ...modelForm, provider: event.target.value })} />
          <input placeholder="模型名称" value={modelForm.model_name} onChange={(event) => setModelForm({ ...modelForm, model_name: event.target.value })} />
          <input placeholder="接口地址" value={modelForm.base_url} onChange={(event) => setModelForm({ ...modelForm, base_url: event.target.value })} />
          <input type="number" step="0.1" placeholder="温度参数" value={modelForm.temperature} onChange={(event) => setModelForm({ ...modelForm, temperature: Number(event.target.value) })} />
        </div>
        <button className="primaryButton compactButton" onClick={createModelConfig} type="button">
          <Send size={18} />
          <span>新增配置</span>
        </button>
        <div className="miniList">
          {modelConfigs.map((config) => (
            <div className="miniItem" key={config.id}>
              <div>
                <strong>{config.provider} / {config.model_name}</strong>
                <span>{config.base_url} / 温度 {config.temperature}</span>
              </div>
              <div className="inlineActions">
                <button title="启用模型" onClick={() => void activateModelConfig(config.id)} type="button">
                  <CheckCircle2 size={17} />
                </button>
                <button disabled={config.is_active} title={config.is_active ? "启用中的模型不可删除" : "删除模型"} onClick={() => void deleteModelConfig(config.id)} type="button">
                  <Trash2 size={17} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </article>

      <article className="panel wide adminSection">
        <div className="panelHeader compact">
          <h2>操作日志</h2>
          <ClipboardList size={20} />
        </div>
        <div className="miniList">
          {logs.map((log) => (
            <div className="miniItem" key={log.id}>
              <div>
                <strong>{log.action}</strong>
                <span>{log.target_type} / {log.target || log.target_id} / {log.created_at || "暂无时间"}</span>
              </div>
            </div>
          ))}
          {logs.length === 0 && <p className="mutedText">暂无管理员操作日志。</p>}
        </div>
      </article>
    </section>
  );
}

function Knowledge() {
  const [knowledgeForm, setKnowledgeForm] = useState({
    collection: defaultKnowledgeCollection,
    title: "",
    content: "",
    file_name: "",
    file_type: "",
    file_content_base64: ""
  });
  const [uploadedKnowledge, setUploadedKnowledge] = useState<AdminKnowledgeItem[]>([]);
  const [recentUploadedKnowledge, setRecentUploadedKnowledge] = useState<AdminKnowledgeItem[]>([]);
  const [recentUploadPage, setRecentUploadPage] = useState(1);
  const [allKnowledgePage, setAllKnowledgePage] = useState(1);
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || `接口返回 ${response.status}`);
    }
    return response.json() as Promise<T>;
  }

  async function loadKnowledgeItems() {
    try {
      const rows = await requestJson<AdminKnowledgeItem[]>("/api/v1/admin/knowledge-items?limit=100");
      setUploadedKnowledge(rows);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载知识库失败。");
    }
  }

  useEffect(() => {
    void loadKnowledgeItems();
  }, []);

  const recentUploadPageCount = Math.max(1, Math.ceil(recentUploadedKnowledge.length / recentKnowledgePageSize));
  const allKnowledgePageCount = Math.max(1, Math.ceil(uploadedKnowledge.length / allKnowledgePageSize));
  const pagedRecentUploads = recentUploadedKnowledge.slice(
    (recentUploadPage - 1) * recentKnowledgePageSize,
    recentUploadPage * recentKnowledgePageSize
  );
  const pagedAllKnowledge = uploadedKnowledge.slice(
    (allKnowledgePage - 1) * allKnowledgePageSize,
    allKnowledgePage * allKnowledgePageSize
  );

  useEffect(() => {
    setRecentUploadPage((page) => Math.min(page, recentUploadPageCount));
  }, [recentUploadPageCount]);

  useEffect(() => {
    setAllKnowledgePage((page) => Math.min(page, allKnowledgePageCount));
  }, [allKnowledgePageCount]);

  useEffect(() => {
    const hasPending = uploadedKnowledge.some((item) => ["pending", "indexing"].includes(item.rag_status));
    if (!hasPending) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadKnowledgeItems();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [uploadedKnowledge]);

  function readFileAsBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const result = String(reader.result || "");
        resolve(result.includes(",") ? result.split(",")[1] : result);
      };
      reader.onerror = () => reject(reader.error || new Error("文件读取失败。"));
      reader.readAsDataURL(file);
    });
  }

  async function handleKnowledgeFile(files: FileList | null) {
    if (!files?.length) {
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      const selectedFiles = await Promise.all(
        Array.from(files).map(async (file) => {
          const isReadableText =
            file.type.startsWith("text/") ||
            file.name.endsWith(".txt") ||
            file.name.endsWith(".md") ||
            file.name.endsWith(".csv") ||
            file.name.endsWith(".json");
          const [content, fileContentBase64] = await Promise.all([
            isReadableText ? file.text() : Promise.resolve(""),
            readFileAsBase64(file)
          ]);
          return {
            title: file.name.replace(/\.[^.]+$/, ""),
            content: content.slice(0, 20000),
            file_name: file.name,
            file_type: file.type || "未知类型",
            file_content_base64: fileContentBase64
          };
        })
      );
      setKnowledgeForm({
        ...knowledgeForm,
        title: "",
        content: "",
        file_name: selectedFiles.map((file) => file.file_name).join(", "),
        file_type: selectedFiles.length === 1 ? selectedFiles[0].file_type : `${selectedFiles.length} 个文件`,
        file_content_base64: ""
      });
      const createdItems: AdminKnowledgeItem[] = [];
      for (const file of selectedFiles) {
        const created = await requestJson<AdminKnowledgeItem>("/api/v1/admin/knowledge-items", {
          method: "POST",
          body: JSON.stringify({
            collection: defaultKnowledgeCollection,
            title: file.title,
            content: file.content,
            file_name: file.file_name,
            file_type: file.file_type,
            file_content_base64: file.file_content_base64
          })
        });
        createdItems.push(created);
      }
      const latestCreatedItems = [...createdItems].reverse();
      setUploadedKnowledge((current) => [...latestCreatedItems, ...current]);
      setRecentUploadedKnowledge((current) => [...latestCreatedItems, ...current]);
      setRecentUploadPage(1);
      setAllKnowledgePage(1);
      setKnowledgeForm({
        collection: defaultKnowledgeCollection,
        title: "",
        content: "",
        file_name: "",
        file_type: "",
        file_content_base64: ""
      });
      setNotice(`已提交 ${createdItems.length} 个后台解析任务。解析完成后会自动显示片段数量。`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "上传知识失败。");
    } finally {
      setLoading(false);
    }
  }

  async function deleteKnowledgeItem(itemId: string) {
    setNotice("");
    try {
      const response = await fetch(`/api/v1/admin/knowledge-items/${itemId}`, { method: "DELETE" });
      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `接口返回 ${response.status}`);
      }
      setUploadedKnowledge((current) => current.filter((item) => item.id !== itemId));
      setRecentUploadedKnowledge((current) => current.filter((item) => item.id !== itemId));
      setNotice("知识已从平台和 RAG 知识库删除。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "删除知识失败。");
    }
  }

  function knowledgeFileMeta(item: AdminKnowledgeItem) {
    return [
      item.file_name || "未命名文件",
      knowledgeStatusLabel(item.rag_status),
      `${item.rag_chunk_count} 个片段`,
      formatDateTime(item.created_at)
    ].join(" / ");
  }

  function renderKnowledgeItem(item: AdminKnowledgeItem) {
    return (
      <div className="miniItem" key={item.id}>
        <div>
          <strong>{item.title || item.file_name || "未命名知识文件"}</strong>
          <span>{knowledgeFileMeta(item)}</span>
        </div>
        <div className="inlineActions">
          <button title="删除知识" onClick={() => void deleteKnowledgeItem(item.id)} type="button">
            <Trash2 size={17} />
          </button>
        </div>
      </div>
    );
  }

  function renderPager(page: number, totalPages: number, onPageChange: (page: number) => void) {
    return (
      <div className="pager knowledgePager">
        <button disabled={page <= 1} onClick={() => onPageChange(page - 1)} type="button">上一页</button>
        <span>{page} / {totalPages}</span>
        <button disabled={page >= totalPages} onClick={() => onPageChange(page + 1)} type="button">下一页</button>
      </div>
    );
  }

  return (
    <section className="knowledgeLayout">
      <div className="knowledgeMainColumn">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <h2>知识库上传</h2>
              <p>上传后统一进入知识库后台解析，不再按文件类型拆分入口。</p>
            </div>
            <Database size={22} />
          </div>
          {notice && <p className="notice">{notice}</p>}
          <div className="knowledgeUploadControls">
            <label className={`uploadControl uploadButtonControl ${loading ? "disabled" : ""}`} htmlFor="knowledgeFileUpload">
              {loading ? <Loader2 className="spin" size={20} /> : <UploadCloud size={20} />}
              <span>
                <strong>{loading ? "提交中..." : "上传知识库文件"}</strong>
                <small>{knowledgeForm.file_name || "支持单个或多个文件"}</small>
              </span>
              <input disabled={loading} id="knowledgeFileUpload" multiple onChange={(event) => void handleKnowledgeFile(event.target.files)} type="file" />
            </label>
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader compact">
            <div>
              <h2>已上传知识库文件</h2>
              <p>展示平台内所有已上传文件，每页 5 个。</p>
            </div>
            <button className="iconButton" onClick={() => void loadKnowledgeItems()} title="刷新知识库上传状态" type="button">
              <RefreshCw size={19} />
            </button>
          </div>
          <div className="miniList">
            {pagedAllKnowledge.map(renderKnowledgeItem)}
            {uploadedKnowledge.length === 0 && <p className="mutedText">暂无已上传知识库文件。</p>}
          </div>
          {uploadedKnowledge.length > allKnowledgePageSize && renderPager(allKnowledgePage, allKnowledgePageCount, setAllKnowledgePage)}
        </article>
      </div>

      <article className="panel knowledgeRecentPanel">
        <div className="panelHeader compact">
          <div>
            <h2>本次上传记录</h2>
            <p>展示本轮页面操作上传的文件，每页 3 个。</p>
          </div>
          <ClipboardList size={20} />
        </div>
        <div className="miniList">
          {pagedRecentUploads.map(renderKnowledgeItem)}
          {recentUploadedKnowledge.length === 0 && <p className="mutedText">暂无本次上传记录。</p>}
        </div>
        {recentUploadedKnowledge.length > recentKnowledgePageSize && renderPager(recentUploadPage, recentUploadPageCount, setRecentUploadPage)}
      </article>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);


