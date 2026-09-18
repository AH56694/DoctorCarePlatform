import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight, Bell, BookOpen, BriefcaseMedical, CalendarDays, HeartPulse, Home, IdCard, LogOut, Menu, MessageSquareText, ShieldCheck, Stethoscope, UserRound, X } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { View } from "../../types";
import "../overview/overview.css";
import "./care-pages.css";

type WorkspaceProps = {
  displayName: string; roleLabel: string; isAdmin: boolean;
  activeView?: View; dateLabel?: string; children: ReactNode;
  onNavigate: (view: View) => void; onLogout: () => void;
};
const navigation: { view: View; label: string; icon: LucideIcon; adminOnly?: boolean }[] = [
  { view: "overview", label: "流程总览", icon: Home },
  { view: "accounts", label: "我的信息", icon: UserRound },
  { view: "jobs", label: "招聘页面", icon: BriefcaseMedical },
  { view: "profiles", label: "应聘发布", icon: IdCard },
  { view: "chat", label: "聊天沟通", icon: MessageSquareText },
  { view: "consultation", label: "智能问诊", icon: Stethoscope },
  { view: "verification", label: "审核管理", icon: ShieldCheck, adminOnly: true },
  { view: "knowledge", label: "知识库", icon: BookOpen, adminOnly: true },
];


export default function WorkspaceShell({displayName, roleLabel, isAdmin, activeView = "overview", dateLabel, children, onNavigate, onLogout}: WorkspaceProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [noticesOpen, setNoticesOpen] = useState(false);
  const menuButton = useRef<HTMLButtonElement>(null);
  const sidebar = useRef<HTMLElement>(null);
  const noticeRegion = useRef<HTMLDivElement>(null);
  const date = dateLabel ?? new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "long", day: "numeric",
  }).format(new Date());

  useEffect(() => {
    const desktop = window.matchMedia("(min-width: 761px)");
    const closeMobileMenu = () => { if (desktop.matches) setMenuOpen(false); };
    desktop.addEventListener("change", closeMobileMenu);
    return () => desktop.removeEventListener("change", closeMobileMenu);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const links = sidebar.current?.querySelectorAll<HTMLButtonElement>("button");
    links?.[0]?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButton.current?.focus();
      }
      if (event.key === "Tab" && links?.length) {
        const first = links[0], last = links[links.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    };
    document.addEventListener("keydown", keydown);
    return () => document.removeEventListener("keydown", keydown);
  }, [menuOpen]);

  useEffect(() => {
    if (!noticesOpen) return;
    const outside = (event: PointerEvent) => {
      if (!noticeRegion.current?.contains(event.target as Node)) setNoticesOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNoticesOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
    };
  }, [noticesOpen]);

  const navigate = (view: View) => {
    setMenuOpen(false);
    onNavigate(view);
  };
  return (
    <div className={`overviewPage${activeView === "overview" ? "" : " care-workspace"}`}>
      <a className="ov-skip" href="#workspace-content">跳到主要内容</a>
      {menuOpen && <button className="ov-overlay" aria-label="关闭导航遮罩" tabIndex={-1} onClick={() => setMenuOpen(false)} />}
      <aside id="overview-navigation" ref={sidebar} className={`ov-sidebar${menuOpen ? " is-open" : ""}`} role={menuOpen ? "dialog" : undefined} aria-modal={menuOpen || undefined} aria-label="工作台导航">
        <button className="ov-mobile-close ov-icon-button" aria-label="关闭导航" onClick={() => { setMenuOpen(false); menuButton.current?.focus(); }} type="button"><X size={22} /></button>
        <div className="ov-brand">
          <div className="ov-brand-mark"><HeartPulse size={34} strokeWidth={1.65} aria-hidden="true" /></div>
          <strong>DoctorCare<span>Platform</span></strong>
          <p>医护陪护服务平台</p>
        </div>
        <nav className="ov-navigation" aria-label="主导航">
          {navigation.filter((item) => !item.adminOnly).map(({ view, label, icon: Icon }) => (
            <button key={view} className={`ov-nav-item${view === activeView ? " is-active" : ""}`} aria-current={view === activeView ? "page" : undefined} type="button" data-view={view} onClick={() => navigate(view)}>
              <Icon size={21} strokeWidth={1.7} aria-hidden="true" /><span>{label}</span>
            </button>
          ))}
          {isAdmin && <>
            <p className="ov-nav-caption">平台管理</p>
            {navigation.filter((item) => item.adminOnly).map(({ view, label, icon: Icon }) => (
              <button key={view} className="ov-nav-item" type="button" data-view={view} onClick={() => navigate(view)}><Icon size={21} strokeWidth={1.7} aria-hidden="true" /><span>{label}</span></button>
            ))}
          </>}
        </nav>
        <div className="ov-user-area">
          <button className="ov-user-card" onClick={() => navigate("accounts")} type="button" data-view="accounts" aria-label={`查看${displayName}的个人信息`}>
            <span className="ov-avatar"><UserRound size={23} strokeWidth={1.65} aria-hidden="true" /></span>
            <span className="ov-user-copy"><strong>{displayName}</strong><small>{roleLabel}</small></span>
          </button>
          <button className="ov-icon-button ov-logout" aria-label="退出登录" title="退出登录" type="button" data-action="logout" onClick={onLogout}><LogOut size={19} /></button>
        </div>
      </aside>

      <div className="ov-workspace" inert={menuOpen || undefined}>
        <header className="ov-topbar">
          <div className="ov-breadcrumb">
            <button ref={menuButton} className="ov-icon-button ov-menu" aria-label="打开导航" aria-controls="overview-navigation" aria-expanded={menuOpen} type="button" onClick={() => setMenuOpen(true)}><Menu size={23} /></button>
            <span>工作台</span><span className="ov-breadcrumb-divider">/</span><strong>{navigation.find(item => item.view === activeView)?.label}</strong>
          </div>
          <div className="ov-topbar-actions">
            <time className="ov-date"><CalendarDays size={17} aria-hidden="true" />{date}</time>
            <div className="ov-notice-region" ref={noticeRegion}>
              <button className="ov-icon-button" aria-label="查看工作台提醒" aria-expanded={noticesOpen} aria-controls="overview-notices" type="button" onClick={() => setNoticesOpen(!noticesOpen)}><Bell size={20} strokeWidth={1.65} /></button>
              {noticesOpen && <div className="ov-notices" id="overview-notices" role="status"><strong>总览提醒</strong><p>{activeView === "overview" ? "当前总览展示示例数据。请前往具体业务页面查看实际进度。" : "可前往聊天沟通和个人信息页查看消息与资料进度。"}</p><button className="ov-text-link" type="button" data-view={isAdmin ? "verification" : "accounts"} onClick={() => navigate(isAdmin ? "verification" : "accounts")}>查看{isAdmin ? "审核管理" : "我的信息"}<ArrowRight size={15} /></button></div>}
            </div>
            <button className="ov-avatar ov-header-avatar" aria-label="查看我的信息" type="button" data-view="accounts" onClick={() => navigate("accounts")}><UserRound size={20} strokeWidth={1.65} /></button>
          </div>
        </header>

        <main className="ov-main" id="workspace-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
