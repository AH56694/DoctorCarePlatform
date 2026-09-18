import type { RoleName } from "../types";

export function roleLabel(role: RoleName) {
  if (role === "admin") {
    return "管理员";
  }
  return role === "patient" ? "病人" : "护理";
}

export function statusLabel(status: string | undefined | null) {
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
