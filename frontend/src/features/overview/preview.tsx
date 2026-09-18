import { useEffect, useState } from "react";
import { hydrateRoot } from "react-dom/client";
import { X } from "lucide-react";
import OverviewPage from "./OverviewPage";
import type { View } from "../../types";

const labels: Record<View, string> = {
  overview: "流程总览", accounts: "我的信息", jobs: "招聘页面", profiles: "应聘发布",
  chat: "聊天沟通", consultation: "智能问诊", verification: "审核管理", knowledge: "知识库",
};
const initialIllustration = document.querySelector<HTMLImageElement>(".ov-hero-image")!.src;
const initialDate = document.querySelector(".ov-date")?.textContent || undefined;

function OverviewPreview() {
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 6000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  return <>
    <OverviewPage displayName="管理员" roleLabel="平台管理" isAdmin preview illustrationUrl={initialIllustration} dateLabel={initialDate}
      onNavigate={(view) => {
        if (view === "overview") { window.scrollTo({ top: 0, behavior: "auto" }); return; }
        setNotice(`这是流程总览页的独立预览。「${labels[view]}」入口可在项目中打开。`);
      }}
      onLogout={() => setNotice("当前为独立设计预览，没有登录中的账号。")}
    />
    {notice && <div className="ov-preview-toast" role="status"><span>{notice}</span><button type="button" aria-label="关闭提示" onClick={() => setNotice("")}><X size={17} /></button></div>}
  </>;
}

hydrateRoot(document.getElementById("overview-root")!, <OverviewPreview />);
