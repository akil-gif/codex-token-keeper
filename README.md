# Codex Token Keeper

自动保鲜 Codex / ChatGPT OAuth Token 的服务，避免 token 过期。

## 功能

- 自动定时刷新 access_token（默认每 8 小时）
- 支持 refresh_token 和完整 auth.json 两种导入方式
- Web 管理界面（查看状态、手动刷新、导出）
- 兼容 Codex CLI `~/.codex/auth.json` 导出格式
- Docker 一键部署

## 本地运行

```bash
pip install -r requirements.txt
cp .env.example .env
# 修改 .env 里的 ADMIN_PASSWORD
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker 部署

```bash
docker compose up -d
```

## 部署到 ClawCloud Run（推荐，每月免费 $5）

### 第一步：推送到 GitHub

```bash
cd codex-token-keeper
git init
git add -A
git commit -m "feat: codex token keeper"
# 在 GitHub 创建一个新仓库（比如 codex-token-keeper），然后：
git remote add origin https://github.com/你的用户名/codex-token-keeper.git
git push -u origin main
```

### 第二步：在 ClawCloud Run 创建应用

1. 打开 https://console.run.claw.cloud ，用 **GitHub 账号登录**（需注册满 180 天才能领 $5/月免费额度）
2. 进入 **App Launchpad** → 点击 **Create App**
3. 填写配置：
   - **App Name**: `codex-token-keeper`
   - **Image**: 点 **Build from Git**，选你的 GitHub 仓库 `codex-token-keeper`
     - Branch: `main`
     - Build Path: `/`
     - Dockerfile 路径: `Dockerfile`
   - **CPU**: `0.1` vCPU（够用，省钱）
   - **Memory**: `256` MB
   - **Container Port**: `8000`
   - **Environment Variables**:
     - `ADMIN_PASSWORD` = `你的强密码`（必改！这是管理后台登录密码）
     - `REFRESH_INTERVAL_HOURS` = `8`（可选，默认 8 小时刷新一次）
     - `PROXY_URL` = （留空，除非你需要代理访问 OpenAI）
   - **Persistent Storage**: 点 **Add Volume**
     - Mount Path: `/app/data`
     - Size: `1` GB（存账号 JSON，足够）
4. 点 **Deploy**

### 第三步：开启外网访问

1. 部署成功后，在应用详情页点 **Network** → **Enable Public Access**
2. 会分配一个域名，如 `codex-token-keeper-xxxx.run.claw.cloud`
3. 浏览器打开这个域名，输入你设的 `ADMIN_PASSWORD` 登录

### 资源消耗估算

| 资源 | 配置 | 月费用 |
|------|------|--------|
| CPU | 0.1 vCPU × 24h × 30d | ~$2.16 |
| 内存 | 256MB × 24h × 30d | ~$0.56 |
| 存储 | 1GB | ~$0.08 |
| **合计** | | **~$2.80/月** |

$5 免费额度足够，还有余量。

## 部署到 Zeabur（备选，有 Fair Use 风险）

```bash
# 方式1：通过 Zeabur CLI
npx zeabur deploy

# 方式2：Dashboard
# 1. https://zeabur.com/projects → New Project
# 2. Deploy from GitHub → 选你的仓库
# 3. 添加环境变量 ADMIN_PASSWORD
# 4. 自动识别 Dockerfile 构建
```

> ⚠️ Zeabur 的 Fair Use 条款禁止 Proxy 服务，token 刷新服务属于灰色地带，建议优先用 ClawCloud Run。

## 使用

1. 浏览器打开 `http://localhost:8000`
2. 输入管理员密码登录
3. 在输入框粘贴 refresh_token 或完整 auth.json，点添加
4. 系统会自动刷新，也可手动点「刷新」按钮
5. 点「导出」下载最新的 auth.json，覆盖到 `~/.codex/auth.json`

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/login | 登录 |
| GET | /api/accounts | 列出所有账号 |
| POST | /api/accounts/import | 批量导入 |
| POST | /api/accounts/{id}/refresh | 手动刷新 |
| POST | /api/refresh-all | 刷新全部 |
| GET | /api/accounts/{id}/export | 导出 auth.json |
| DELETE | /api/accounts/{id} | 删除账号 |
