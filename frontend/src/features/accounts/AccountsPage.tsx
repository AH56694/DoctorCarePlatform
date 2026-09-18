import { useState } from "react";
import { FileHeart, IdCard, Send, UploadCloud, UserRound, ShieldCheck, FileText, X, Loader2 } from "lucide-react";
import type { RoleName, AccountRead } from "../../types";
import { apiFetch } from "../../lib/api";
import { apiErrorMessage } from "../../lib/api-error";
import { roleLabel, statusLabel } from "../../lib/presentation";

export default function AccountsIdentity({
  account,
  setAccount
}: {
  account: AccountRead;
  setAccount: (account: AccountRead) => void;
}) {
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    try { await action(); } finally { setBusy(false); }
  }
  const [patientForm, setPatientForm] = useState({
    real_name: account.patient_profile?.real_name ?? "",
    id_number: "",
    age: String(account.patient_profile?.basic_info?.age ?? ""),
    care_need: String(account.patient_profile?.basic_info?.care_need ?? ""),
    care_details: String(account.patient_profile?.basic_info?.care_details ?? "")
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
  const [caseUploads, setCaseUploads] = useState<Array<{ file_url: string; summary: string; description: string }>>(() => {
    const records = account.patient_profile?.basic_info?.case_uploads;
    return Array.isArray(records) ? records.filter((item): item is { file_url: string; summary: string; description: string } => Boolean(item && typeof item === "object" && typeof item.file_url === "string" && typeof item.summary === "string" && typeof item.description === "string")) : [];
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
      const basic_info: Record<string, unknown> = { ...account.patient_profile?.basic_info, care_need: patientForm.care_need, care_details: patientForm.care_details };
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
          id_number: patientForm.id_number || undefined,
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
        body: JSON.stringify({ ...caregiverForm, id_number: caregiverForm.id_number || undefined })
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
          id_number: patientForm.id_number || undefined,
          basic_info
        })
      });
      setAccount(updated);
      setCaseUploads(nextUploads);
      setCaseForm({ file_url: "", summary: "", description: "" });
      setNotice("病例资料记录已保存。");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "上传病例资料失败。");
    }
  }

  const hasPatient = Boolean(account?.roles.some((item) => item.role === "patient"));
  const hasCaregiver = Boolean(account?.roles.some((item) => item.role === "caregiver"));
  const patientRole = account.roles.find((item) => item.role === "patient");
  const caregiverRole = account.roles.find((item) => item.role === "caregiver");
  const activeRole = account.active_role;

  const maskedPhone = account.phone.length > 7 ? `${account.phone.slice(0, 3)} **** ${account.phone.slice(-4)}` : account.phone;
  return (
    <section className="care-account-layout" aria-label="我的身份与资料">
      <aside className="care-card care-identity-card">
        <div className="care-person-hero">
          <span className="care-person-avatar"><UserRound size={48} strokeWidth={1.3} /></span>
          <h2>{account.display_name || "我的账号"}</h2><p>{maskedPhone}</p>
          <span className="care-badge"><ShieldCheck size={14} />账号{statusLabel(account.status)}</span>
        </div>
        <h3>当前身份</h3>
        <div className="care-role-switch" role="group" aria-label="身份切换">
          {(["patient", "caregiver"] as const).map(role => <button key={role} type="button" disabled={busy} aria-pressed={activeRole === role} className={activeRole === role ? "is-active" : ""} onClick={() => void perform(() => (role === "patient" ? hasPatient : hasCaregiver) ? switchRole(role) : createRole(role))}>
            {role === "patient" ? <UserRound size={21} /> : <IdCard size={21} />}{roleLabel(role)}
          </button>)}
        </div>
        <p className="care-muted">按当前身份管理资料与服务。</p>
        <h3 className="care-section-title">认证进度</h3>
        <div className="care-verification-row"><span><IdCard size={20} />病人实名</span><span className={`care-badge ${account.patient_profile?.id_verified ? "" : "is-pending"}`}>{!hasPatient ? "未开通" : account.patient_profile?.id_verified ? "已核验" : statusLabel(patientRole?.verification_status || "pending")}</span></div>
        <div className="care-verification-row"><span><FileHeart size={20} />护理资质</span><span className={`care-badge ${caregiverRole?.verification_status === "approved" ? "" : "is-pending"}`}>{hasCaregiver ? statusLabel(caregiverRole?.verification_status || "pending") : "未开通"}</span></div>
        <div className="care-privacy-note"><ShieldCheck size={23} /><p>资料用于服务与身份核验。</p></div>
        {!hasCaregiver && <button className="care-button is-outline care-full" disabled={busy} onClick={() => void perform(() => createRole("caregiver"))} type="button">开通护理身份</button>}
        {!hasPatient && <button className="care-button is-outline care-full" disabled={busy} onClick={() => void perform(() => createRole("patient"))} type="button">开通病人身份</button>}
      </aside>

      <div className="care-account-main">
        {notice && <p className="care-notice" role="status">{notice}</p>}
        {activeRole === "patient" && <>
          <form className="care-card" onSubmit={event => { event.preventDefault(); void perform(savePatientProfile); }}>
            <div className="care-card-heading"><h2>基础资料</h2><p>请填写真实、有效的身份信息</p></div>
            <div className="care-form-grid">
              <label>真实姓名<input required maxLength={80} autoComplete="name" placeholder="填写真实姓名" value={patientForm.real_name} onChange={event => setPatientForm({ ...patientForm, real_name: event.target.value })} /></label>
              <label>身份证号<input autoComplete="off" placeholder={account.patient_profile ? "留空保留已提交的证件号码" : "填写证件号码"} value={patientForm.id_number} onChange={event => setPatientForm({ ...patientForm, id_number: event.target.value })} /></label>
              <label>年龄<input type="number" min="0" max="150" placeholder="填写年龄" value={patientForm.age} onChange={event => setPatientForm({ ...patientForm, age: event.target.value })} /></label>
              <label>护理需求<input list="care-needs" placeholder="例如：术后康复陪护" value={patientForm.care_need} onChange={event => setPatientForm({ ...patientForm, care_need: event.target.value })} /><datalist id="care-needs"><option value="术后康复陪护" /><option value="日常生活照护" /><option value="居家康复协助" /></datalist></label>
              <label className="care-span-all">护理需求说明<textarea rows={3} maxLength={2000} placeholder="补充护理安排、日常起居协助等需求" value={patientForm.care_details} onChange={event => setPatientForm({ ...patientForm, care_details: event.target.value })} /></label>
            </div>
            <div className="care-form-actions"><button className="care-button" disabled={busy} type="submit">{busy && <Loader2 size={16} className="spin" />}保存资料</button><small>身份信息变更后需重新审核</small></div>
          </form>
          <form className="care-card" onSubmit={event => { event.preventDefault(); void perform(submitCaseUpload); }}>
            <div className="care-card-heading"><h2>病例资料</h2><FileHeart size={21} /></div>
            <label className="care-upload" htmlFor="caseFileUpload"><UploadCloud size={29} /><span><strong>点击选择病例或护理记录</strong><small>整理相关资料，便于后续沟通</small></span><input id="caseFileUpload" type="file" onChange={event => handleCaseFile(event.target.files)} /></label>
            {caseForm.file_url && <div className="care-file-row"><FileText size={23} /><span><strong>{caseForm.file_url.replace("local-upload://", "")}</strong><small>已选择 · 待提交</small></span><button className="care-icon-button" type="button" aria-label="移除所选病例文件" onClick={() => setCaseForm({ ...caseForm, file_url: "" })}><X size={17} /></button></div>}
            <p className="care-upload-note">当前文件选择仅记录名称。请填写病例摘要，或在下方提供已有的文件地址。</p>
            <div className="care-form-grid">
              <label className="care-span-all">病例摘要<input placeholder="近期照护安排与观察记录" value={caseForm.summary} onChange={event => setCaseForm({ ...caseForm, summary: event.target.value })} /></label>
              <label className="care-span-all">病例说明<textarea rows={2} placeholder="补充需要说明的内容" value={caseForm.description} onChange={event => setCaseForm({ ...caseForm, description: event.target.value })} /></label>
            </div>
            <details className="care-details"><summary>已有文件地址</summary><label>文件地址<input type="text" placeholder="填写已有病例文件地址" value={caseForm.file_url} onChange={event => setCaseForm({ ...caseForm, file_url: event.target.value })} /></label></details>
            <div className="care-form-actions is-right"><button className="care-button" disabled={busy || (!caseForm.file_url.trim() && !caseForm.summary.trim())} type="submit"><Send size={16} />提交病例资料</button></div>
            {caseUploads.length > 0 && <div className="care-saved-files"><h3>已保存的病例资料</h3>{caseUploads.map((item, index) => <div className="care-file-row" key={`${item.file_url}-${index}`}><FileText size={21} /><span><strong>{item.summary || "病例资料"}</strong><small>{item.description || item.file_url}</small></span><span className="care-badge">已记录</span></div>)}</div>}
          </form>
        </>}

        {activeRole === "caregiver" && <>
          <form className="care-card" onSubmit={event => { event.preventDefault(); void perform(saveCaregiverProfile); }}>
            <div className="care-card-heading"><h2>护理基础资料</h2><p>让有需要的人更了解你</p></div>
            <div className="care-form-grid">
              <label>真实姓名<input required placeholder="填写真实姓名" value={caregiverForm.real_name} onChange={event => setCaregiverForm({ ...caregiverForm, real_name: event.target.value })} /></label>
              <label>身份证号<input autoComplete="off" placeholder="留空保留已提交的证件号码" value={caregiverForm.id_number} onChange={event => setCaregiverForm({ ...caregiverForm, id_number: event.target.value })} /></label>
              <label>服务城市<input placeholder="填写服务城市" value={caregiverForm.service_city} onChange={event => setCaregiverForm({ ...caregiverForm, service_city: event.target.value })} /></label>
              <label>经验年限<input type="number" min="0" max="80" value={caregiverForm.experience_years} onChange={event => setCaregiverForm({ ...caregiverForm, experience_years: Number(event.target.value) })} /></label>
              <label className="care-span-all">护理经验与服务介绍<textarea rows={4} placeholder="护理经验、擅长服务、可服务时间" value={caregiverForm.bio} onChange={event => setCaregiverForm({ ...caregiverForm, bio: event.target.value })} /></label>
            </div>
            <label className="care-checkbox"><input type="checkbox" checked={caregiverForm.is_available} onChange={event => setCaregiverForm({ ...caregiverForm, is_available: event.target.checked })} />当前可接单</label>
            <div className="care-form-actions"><button className="care-button" disabled={busy} type="submit">保存护理资料</button><small>身份信息变更后需重新审核</small></div>
          </form>
          <form className="care-card" onSubmit={event => { event.preventDefault(); void perform(submitCertification); }}>
            <div className="care-card-heading"><h2>护理资质</h2><IdCard size={21} /></div>
            <label className="care-upload" htmlFor="certificateFileUpload"><UploadCloud size={29} /><span><strong>选择护理证书或资质证明</strong><small>{certForm.file_url ? certForm.file_url.replace("local-upload://", "") : "补充资质，便于平台审核"}</small></span><input id="certificateFileUpload" type="file" onChange={event => handleCertificateFile(event.target.files)} /></label>
            <p className="care-upload-note">当前文件选择仅记录名称；审核时请提供可访问的证明文件地址。</p>
            <div className="care-form-grid"><label>证书类型<input required value={certForm.certificate_type} onChange={event => setCertForm({ ...certForm, certificate_type: event.target.value })} /></label><label>证书文件地址<input required placeholder="填写已有证书文件地址" value={certForm.file_url} onChange={event => setCertForm({ ...certForm, file_url: event.target.value })} /></label><label className="care-span-all">证书说明<textarea rows={2} value={certForm.description} onChange={event => setCertForm({ ...certForm, description: event.target.value })} /></label></div>
            <div className="care-form-actions is-right"><button className="care-button" disabled={busy} type="submit">提交护理认证</button></div>
            {account.certifications.map(cert => <div className="care-file-row" key={cert.id}><FileText size={21} /><span><strong>{cert.certificate_type}</strong><small>{cert.description || "暂无说明"}</small></span><span className="care-badge is-pending">{statusLabel(cert.review_status)}</span></div>)}
            {!account.certifications.length && <p className="care-empty">暂无护理认证记录</p>}
          </form>
        </>}
        {activeRole === "admin" && <div className="care-card care-empty"><ShieldCheck size={36} /><h2>当前为管理员身份</h2><p>可在左侧开通或切换病人、护理身份后维护对应资料。</p></div>}
      </div>
    </section>
  );
}
