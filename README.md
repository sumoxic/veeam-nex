# Veeam Inspection Platform（Veeam 巡检平台）

面向 **Veeam Backup & Replication（VBR）** 的巡检与可视化平台。平台通过 VBR REST API 采集基础设施清单，使用可配置的规则引擎发现风险，并提供巡检驾驶舱、告警通知、发现项闭环与带审计的远程操作。

支持 **VBR 12 / VBR 13** 双版本，自动识别 REST API 版本；也可在创建目标时手动指定版本。

---

## 功能特性

- **巡检目标管理**：多目标接入、连通性测试、定时排期、版本偏好（自动检测 / VBR 12 / VBR 13）。
- **全量数据采集**：列表端点自动翻页（单页 200 条），以 VBR 服务器时钟作为本轮时间基准。
- **规则引擎**：覆盖服务器、许可、作业、还原点、存储库、代理、受管服务器、受保护对象等类别；支持全局阈值与目标级覆盖。
- **巡检驾驶舱**：按巡检轮次回看当时的作业状态、仓库容量、还原点、会话与发现项，而非当前实时状态。
- **发现项闭环**：待处理 / 已确认 / 已解决，保留出现次数、首次/最近发现时间与历史事件。
- **告警通知**：告警规则匹配 + SMTP / Webhook 渠道，支持冷却时间、去重窗口与恢复通知。
- **远程操作**：作业启动/重试、代理启停采用「建单 → 一次性令牌确认 → 执行」两步模型，全流程落审计；VBR 12 不支持的操作会在执行前明确拒绝。
- **权限与安全**：JWT 认证、RBAC（admin / operator / viewer）、VBR 与 SMTP 凭据使用 Fernet 加密存储。
- **版本标识**：目标、巡检记录、详情页与驾驶舱均展示 VBR 大版本、构建号与 REST API 版本。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.12、FastAPI、SQLAlchemy 2、Alembic、MySQL 8、APScheduler、PyJWT、cryptography、loguru |
| 前端 | Vue 3 + TypeScript、Vite 5、Element Plus、Pinia、Vue Router、ECharts |
| 测试 | pytest（后端）、vue-tsc 类型检查 + Vite 生产构建（前端） |

## 目录结构

```
veeam-nex/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST 路由（targets / inspections / findings / rules / alerts ...）
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── services/        # 业务服务（巡检、告警、操作、指标等）
│   │   ├── vbr/             # VBR 客户端、采集器、端点定义、翻页、规则检查
│   │   ├── scheduler/       # APScheduler 定时巡检
│   │   ├── security/        # 口令哈希、凭据加密、JWT
│   │   ├── db/              # 会话、种子数据
│   │   └── config.py        # 环境变量配置
│   ├── alembic/             # 数据库迁移
│   ├── scripts/             # 管理员初始化、密钥生成
│   ├── tests/               # pytest 测试
│   ├── .env.example         # 配置模板
│   └── run.sh               # 开发模式启动脚本
└── frontend/
    ├── src/
    │   ├── api/             # 接口封装与类型定义
    │   ├── components/      # 通用组件、图表、版本标签
    │   ├── views/           # 页面（目标 / 巡检 / 驾驶舱 / 规则 / 告警 / 审计 ...）
    │   ├── stores/          # Pinia 状态
    │   └── utils/           # 格式化、版本、表格工具
    └── vite.config.ts       # 开发服务器与 /api 代理
```

## 快速开始

### 环境要求

- Python **3.11+**（当前开发与验证使用 3.12）
- Node.js **18+**
- MySQL **8.0**，需预先创建数据库 `veeam_inspection`
- 可访问的 VBR 服务器（REST API 默认端口 `9419`）

> 平台在配置层强制 `DB_NAME=veeam_inspection`，避免误写同实例上的其他业务库。

### 1. 启动后端

```bash
cd backend

# 创建虚拟环境并安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 准备配置
cp .env.example .env
chmod 600 .env

# 生成凭据加密密钥与 JWT 密钥，将输出填入 .env
python scripts/generate_keys.py

# 按需修改数据库连接等信息后，执行迁移
alembic upgrade head

# 创建管理员账号（首次）
python scripts/bootstrap_admin.py --username admin --password 'Admin@12345'

# 启动开发服务（0.0.0.0:18000，热重载）
./run.sh
```

启动后可访问：

- 健康检查：<http://127.0.0.1:18000/api/v1/system/health>
- Swagger 文档：<http://127.0.0.1:18000/docs>
- OpenAPI：<http://127.0.0.1:18000/openapi.json>

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

