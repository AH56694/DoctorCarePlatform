import WorkspaceShell from "./features/workspace/WorkspaceShell";
import AccountsIdentity from "./features/accounts/AccountsPage";
import Jobs from "./features/jobs/JobsPage";
import Consultation, { formatDateTime } from "./features/consultation/ConsultationPage";
import { roleLabel, statusLabel } from "./lib/presentation";
import { StrictMode, type ReactNode, useState } from "react";
import { createRoot } from "react-dom/client";
import { useCallback } from "react";
import { useEffect } from "react";
import { BadgeCheck, Bell, BookOpenCheck, BriefcaseMedical, CheckCircle2, ClipboardList, Database, FileHeart, Handshake, HeartPulse, IdCard, LayoutDashboard, Loader2, LogOut, MessageSquareText, RefreshCw, Search, Send, Settings, ShieldCheck, Trash2, UploadCloud, UserCheck, UserPlus } from "lucide-react";
import "./styles.css";
import OverviewPage from "./features/overview/OverviewPage";

import type { View, PatientHomepage, CaregiverResume, ServiceReview, AdminSummary, AdminUser, AdminCertification, AdminAiModelConfig, AdminLog, AdminKnowledgeItem, RoleName, AccountRead, AuthResponse, CareConversation, CareMessage } from "./types";
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

import { apiFetch } from "./lib/api";
import { loadCurrentSession, saveCurrentSession, clearCurrentSession, sessionExpiredEvent } from "./lib/session";

async function fetchAccountIdentity(userId: string): Promise<AccountRead> {
  const response = await apiFetch(`/api/v1/accounts/${encodeURIComponent(userId)}/identity`);
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
    const expire = () => {
      setAccountState(null);
      setActiveView("overview");
    };
    window.addEventListener(sessionExpiredEvent, expire);
    return () => window.removeEventListener(sessionExpiredEvent, expire);
  }, []);

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
        clearCurrentSession();
        setAccountState(null);
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

  if (activeView === "overview") {
    return <OverviewPage
      displayName={account.display_name || account.phone}
      roleLabel={isAdmin ? "平台管理" : roleLabel(account.active_role)}
      isAdmin={isAdmin}
      onNavigate={setActiveView}
      onLogout={logout}
    />;
  }

  if (activeView === "accounts" || activeView === "jobs" || activeView === "consultation") {
    const pageMeta = {
      accounts: ["我的信息", "完善身份资料，安心开启每一次照护。"],
      jobs: ["护理招聘", "清晰发布照护需求，找到合适的护理伙伴。"],
      consultation: ["智能问诊", "整理问题与护理记录，让每次咨询更清晰。"],
    }[activeView];
    return <WorkspaceShell displayName={account.display_name || account.phone} roleLabel={isAdmin ? "平台管理" : roleLabel(account.active_role)} isAdmin={isAdmin} activeView={activeView} onNavigate={setActiveView} onLogout={logout}>
      <div className="care-heading"><h1>{pageMeta[0]}</h1><p>{pageMeta[1]}</p></div>
      {activeView === "accounts" && <AccountsIdentity account={account} setAccount={setAccount} />}
      {activeView === "jobs" && <Jobs account={account} onOpenChat={() => setActiveView("chat")} />}
      {activeView === "consultation" && <Consultation account={account} />}
      <footer className="ov-footer">DoctorCarePlatform · 医护陪护服务平台</footer>
    </WorkspaceShell>;
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

        {activeView === "profiles" && <Profiles account={account} onOpenChat={() => setActiveView("chat")} />}
        {activeView === "chat" && <CareChat account={account} />}
        {activeView === "verification" && isAdmin && <Verification />}
        {activeView === "knowledge" && isAdmin && <Knowledge />}
      </section>
    </main>
  );
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
  return account.roles.some((role) => role.role === "admin");
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
    const response = await apiFetch(path, {
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
    const response = await apiFetch(path, {
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
      const params = new URLSearchParams({ viewer_id: account.id });
      const result = await requestJson<CaregiverResume>(
        `/api/v1/profiles/caregivers/${targetId.trim()}?${params.toString()}`
      );
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
    const response = await apiFetch(path, {
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
    const response = await apiFetch(path, {
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
    const response = await apiFetch(path, {
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
      const response = await apiFetch(`/api/v1/admin/knowledge-items/${itemId}`, { method: "DELETE" });
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


