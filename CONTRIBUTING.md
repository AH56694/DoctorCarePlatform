# 开发与变更约定

项目按可独立验证的小批次迭代。业务接口保持 `/api/v1` 兼容；破坏性变更需要新版本、迁移说明和前端升级方案。

## 代码边界

- 路由负责参数、身份和 HTTP 响应；新增业务流程放入 `backend/app/services`，避免继续扩大路由文件。
- 新增接口必须声明访问角色及对象归属检查，调用者不能通过请求体决定自己的身份或管理员权限。
- 同步数据库调用使用普通 `def` 路由；含外部异步调用的流程应分离短事务，不跨模型调用长时间占用连接。
- 会话对象不能跨并发任务共享；业务写入由明确的事务边界提交，缓存不能承担唯一的数据来源。
- 前端请求统一经过 `frontend/src/lib/api.ts`，会话管理经过 `lib/session.ts`；按功能逐步拆分现有页面。
- 应用日志禁止记录密码、令牌、姓名证件、完整问题、病历或附件内容；用请求编号和业务事件定位问题。
- 不提交运行数据库、真实账号或问诊数据、密钥、备份和模型索引。生成的 `overview.html` 保留本地，通过源码及导出脚本复现。
- `.gitignore` 不会移除已提交的历史数据。发现此类问题时先记录范围，再单独协调历史清理；本次发现见 `docs/远程仓库推送检查.md`。

## 提交前验证

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pytest python-service/tests -q
.\.venv\Scripts\python.exe -m ruff check backend python-service tests --select E9,F63,F7,F82
npm --prefix frontend test
npm --prefix frontend run build
.\scripts\tests\test-local-processes.ps1
```

默认后端测试会跳过需要隔离 MySQL 的集成测试。CI 提供 MySQL 8.4，执行实际迁移和数据库约束测试。不要把 `TEST_MYSQL_URL` 指向业务数据库。

## 依赖维护

Python 部署锁文件面向 Linux x86_64、Python 3.11 和 CPU PyTorch。修改依赖输入后，用 uv 重新生成锁文件并重新执行安全审计；不能仅修改输入文件而继续使用旧锁文件。

```powershell
python scripts/lock-dependencies.py
python scripts/audit-dependencies.py requirements.lock --output backend-dependency-audit.json
python scripts/audit-dependencies.py python-service/requirements.lock --output ai-dependency-audit.json
```

前端修改依赖后更新 `package-lock.json`，CI 和容器统一使用 `npm ci`。Dependabot 的 Python 更新仍需人工重建部署锁文件。不要使用强制跳过漏洞检查作为常规发布方式。

## 数据库变更

MySQL 使用 `alembic.mysql.ini` 和 `migrations/mysql_versions`。历史 `migrations/versions` 为 PostgreSQL 迁移链，不能对 MySQL 执行。

`20260905_baseline.sql` 是发布基线，第一次正式部署后不得修改。后续追加迁移；先增加兼容字段，再迁移数据，最后删除旧字段。每次迁移说明数据量影响、锁表风险及恢复方式。已有库首次纳入迁移管理必须备份、比对并人工验收，不能直接 `stamp head`。

## 合并与发布

在代码托管平台启用受保护主分支，并把 CI 中的后端、AI、前端、MySQL 和 Windows 启停安全作业设为必需检查。仓库配置文件本身不会自动开启分支保护。生产发布流程及尚未关闭的上线问题见 `docs/生产部署与运维手册.md` 和 `docs/企业级审计与整改报告.md`。
