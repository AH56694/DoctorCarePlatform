// Development-only fixture: all API calls stay in memory; never contacts the backend.
import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import WorkspaceShell from "../../src/features/workspace/WorkspaceShell";
import AccountsPage from "../../src/features/accounts/AccountsPage";
import JobsPage from "../../src/features/jobs/JobsPage";
import ConsultationPage from "../../src/features/consultation/ConsultationPage";
import type { AccountRead, View } from "../../src/types";
import "../../src/styles.css";

let account: AccountRead = { id:"fixture-patient",phone:"13800000000",display_name:"演示用户",status:"active",active_role:"patient",roles:[{id:"r1",role:"patient",is_active:true,verification_status:"pending"},{id:"r2",role:"caregiver",is_active:false,verification_status:"pending"}],patient_profile:{real_name:"演示用户",id_verified:false,verification_status:"pending",basic_info:{age:68,care_need:"术后康复陪护",care_details:"希望安排日间陪护，协助起居并整理每日护理记录。",preserved_metadata:"keep-me"}},caregiver_profile:{real_name:"护理演示用户",id_verified:false,verification_status:"pending",bio:"提供日常照护与康复协助。",is_available:true,experience_years:5,service_city:"上海",rating_avg:4.8},certifications:[] };
const jobs = [{id:"job-1",employer_id:account.id,title:"术后康复陪护",city:"上海",care_type:"术后护理",care_level:"日间陪护",location:"浦东新区",budget_cents:48000,status:"published",description:"协助日常起居与活动，整理护理观察记录。期待有相关经验的护理伙伴，服务安排可沟通。",special_requirements:"有照护经验，耐心细致。"},{id:"job-2",employer_id:account.id,title:"夜间病房陪护",city:"杭州",care_type:"住院照护",care_level:"夜间陪护",location:"西湖区",budget_cents:36000,status:"published",description:"关注夜间照护需求，协助基础生活起居，具体工作与服务时间可提前沟通。",special_requirements:"沟通耐心，能够稳定服务。"},{id:"job-3",employer_id:"fixture-other",title:"居家康复协助",city:"苏州",care_type:"居家护理",care_level:"日间照护",location:"工业园区",budget_cents:52000,status:"published",description:"日常起居协助与居家陪伴，服务安排可沟通。",special_requirements:""}];
const people = [{user_id:"care-1",real_name:"林阿姨",bio:"提供日常生活照护与康复协助，重视沟通，服务细致。",service_city:"上海",experience_years:8,rating_avg:4.9,is_available:true},{user_id:"care-2",real_name:"周阿姨",bio:"熟悉住院陪护与居家照护，能够稳定安排服务时间。",service_city:"杭州",experience_years:6,rating_avg:4.8,is_available:true},{user_id:"care-3",real_name:"陈师傅",bio:"日常起居协助、护理观察与陪伴，期待与家属提前沟通。",service_city:"上海",experience_years:5,rating_avg:0,is_available:true}];
const applications = [{id:"apply-1",job_id:"job-1",caregiver_id:"care-1",cover_letter:"有相关照护经验，可沟通服务时间。",status:"pending"}];
const invitations = [{id:"invite-1",patient_id:account.id,caregiver_id:"care-2",job_id:"job-1",status:"pending",message:"想了解您的服务时间，期待进一步沟通。"}];
const sessions = [{id:"session-1",title:"日常护理记录整理",summary:"了解如何整理照护观察与沟通事项",updated_at:"2026-09-15T09:00:00+08:00",created_at:"2026-09-15T08:30:00+08:00"},{id:"session-2",title:"居家照护沟通准备",summary:"第一次沟通前的信息整理",updated_at:"2026-09-14T10:00:00+08:00",created_at:"2026-09-14T10:00:00+08:00"}];
let messages = [{id:"m1",session_id:"session-1",sender:"user",content:"我想整理每日的护理观察记录，方便与护理人员沟通。",created_at:"2026-09-15T08:30:00+08:00"},{id:"m2",session_id:"session-1",sender:"ai",content:"### 让照护信息更清晰\n可以把记录按时间、观察和待沟通事项整理。\n\n1. 记录日期与观察时间。\n2. 用客观文字描述观察到的情况。\n3. 列出希望进一步确认的问题。\n\n这是用于界面验证的示例内容。",created_at:"2026-09-15T08:30:01+08:00",metadata_json:{citations:[]}}];
const requests: Array<{path:string;method:string;body:unknown}> = [];
let failNext = false;
let empty = false;
const json = (body:unknown,status=200) => new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json"}});
window.fetch = async (input,init={}) => {
  const path = String(input); const method = init.method || "GET"; const body = init.body ? JSON.parse(String(init.body)) : {};
  requests.push({path,method,body});
  window.dispatchEvent(new Event("fixture-request"));
  if (failNext) {failNext = false; return json({detail:"测试：服务暂不可用"},503);}
  if (path.includes("/ai/chat/stream")) {
    const answer = "已收到你的问题。可以继续补充观察时间、已有记录与希望沟通的事项。此回复仅用于界面测试。";
    const response = {answer,intent:{category:"medical_consult",subcategory:"care_method",confidence:0.9},cache_hit_level:"miss",citations:[],session_id:"session-1",tool_calls:[],steps:[],intermediate_conclusions:[]};
    messages = [...messages,{id:crypto.randomUUID(),sender:"user",content:body.message,session_id:"session-1",created_at:new Date().toISOString()},{id:crypto.randomUUID(),sender:"ai",content:answer,session_id:"session-1",created_at:new Date().toISOString()}];
    const frames = [{type:"token",content:answer.slice(0,18)},{type:"token",content:answer.slice(18)},{type:"final",response}];
    return new Response(new ReadableStream({async start(controller){for(const frame of frames){controller.enqueue(new TextEncoder().encode(`data: ${JSON.stringify(frame)}\n\n`));await new Promise(resolve=>setTimeout(resolve,250));}controller.close();}}),{headers:{"Content-Type":"text/event-stream"}});
  }
  if (path.includes("/ai/sessions/") && path.includes("/messages")) return json(empty ? [] : messages);
  if (path.includes("/ai/sessions?")) return json(empty ? [] : sessions);
  if (path.includes("/roles")) {account = {...account,active_role:body.role};return json(account);}
  if (path.includes("/profiles/patient") && method === "PUT") {account = {...account,patient_profile:{...account.patient_profile!,real_name:body.real_name,basic_info:body.basic_info}};return json(account);}
  if (path.includes("/profiles/caregiver") && method === "PUT") {account = {...account,caregiver_profile:{...account.caregiver_profile!,...body}};return json(account);}
  if (path.includes("/identity")) return json(account);
  if (path.includes("/certifications")) return json({id:"certificate-fixture"});
  if (path.includes("/caregivers/available")) {const url = new URL(path,location.origin); return json(empty ? [] : people.filter(person => (!url.searchParams.get("city") || person.service_city.includes(url.searchParams.get("city")!)) && person.experience_years >= Number(url.searchParams.get("min_experience") || 0)));}
  if (path.includes("/profiles/caregivers/")) return json(people[0]);
  if (path.includes("/review")) {const item = applications.find(row=>path.includes(row.id));if(item)item.status=body.status;return json({status:body.status});}
  if (path.includes("/respond")) {const item = invitations.find(row=>path.includes(row.id));if(item)item.status=body.status;return json({status:body.status});}
  if (path.includes("/applications")) {if(method === "POST"){const item = {id:crypto.randomUUID(),job_id:path.split("/")[4],status:"pending",...body};applications.push(item);return json(item);}return json(empty ? [] : applications.filter(item=>path.includes("/caregivers/") || path.includes(item.job_id)));}
  if (path.includes("/invitations")) {if(method === "POST"){const item = {id:crypto.randomUUID(),status:"pending",...body};invitations.push(item);return json(item);}return json(empty ? [] : invitations);}
  if (path.includes("/api/v1/jobs")) {if(method === "POST"){const item = {...body,id:crypto.randomUUID(),status:"published"};jobs.push(item);return json(item);}return json(empty ? [] : jobs);}
  if (path.includes("/conversations")) return json({id:"fixture-chat",title:"招聘沟通"});
  return json({detail:`Unmocked fixture request: ${path}`},501);
};
function Fixture() {
  const [user,setUser] = useState(account); const [view,setView] = useState<View>("accounts"); const [,render] = useState(0); const [action,setAction] = useState("");
  window.onpopstate = () => setView("accounts");
  const titles = {accounts:["我的信息","完善身份资料，安心开启每一次照护。"],jobs:["护理招聘","清晰发布照护需求，找到合适的护理伙伴。"],consultation:["智能问诊","整理问题与护理记录，让每次咨询更清晰。"]};
  const key = view in titles ? view as keyof typeof titles : "accounts";
  return <><div style={{padding:"8px 20px",background:"#fff6dc",fontSize:12}}>独立 UI 测试 · 所有数据均为虚构，提交仅写入内存 <button onClick={()=>{failNext=true;setAction("下一次请求将失败");}}>模拟请求失败</button> <button onClick={()=>{empty=!empty;setAction(empty?"空数据模式：重新进入页面生效":"已恢复示例数据");}}>切换空数据</button> <button onClick={()=>{account={...account,active_role:user.active_role === "patient" ? "caregiver" : "patient"};setUser(account);}}>切换测试身份</button> <button onClick={()=>render(value=>value+1)}>查看测试请求</button><span role="status">{action}</span><details><summary>请求记录</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(requests,null,2)}</pre></details></div><WorkspaceShell displayName={user.display_name} roleLabel={user.active_role === "patient" ? "病人身份" : "护理身份"} isAdmin={false} activeView={key} onNavigate={setView} onLogout={()=>setAction("已触发退出入口")}><div className="care-heading"><h1>{titles[key][0]}</h1><p>{titles[key][1]}</p></div>{key === "accounts" ? <AccountsPage key={user.active_role} account={user} setAccount={setUser} /> : key === "jobs" ? <JobsPage key={user.active_role} account={user} onOpenChat={()=>setAction("已触发聊天入口")} /> : <ConsultationPage account={user} />}<footer className="ov-footer">DoctorCarePlatform · UI 测试示例</footer></WorkspaceShell></>;
}
createRoot(document.getElementById("root")!).render(<StrictMode><Fixture /></StrictMode>);