开发服务器监听 `0.0.0.0:5174`，并将 `/api` 代理到 `http://127.0.0.1:18000`。如后端地址不同，可通过环境变量覆盖：

```bash
VITE_API_TARGET=http://192.168.1.10:18000 npm run dev
```

浏览器打开 <http://localhost:5174>，使用上一步创建的管理员账号登录。

## 配置说明

所有配置从 `backend/.env` 或环境变量读取，模板见 `backend/.env.example`。

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `DB_HOST` / `DB_PORT` | MySQL 地址 | `10.0.54.101:3306` |
| `DB_USER` / `DB_PASSWORD` | MySQL 账号 | `root` / 空 |
| `DB_NAME` | 数据库名，**只允许** `veeam_inspection` | `veeam_inspection` |
| `API_HOST` / `API_PORT` | 后端监听地址 | `0.0.0.0:18000` |
| `SECRET_KEY` | Fernet 凭据加密密钥（丢失将无法解密已存口令） | 空 |
| `PREVIOUS_SECRET_KEYS` | 轮换期间的旧密钥，逗号分隔 | 空 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 空 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 访问令牌有效期（分钟） | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | 刷新令牌有效期（天） | `7` |
| `SCHEDULER_ENABLED` | 是否启用定时巡检调度器 | `true` |
| `DEFAULT_TIMEZONE` | 默认排期时区 | `Asia/Shanghai` |
| `DEFAULT_MAX_BACKUP_AGE_HOURS` | 默认备份时效阈值（小时） | `48` |
| `DEFAULT_MIN_FREE_PERCENT` | 默认仓库最小剩余空间百分比 | `20` |
| `DEFAULT_MIN_FREE_GB` | 默认仓库最小剩余空间（GB） | `20` |
| `INSPECTION_RETENTION_DAYS` | 巡检数据保留天数 | `90` |

## VBR 版本兼容

平台在认证后自动探测 VBR 支持的 REST API 版本：

| VBR 大版本 | REST API 版本 |
| --- | --- |
| VBR 13 | `1.3-rev2` |
| VBR 12 | `1.2-rev1` |

- 目标的 `version_preference` 可取 `auto`（默认）、`12`、`13`；手动指定后跳过自动探测。
- `auto` 模式依次尝试 `1.3-rev2` → `1.2-rev1`，探测结果缓存在目标上，并用构建号在界面显示「VBR 12 / VBR 13」。
- VBR 12 的差异已做兼容处理：
  - 代理列表改用 `/backupInfrastructure/proxies`（无 `/proxies/states`），在线状态由受管服务器推断；
  - `serverTime` 的时区字段使用 `timeZone`（VBR 13 为 `ianaTimeZoneId`）；
  - 不支持作业重试与代理启停，相关远程操作会返回明确的版本不支持错误；
  - 部分对象字段（如路径、大小、最近运行失败标记）缺失时按空值展示。
- 列表端点统一使用 `skip` / `limit` 翻页，单页 200 条，最多 50 页；超限会记录采集错误而不是静默截断。
- 许可受限的端点会降级为空数据并记录错误，不会中断整轮巡检；认证失败则整轮失败。

## 测试

```bash
# 后端单元测试
cd backend
PYTHONPATH=. .venv/bin/python -m pytest -q

# 前端类型检查与生产构建
cd frontend
npm run type-check
npm run build
```

## 生产部署

1. **构建前端静态资源**

   ```bash
   cd frontend
   npm ci
   npm run build   # 输出到 frontend/dist
   ```

2. **启动后端**（示例 systemd 单元，按实际路径调整）

   ```ini
   [Unit]
   Description=Veeam Inspection Platform API
   After=network.target

   [Service]
   WorkingDirectory=/opt/veeam-nex/backend
   Environment=PYTHONPATH=.
   ExecStart=/opt/veeam-nex/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 18000
   Restart=always
   User=veeam

   [Install]
   WantedBy=multi-user.target
   ```

3. **Nginx 反向代理**：托管 `frontend/dist`，并将 `/api` 转发到 `http://127.0.0.1:18000`。

4. **升级时执行迁移**：`cd backend && alembic upgrade head`。

### 安全建议

- `backend/.env` 权限设为 `600`，切勿提交到版本库；`SECRET_KEY` / `JWT_SECRET_KEY` 必须使用独立随机值。
- 首次登录后立即修改管理员初始口令。
- 生产环境建议启用 HTTPS，并限制数据库与 VBR 接口的网络访问范围。
- 远程操作采用 15 分钟有效的一次性确认令牌，所有操作均写入审计表，请定期审查「操作审计」页面。
