import { useState } from "react";
import { useEffect } from "react";
import { BriefcaseMedical, ClipboardList, Loader2, MapPin, MessageSquareText, Plus, RefreshCw, Search, Send, Star, X } from "lucide-react";
import type { JobPosting, JobApplication, AvailableCaregiver, Invitation, MatchResult, CaregiverResume, AccountRead, CareConversation } from "../../types";
import { apiFetch } from "../../lib/api";
import { apiErrorMessage } from "../../lib/api-error";
import { statusLabel } from "../../lib/presentation";

export default function Jobs({ account, onOpenChat }: { account: AccountRead; onOpenChat: () => void }) {
  const isPatient = account.active_role === "patient";
  const isCaregiver = account.active_role === "caregiver";
  const [jobRows, setJobRows] = useState<JobPosting[]>([]);
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [caregivers, setCaregivers] = useState<AvailableCaregiver[]>([]);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [selectedJobId, setSelectedJobId] = useState("");
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [tab, setTab] = useState("jobs");
  const [query, setQuery] = useState("");
  const [publishOpen, setPublishOpen] = useState(false);
  const [invitee, setInvitee] = useState<AvailableCaregiver | null>(null);
  const [busy, setBusy] = useState(false);
  async function perform(action: () => Promise<void>) {
    if (busy || loading) return;
    setBusy(true);
    try { await action(); } finally { setBusy(false); }
  }
  const [jobForm, setJobForm] = useState({
    employer_id: account.id,
    title: "",
    city: "",
    patient_gender: "",
    patient_age: 0,
    patient_height_cm: 0,
    patient_weight_kg: 0,
    disease_type: "",
    care_type: "",
    care_level: "",
    location: "",
    address_detail: "",
    salary_amount: 0,
    salary_unit: "天",
    care_start_date: "",
    care_end_date: "",
    care_start_time: "08:00",
    care_end_time: "18:00",
    budget_cents: 0,
    description: "",
    special_requirements: ""
  });
  const [applicationForm, setApplicationForm] = useState({
    caregiver_id: account.active_role === "caregiver" ? account.id : "",
    cover_letter: ""
  });
  const [invitationForm, setInvitationForm] = useState({
    patient_id: account.id,
    caregiver_id: "",
    message: ""
  });
  const [caregiverFilters, setCaregiverFilters] = useState({
    city: "",
    keyword: "",
    min_experience: ""
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
      throw new Error(await apiErrorMessage(response));
    }
    return response.json() as Promise<T>;
  }

  async function refreshJobs() {
    setLoading(true);
    setNotice("");
    try {
      const [jobResult, invitationResult] = await Promise.all([
        requestJson<JobPosting[]>("/api/v1/jobs?status=published"),
        isPatient || isCaregiver
          ? requestJson<Invitation[]>("/api/v1/jobs/invitations")
          : Promise.resolve([])
      ]);
      const ownedJobs = jobResult.filter((job) => job.employer_id === account.id);
      const selectedStillValid = jobResult.some((job) => job.id === selectedJobId);
      const nextJobId = isPatient
        ? (ownedJobs.some((job) => job.id === selectedJobId) ? selectedJobId : ownedJobs[0]?.id || "")
        : (selectedStillValid ? selectedJobId : jobResult[0]?.id || "");
      const [caregiverResult, applicationResult] = await Promise.all([
        isPatient && nextJobId
          ? fetchRecommendedCaregivers(nextJobId)
          : Promise.resolve([]),
        isPatient && nextJobId
          ? requestJson<JobApplication[]>(`/api/v1/jobs/${nextJobId}/applications`)
          : isCaregiver
            ? requestJson<JobApplication[]>(`/api/v1/jobs/caregivers/${account.id}/applications`)
            : Promise.resolve([])
      ]);
      setJobRows(jobResult);
      setCaregivers(caregiverResult);
      setApplications(applicationResult);
      setInvitations(invitationResult);
      setSelectedJobId(nextJobId);
    } catch (error) {
      setJobRows([]);
      setApplications([]);
      setCaregivers([]);
      setInvitations([]);
      setSelectedJobId("");
      setNotice(error instanceof Error ? error.message : "招聘数据加载失败，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  async function fetchRecommendedCaregivers(jobId = selectedJobId) {
    if (!isPatient || !jobId) {
      return [];
    }
    const knownJob = jobRows.find((job) => job.id === jobId);
    if (knownJob && knownJob.employer_id !== account.id) {
      return [];
    }
    const params = new URLSearchParams({ job_id: jobId });
    if (caregiverFilters.city.trim()) {
      params.set("city", caregiverFilters.city.trim());
    }
    if (caregiverFilters.keyword.trim()) {
      params.set("keyword", caregiverFilters.keyword.trim());
    }
    if (caregiverFilters.min_experience) {
      params.set("min_experience", caregiverFilters.min_experience);
    }
    return requestJson<AvailableCaregiver[]>(`/api/v1/jobs/caregivers/available?${params.toString()}`);
  }

  async function refreshRecommendedCaregivers(jobId = selectedJobId) {
    if (!jobId) {
      setNotice("请先发布或选择本人名下的岗位。");
      return;
    }
    setLoading(true);
    setNotice("");
    try {
      setCaregivers(await fetchRecommendedCaregivers(jobId));
      setNotice("已更新推荐护理人员。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载推荐护理人员失败。");
    } finally {
      setLoading(false);
    }
  }

  async function loadApplications(jobId = selectedJobId) {
    if (!isPatient || !jobId) {
      return;
    }
    const job = jobRows.find((row) => row.id === jobId);
    if (job && job.employer_id !== account.id) {
      setApplications([]);
      setCaregivers([]);
      setSelectedJobId(jobId);
      setNotice("只能管理本人发布岗位的应聘记录和候选人推荐。");
      return;
    }
    try {
      const [rows, people] = await Promise.all([
        requestJson<JobApplication[]>(`/api/v1/jobs/${jobId}/applications`),
        fetchRecommendedCaregivers(jobId)
      ]);
      setApplications(rows);
      setCaregivers(people);
      setSelectedJobId(jobId);
      setInvitee(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载应聘记录失败。");
    }
  }

  async function selectRecommendedCaregiver(caregiver: AvailableCaregiver) {
    setInvitee(caregiver);
    setInvitationForm((current) => ({ ...current, caregiver_id: caregiver.user_id }));
    try {
      const params = new URLSearchParams({ viewer_id: account.id });
      if (selectedJobId) {
        params.set("job_id", selectedJobId);
      }
      await requestJson<CaregiverResume>(
        `/api/v1/profiles/caregivers/${caregiver.user_id}?${params.toString()}`
      );

    } catch (error) {
      setNotice(error instanceof Error ? error.message : "加载护理人员详情失败。");
    }
  }

  async function createJob() {
    setLoading(true);
    setNotice("");
    try {
      const salaryCents = Math.round(Math.max(0, Number(jobForm.salary_amount) || 0) * 100);
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
      await refreshJobs();
      setPublishOpen(false);
      setTab("jobs");
      setNotice(`招聘已发布：${created.title}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "发布招聘失败。");
    } finally {
      setLoading(false);
    }
  }

  async function applyForJob() {
    if (!isCaregiver || !selectedJobId) {
      setNotice("请以护理身份选择招聘后提交应聘。");
      return;
    }
    try {
      const application = await requestJson<JobApplication>(`/api/v1/jobs/${selectedJobId}/applications`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ ...applicationForm, caregiver_id: account.id })
      });
      setNotice("应聘已提交，可在应聘记录中查看进度。");
      setApplicationForm(current => ({ ...current, cover_letter: "" }));
      setApplications(await requestJson<JobApplication[]>(`/api/v1/jobs/caregivers/${account.id}/applications`));
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
      await refreshJobs();
      setNotice(statusValue === "accepted" ? "应聘已通过，可前往聊天沟通。" : "已拒绝该应聘。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "处理应聘失败。");
    }
  }

  async function createInvitation() {
    if (!selectedJobId || !invitationForm.patient_id.trim() || !invitationForm.caregiver_id.trim()) {
      setNotice("请选择本人发布的岗位和护理方后再发送邀请。");
      return;
    }
    try {
      const invitation = await requestJson<Invitation>("/api/v1/jobs/invitations", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ ...invitationForm, job_id: selectedJobId || null })
      });
      await refreshJobs();
      setInvitee(null);
      setInvitationForm(current => ({ ...current, caregiver_id: "", message: "" }));
      setNotice("邀请已发送，可在邀请记录中查看进度。");
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
      setNotice(statusValue === "accepted" ? "已接受邀请，可前往聊天沟通。" : "已拒绝邀请。");
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
  }, [account.id, account.active_role]);


  const selectedJob = jobRows.find(job => job.id === selectedJobId);
  const visibleJobs = jobRows.filter(job => `${job.title} ${job.city} ${job.care_type} ${job.location}`.toLowerCase().includes(query.trim().toLowerCase()));
  const disabled = loading || busy;
  const jobTitle = (id?: string | null) => jobRows.find(job => job.id === id)?.title || "关联岗位";
  const caregiverName = (id: string) => caregivers.find(person => person.user_id === id)?.real_name || `护理用户 · ${id.slice(0, 8)}`;
  const publishFields: Array<{key: keyof typeof jobForm; label: string; type?: string; required?: boolean; max?: number}> = [
    {key:"title",label:"招聘标题",required:true},{key:"city",label:"服务城市",required:true},
    {key:"care_type",label:"护理类型",required:true},{key:"care_level",label:"照护安排"},
    {key:"patient_age",label:"病人年龄",type:"number",max:150},{key:"disease_type",label:"病症类型"},
    {key:"patient_height_cm",label:"身高（厘米）",type:"number",max:300},{key:"patient_weight_kg",label:"体重（公斤）",type:"number",max:600},
    {key:"location",label:"服务区域",required:true},{key:"address_detail",label:"详细地点"},
    {key:"care_start_date",label:"开始日期",type:"date"},{key:"care_end_date",label:"结束日期",type:"date"},
    {key:"care_start_time",label:"每日开始时间",type:"time"},{key:"care_end_time",label:"每日结束时间",type:"time"},
    {key:"salary_amount",label:"薪资酬劳（元）",type:"number",required:true}
  ];
  return (
    <section className="care-jobs-page" aria-label="护理招聘工作区">
      <div className="care-jobs-toolbar">
        <p className="care-muted">{loading ? "正在加载招聘信息…" : `共 ${jobRows.length} 个在招岗位`}</p>
        <div className="care-actions"><button className="care-icon-button" title="刷新招聘" aria-label="刷新招聘" disabled={disabled} onClick={() => void refreshJobs()} type="button"><RefreshCw size={18} className={loading ? "spin" : ""} /></button>{isPatient && <button className="care-button" disabled={disabled} aria-expanded={publishOpen} aria-controls="care-publish" onClick={() => setPublishOpen(!publishOpen)} type="button">{publishOpen ? <X size={18} /> : <Plus size={18} />}{publishOpen ? "收起表单" : "发布招聘"}</button>}</div>
      </div>
      {notice && <p className="care-notice" role="status">{notice}</p>}
      {publishOpen && isPatient && <form id="care-publish" className="care-card care-publish" onSubmit={event => {event.preventDefault(); void perform(createJob);}}>
        <div className="care-card-heading"><div><h2>发布护理招聘</h2><p>填写服务安排，让护理人员了解你的需求。</p></div><BriefcaseMedical size={24} /></div>
        <div className="care-form-grid">
          {publishFields.map(field => <label key={field.key}>{field.label}<input type={field.type || "text"} required={field.required} minLength={field.key === "title" ? 2 : undefined} maxLength={field.key === "title" ? 120 : undefined} min={field.type === "number" ? 0 : field.key === "care_end_date" ? jobForm.care_start_date : undefined} max={field.max} step={field.key === "salary_amount" ? "0.01" : undefined} value={jobForm[field.key] || ""} onChange={event => setJobForm({...jobForm,[field.key]:field.type === "number" ? Number(event.target.value) : event.target.value})} /></label>)}
          <label>计薪方式<select value={jobForm.salary_unit} onChange={event => setJobForm({...jobForm,salary_unit:event.target.value})}>{["小时","天","周","月"].map(unit => <option key={unit} value={unit}>按{unit}</option>)}</select></label>
          <label>病人性别<select value={jobForm.patient_gender} onChange={event => setJobForm({...jobForm,patient_gender:event.target.value})}><option value="">请选择</option>{["女","男","其他"].map(value => <option key={value}>{value}</option>)}</select></label>
          <label className="care-span-all">补充护理说明<textarea rows={3} value={jobForm.description} onChange={event => setJobForm({...jobForm,description:event.target.value})} /></label>
          <label className="care-span-all">特殊要求<textarea rows={2} value={jobForm.special_requirements} onChange={event => setJobForm({...jobForm,special_requirements:event.target.value})} /></label>
        </div><div className="care-form-actions is-right"><button className="care-button is-outline" type="button" onClick={() => setPublishOpen(false)}>暂不发布</button><button className="care-button" disabled={disabled} type="submit"><Send size={16} />确认发布</button></div>
      </form>}
      <div className="care-card care-job-tabs">
        <div className="care-tabs" role="tablist" aria-label="招聘记录" onKeyDown={event => {
          const ids = ["jobs", "applications", "invitations"];
          const index = ids.indexOf(tab);
          const next = event.key === "ArrowRight" ? (index + 1) % 3 : event.key === "ArrowLeft" ? (index + 2) % 3 : event.key === "Home" ? 0 : event.key === "End" ? 2 : -1;
          if (next >= 0) { event.preventDefault(); setTab(ids[next]); event.currentTarget.querySelectorAll<HTMLButtonElement>("button")[next]?.focus(); }
        }}>{[["jobs","招聘动态"],["applications",isCaregiver ? "我的应聘" : "应聘记录"],["invitations",isCaregiver ? "收到的邀请" : "已发送邀请"]].map(([id,label]) => <button key={id} id={`tab-${id}`} role="tab" type="button" tabIndex={tab === id ? 0 : -1} aria-selected={tab === id} aria-controls="care-job-panel" className={tab === id ? "is-active" : ""} onClick={() => setTab(id)}>{label}</button>)}</div>
        {tab === "jobs" && <label className="care-search"><Search size={18} /><input aria-label="搜索招聘" placeholder="搜索岗位、城市或护理类型" value={query} onChange={event => setQuery(event.target.value)} /></label>}
      </div>
      <div className="care-jobs-layout">
        <div id="care-job-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="care-job-list">
          {tab !== "jobs" && <div className="care-card care-record-context"><h2>{tab === "applications" ? "应聘记录" : isCaregiver ? "收到的邀请" : "已发送邀请"}</h2>{isPatient && tab === "applications" && <label>当前岗位<select disabled={disabled} value={selectedJobId} onChange={event => void perform(() => loadApplications(event.target.value))}><option value="" disabled>请选择本人发布的岗位</option>{jobRows.filter(job => job.employer_id === account.id).map(job => <option key={job.id} value={job.id}>{job.title}</option>)}</select></label>}</div>}
          {tab === "jobs" && visibleJobs.map(job => <article className={`care-card care-job-card ${selectedJobId === job.id ? "is-selected" : ""}`} key={job.id}>
            <div className="care-job-title"><span className="care-square-icon"><BriefcaseMedical size={24} /></span><div><h2>{job.title}</h2><p><MapPin size={14} />{job.city} {job.location}</p></div><span className="care-badge">{statusLabel(job.status)}</span></div>
            <div className="care-tags">{[job.care_type,job.care_level].filter(Boolean).map((tag,i) => <span key={i}>{tag}</span>)}{job.employer_id === account.id && <span>我发布的</span>}</div>
            <p className="care-job-description">{job.description || "暂无补充说明"}</p>
            {job.special_requirements && <details className="care-details"><summary>护理要求与详情</summary><p className="care-preserve-lines">{job.special_requirements}</p><p className="care-preserve-lines">{job.description}</p></details>}
            <div className="care-job-bottom"><div className="care-budget"><small>预算</small><strong>¥{(job.budget_cents / 100).toLocaleString("zh-CN",{maximumFractionDigits:2})}</strong>{job.salary?.unit && <small> / {job.salary.unit}</small>}</div><div className="care-actions">
              {isPatient && job.employer_id === account.id && <button type="button" className="care-button is-outline" disabled={disabled} onClick={() => void perform(async () => {setInvitee(null); await loadApplications(job.id);})}>{selectedJobId === job.id ? "已选岗位" : "选择岗位"}</button>}
              {isPatient && job.employer_id === account.id && <button type="button" className="care-button" disabled={disabled} onClick={() => void perform(async () => {setInvitee(null); await loadApplications(job.id); setTab("applications");})}>查看应聘</button>}
              {isCaregiver && job.employer_id !== account.id && <><button type="button" className="care-button is-outline" disabled={disabled} onClick={() => void perform(() => openConversation(job.employer_id,"job",job.id))}>发起沟通</button><button type="button" className="care-button" disabled={disabled} onClick={() => {setSelectedJobId(job.id);setTab("applications");}}>我要应聘</button></>}
            </div></div>
          </article>)}
          {tab === "applications" && isCaregiver && <form className="care-card" onSubmit={event => {event.preventDefault(); void perform(applyForJob);}}><h2>提交应聘</h2><label>选择岗位<select disabled={disabled} required value={selectedJobId} onChange={event => setSelectedJobId(event.target.value)}><option value="" disabled>请选择岗位</option>{jobRows.map(job => <option key={job.id} value={job.id}>{job.title} · {job.city}</option>)}</select></label><label>应聘说明<textarea rows={3} placeholder="介绍相关护理经验、可服务时间" value={applicationForm.cover_letter} onChange={event => setApplicationForm({...applicationForm,cover_letter:event.target.value})} /></label><div className="care-form-actions is-right"><button className="care-button" disabled={disabled || !selectedJobId}>提交应聘</button></div></form>}
          {tab === "applications" && applications.map(item => <article className="care-card care-record" key={item.id}><div className="care-card-heading"><h2>{isCaregiver ? jobTitle(item.job_id) : caregiverName(item.caregiver_id)}</h2><span className="care-badge is-pending">{item.status === "pending" ? "待处理" : item.status === "accepted" ? "已通过" : statusLabel(item.status)}</span></div><p>{item.cover_letter || "暂无应聘说明"}</p>{isPatient && <div className="care-form-actions is-right"><button className="care-button is-outline" disabled={disabled} onClick={() => void perform(() => openConversation(item.caregiver_id,"application",item.id))}>沟通</button>{item.status === "pending" && <><button className="care-button is-outline" disabled={disabled} onClick={() => void perform(() => reviewApplication(item.id,"rejected"))}>拒绝</button><button className="care-button" disabled={disabled} onClick={() => void perform(() => reviewApplication(item.id,"accepted"))}>通过应聘</button></>}</div>}</article>)}
          {tab === "invitations" && invitations.map(item => <article className="care-card care-record" key={item.id}><div className="care-card-heading"><h2>{jobTitle(item.job_id)}</h2><span className="care-badge is-pending">{item.status === "pending" ? "待回应" : statusLabel(item.status)}</span></div><p>{isCaregiver ? `邀请方 · ${item.patient_id.slice(0,8)}` : caregiverName(item.caregiver_id)}</p><p>{item.message || "暂无邀请说明"}</p><div className="care-form-actions is-right"><button className="care-button is-outline" disabled={disabled} onClick={() => void perform(() => openConversation(isCaregiver ? item.patient_id : item.caregiver_id,"invitation",item.id))}>发起沟通</button>{isCaregiver && item.status === "pending" && <><button className="care-button is-outline" disabled={disabled} onClick={() => void perform(() => respondInvitation(item.id,"rejected"))}>拒绝</button><button className="care-button" disabled={disabled} onClick={() => void perform(() => respondInvitation(item.id,"accepted"))}>接受邀请</button></>}</div></article>)}
          {!loading && (tab === "jobs" ? !visibleJobs.length : tab === "applications" ? !applications.length : !invitations.length) && <div className="care-card care-empty"><ClipboardList size={34} /><h3>{tab === "jobs" ? "暂无匹配的招聘" : tab === "applications" ? "暂无应聘记录" : "暂无邀请记录"}</h3><p>{tab === "jobs" ? "试试其他关键词，或稍后刷新。" : "相关进度会显示在这里。"}</p></div>}
          {loading && !jobRows.length && <div className="care-card care-empty" role="status"><Loader2 className="spin" size={25} />正在加载招聘信息…</div>}
        </div>
        <aside className="care-card care-recommendations">
          <div className="care-card-heading"><div><h2>{isPatient ? "推荐护理人员" : "照护连接，从沟通开始"}</h2><p>{isPatient ? selectedJob ? `为「${selectedJob.title}」寻找合适人选` : "选择本人发布的岗位后查看推荐" : "了解服务安排，确认双方的需求与期待。"}</p></div></div>
          {isPatient && <>
            <form className="care-filter-form" onSubmit={event => {event.preventDefault();void perform(() => refreshRecommendedCaregivers());}}><label>服务城市<input placeholder="不限城市" value={caregiverFilters.city} onChange={event => setCaregiverFilters({...caregiverFilters,city:event.target.value})} /></label><label>最低经验<select value={caregiverFilters.min_experience} onChange={event => setCaregiverFilters({...caregiverFilters,min_experience:event.target.value})}><option value="">不限年限</option>{[1,3,5,10].map(year => <option key={year} value={year}>{year} 年及以上</option>)}</select></label><label className="care-span-all">护理技能<input placeholder="搜索护理技能或简介" value={caregiverFilters.keyword} onChange={event => setCaregiverFilters({...caregiverFilters,keyword:event.target.value})} /></label><button className="care-button is-outline care-span-all" disabled={disabled || !selectedJobId}><Search size={16} />筛选护理人员</button></form>
            {invitee && <form className="care-invitation-form" onSubmit={event => {event.preventDefault();void perform(createInvitation);}}><div className="care-card-heading"><h3>邀请 {invitee.real_name || "护理人员"}</h3><button aria-label="取消邀请编辑" className="care-icon-button" type="button" onClick={() => setInvitee(null)}><X size={17} /></button></div><p>{selectedJob?.title}</p><label>邀请说明<textarea rows={3} autoFocus placeholder="简要介绍照护需求与时间安排" value={invitationForm.message} onChange={event => setInvitationForm({...invitationForm,message:event.target.value})} /></label><button className="care-button care-full" disabled={disabled || !selectedJobId}><Send size={16} />确认发送邀请</button></form>}
            {caregivers.map(person => <article className="care-candidate" key={person.user_id}><div className="care-candidate-heading"><span className="care-candidate-avatar">{(person.real_name || "护").slice(0,1)}</span><div><h3>{person.real_name || "护理人员"}</h3><p>{person.service_city || "城市未填写"} · {person.experience_years} 年经验</p></div><span className="care-rating"><Star size={14} />{person.rating_avg > 0 ? person.rating_avg.toFixed(1) : "暂无评分"}</span></div><p className="care-candidate-bio">{person.bio || "暂无服务介绍"}</p><div className="care-actions"><button className="care-button is-outline" disabled={disabled} onClick={() => void perform(() => openConversation(person.user_id,"job",selectedJobId))}><MessageSquareText size={15} />发起沟通</button><button className="care-button" disabled={disabled || !selectedJobId} onClick={() => void perform(() => selectRecommendedCaregiver(person))}>发送邀请</button></div></article>)}
            {!caregivers.length && <div className="care-empty"><Search size={29} /><p>{selectedJobId ? "暂无符合条件的护理人员" : "先发布或选择你的岗位"}</p></div>}
          </>}
          {!isPatient && <div className="care-empty"><MessageSquareText size={42} /><p>从招聘卡片发起沟通，或在邀请记录中查看新的机会。</p></div>}
        </aside>
      </div>
    </section>
  );
}
