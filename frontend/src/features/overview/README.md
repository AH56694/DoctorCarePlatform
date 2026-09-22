# 流程总览界面

`OverviewPage.tsx` 负责流程总览内容，通过 `../workspace/WorkspaceShell.tsx` 复用导航和顶部栏。`overview.css` 的页面规则限定在 `.overviewPage` 内，共享外壳样式位于 `../workspace/care-pages.css`。账号、招聘和问诊页面分别位于相邻的功能目录。

统计、招聘动态与管理员待办保持为明确标注的示例数据；没有新增业务接口或用示例数据覆盖实际记录。按钮通过 `onNavigate` 接入现有视图，退出通过 `onLogout` 接入原会话管理。普通用户不展示管理员导航。

## 独立 HTML

在 `frontend` 目录执行 `npm run export:overview`，在项目根目录生成 `overview.html`（即 `DoctorCarePlatform/overview.html`）。文件内嵌脚本、CSS、图标和插画，无需网络、服务端或登录即可打开。招聘状态筛选、移动导航和提醒弹层可操作；其他页面的入口显示预览说明。

HTML 使用 `preview.tsx` 引用同一个页面组件生成，避免另写一套页面导致样式偏离。更改设计后重新导出即可；`npm run build` 也会先更新 HTML。

Git 仅保存页面源码、插画和导出脚本；生成的根目录 `overview.html` 已忽略，仍可在本地生成和交付。

文件包含预先渲染的 HTML 正文，禁用脚本仍可查看静态页面。启用脚本后接管筛选和导航交互；内容安全策略禁止预览向外发送网络请求。

## 验证方式

从仓库根目录执行 `npm --prefix frontend test` 和 `npm --prefix frontend run build`。构建包含 TypeScript 检查、离线页面导出及 Vite 产物；导出脚本同时检查普通用户页面不包含审核管理与知识库导航。

视觉验收应覆盖桌面、390px 和 320px 手机布局，以及招聘筛选、预览入口反馈、提醒弹层、移动导航和 Escape 关闭。测试通过数量与验收记录以对应提交的运行结果为准。

## 插画素材

`public/images/overview-care-illustration.png` 使用内置 imagegen 工具根据已确认的样例生成。素材需求：浅薄荷绿色背景，护理人员陪伴银发长者，右侧构图、柔和窗光、左侧留白，不含文字、界面或标志。
