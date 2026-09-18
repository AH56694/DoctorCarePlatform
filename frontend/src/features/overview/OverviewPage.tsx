import { useState } from "react";
import { ArrowRight, BedDouble, Bell, BookOpen, BriefcaseMedical, ChevronRight, FileCheck2, Home, Info, MessageSquareText, Moon, ShieldCheck, Stethoscope, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { View } from "../../types";
import WorkspaceShell from "../workspace/WorkspaceShell";

type OverviewProps = {
  displayName: string;
  roleLabel: string;
  isAdmin: boolean;
  onNavigate: (view: View) => void;
  onLogout: () => void;
  /** The HTML export embeds this same page with illustrative data. */
  preview?: boolean;
  illustrationUrl?: string;
  dateLabel?: string;
};

const exampleMetrics: { label: string; value: string; detail: string; icon: LucideIcon; tone: string }[] = [
  { label: "智能问诊次数", value: "1,284", detail: "本周增长 18.6%", icon: Stethoscope, tone: "green" },
  { label: "护理招聘", value: "326", detail: "72 条等待匹配", icon: BriefcaseMedical, tone: "green" },
  { label: "审核队列", value: "41", detail: "12 条待优先处理", icon: ShieldCheck, tone: "blue" },
  { label: "待处理提醒", value: "8", detail: "及时关注平台动态", icon: Bell, tone: "amber" },
];

const exampleJobs = [
  { title: "术后陪护护理", detail: "髋部术后恢复期", city: "上海", price: 480, status: "匹配中", tone: "green", icon: BedDouble },
  { title: "夜间病房陪护", detail: "夜间陪护与生活协助", city: "杭州", price: 360, status: "沟通中", tone: "blue", icon: Moon },
  { title: "居家康复协助", detail: "日常起居与康复陪伴", city: "苏州", price: 520, status: "已发布", tone: "neutral", icon: Home },
];
const filters = ["全部", "匹配中", "沟通中"] as const;

export default function OverviewPage({
  displayName, roleLabel, isAdmin, onNavigate, onLogout, preview = false,
  illustrationUrl = "/images/overview-care-illustration.png",
  dateLabel,
}: OverviewProps) {
  const [filter, setFilter] = useState<string>("全部");
  const navigate = onNavigate;
  const visibleJobs = exampleJobs.filter((job) => filter === "全部" || job.status === filter);
  const tasks: { title: string; detail: string; icon: LucideIcon; view: View }[] = isAdmin ? [
    { title: "护理资质审核", detail: "12 项待处理", icon: FileCheck2, view: "verification" },
    { title: "身份资料核验", detail: "6 项待处理", icon: UserRound, view: "verification" },
    { title: "知识内容更新", detail: "3 项待处理", icon: BookOpen, view: "knowledge" },
  ] : [
    { title: "完善身份资料", detail: "查看资料与审核状态", icon: UserRound, view: "accounts" },
    { title: "查看护理机会", detail: "发现适合的照护服务", icon: BriefcaseMedical, view: "jobs" },
    { title: "继续服务沟通", detail: "查看已有的沟通会话", icon: MessageSquareText, view: "chat" },
  ];

  return (
    <WorkspaceShell displayName={displayName} roleLabel={roleLabel} isAdmin={isAdmin} dateLabel={dateLabel} onNavigate={onNavigate} onLogout={onLogout}>
          <div className="ov-page-heading">
            <div><p className="ov-eyebrow">OVERVIEW</p><h1>流程总览</h1><p className="ov-description">快速了解平台动态，安排今天的照护工作。</p></div>
            <span className="ov-preview-badge" title="本页统计、招聘和待办数量均为示例，不代表实时业务数据。"><Info size={13} aria-hidden="true" />{preview ? "设计预览 · 示例数据" : "示例数据"}</span>
          </div>

          <section className="ov-hero" aria-labelledby="overview-welcome">
            <img className="ov-hero-image" src={illustrationUrl} alt="护理人员温柔陪伴一位长者" width="1536" height="1024" fetchPriority="high" />
            <div className="ov-hero-content"><h2 id="overview-welcome">让照护服务，有序发生</h2><p>连接患者与护理人员，让沟通、匹配与服务更高效。</p>
              <div className="ov-hero-actions">
                <button className="ov-button ov-button-primary" type="button" data-view="consultation" onClick={() => navigate("consultation")}>进入智能问诊<ArrowRight size={18} /></button>
                <button className="ov-button ov-button-outline" type="button" data-view="jobs" onClick={() => navigate("jobs")}>查看护理招聘</button>
              </div>
            </div>
          </section>

          <section className="ov-metrics" aria-label="平台概况（示例数据）">
            {exampleMetrics.map(({ label, value, detail, icon: Icon, tone }, index) => (
              <article className="ov-metric" key={label}>
                <span className={`ov-icon-tile ov-tone-${tone}`}><Icon size={27} strokeWidth={1.65} aria-hidden="true" /></span>
                <div className="ov-metric-copy"><h2>{label}</h2><strong>{value}</strong><p>{detail}</p></div>
                {index === 0 && <svg className="ov-sparkline" viewBox="0 0 90 44" fill="none" aria-hidden="true"><path d="M3 36C10 35 11 38 17 32S24 24 30 29S38 30 44 21S52 25 58 23S65 10 70 15S77 21 87 5" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" /></svg>}
              </article>
            ))}
          </section>

          <div className="ov-lower-grid">
            <section className="ov-panel ov-jobs" aria-labelledby="overview-jobs-heading">
              <div className="ov-panel-heading"><h2 id="overview-jobs-heading">护理招聘动态</h2><button className="ov-text-link" type="button" data-view="jobs" onClick={() => navigate("jobs")}>查看全部<ArrowRight size={16} /></button></div>
              <div className="ov-filters" role="group" aria-label="筛选招聘状态">
                {filters.map((item) => <button key={item} className={`ov-filter${filter === item ? " is-active" : ""}`} type="button" aria-pressed={filter === item} onClick={() => setFilter(item)}>{item}</button>)}
              </div>
              <div className="ov-table-scroll">
                <table className="ov-jobs-table"><caption className="ov-sr-only">护理招聘动态，当前为示例数据</caption>
                  <thead><tr><th scope="col">护理需求</th><th scope="col">所在城市</th><th scope="col">服务预算</th><th scope="col">当前状态</th></tr></thead>
                  <tbody>{visibleJobs.map(({ title, detail, city, price, status, tone, icon: Icon }) => <tr key={title}>
                    <td><div className="ov-job-name"><span className={`ov-icon-tile ov-tone-${tone === "neutral" ? "green" : tone}`}><Icon size={23} strokeWidth={1.7} aria-hidden="true" /></span><div><strong>{title}</strong><p>{detail}</p></div></div></td>
                    <td>{city}</td><td className="ov-price">¥{price}<span> / 天</span></td><td><span className={`ov-status ov-status-${tone}`}>{status}</span></td>
                  </tr>)}</tbody>
                </table>
              </div>
              <p className="ov-filter-summary" aria-live="polite">共 {visibleJobs.length} 条{filter === "全部" ? "招聘动态" : `${filter}动态`}</p>
            </section>

            <section className="ov-panel ov-tasks" aria-labelledby="overview-tasks-heading">
              <div className="ov-panel-heading"><h2 id="overview-tasks-heading">{isAdmin ? "待办事项" : "服务快捷入口"}</h2><button className="ov-text-link" type="button" data-view={isAdmin ? "verification" : "accounts"} onClick={() => navigate(isAdmin ? "verification" : "accounts")}>查看全部<ChevronRight size={16} /></button></div>
              <div className="ov-task-list">{tasks.map(({ title, detail, icon: Icon, view }) => <button key={title} className="ov-task" data-view={view} type="button" onClick={() => navigate(view)}><span className="ov-icon-tile ov-tone-green"><Icon size={22} strokeWidth={1.7} aria-hidden="true" /></span><span className="ov-task-copy"><strong>{title}</strong><small>{detail}</small></span><ChevronRight size={17} aria-hidden="true" /></button>)}</div>
              <div className="ov-privacy"><ShieldCheck size={25} strokeWidth={1.65} aria-hidden="true" /><div><h3>服务与隐私</h3><p>关注服务质量，妥善保护用户信息。</p></div></div>
            </section>
          </div>
          <footer className="ov-footer">DoctorCarePlatform<span>·</span>医护陪护服务平台</footer>
    </WorkspaceShell>
  );
}
