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

## ClawCloud Run 部署

1. 登录 [ClawCloud Run](https://console.run.claw.cloud)
2. App Launchpad → Create App
3. 镜像：构建后推送到 Docker Hub，或直接用 GitHub 仓库自动构建
4. 配置：
   - CPU: 0.1 vCPU
   - 内存: 256MB
   - 端口: 8000
   - 环境变量：`ADMIN_PASSWORD=你的密码`
   - 持久化存储：挂载 `/app/data`

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
