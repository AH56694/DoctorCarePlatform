import { renderToString } from "react-dom/server";
import OverviewPage from "../src/features/overview/OverviewPage";

export function renderOverview(illustrationUrl: string, isAdmin = true) {
  return renderToString(<OverviewPage
    displayName={isAdmin ? "管理员" : "体验用户"}
    roleLabel={isAdmin ? "平台管理" : "病人"}
    isAdmin={isAdmin} preview illustrationUrl={illustrationUrl}
    onNavigate={() => {}} onLogout={() => {}}
  />);
}
