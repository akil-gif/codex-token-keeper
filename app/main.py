"""Codex Token Keeper - 主程序"""
from __future__ import annotations

import asyncio
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.config import config
from app.logger import logger
from app.routes import router
from app.scheduler import scheduler_loop, startup_refresh

app = FastAPI(title="Codex Token Keeper", version="1.0.0")

app.state.session_token = uuid.uuid4().hex
app.include_router(router)


@app.on_event("startup")
async def on_startup():
    logger.info(f"Starting Codex Token Keeper on {config.HOST}:{config.PORT}")
    logger.info(f"Data dir: {config.DATA_DIR}")
    asyncio.create_task(startup_refresh())
    asyncio.create_task(scheduler_loop())


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    token = request.cookies.get("session", "")
    expected = app.state.session_token
    if token == expected:
        return HTMLResponse(DASHBOARD_HTML)
    return HTMLResponse(LOGIN_HTML)


LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Codex Token Keeper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,-apple-system,sans-serif}
body{background:#0f1117;color:#e4e4e7;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#1a1d27;border:1px solid #2a2d37;border-radius:12px;padding:40px;width:360px}
h1{font-size:20px;margin-bottom:8px;text-align:center}
p.sub{color:#71717a;font-size:13px;text-align:center;margin-bottom:24px}
input{width:100%;padding:10px 14px;background:#0f1117;border:1px solid #2a2d37;border-radius:8px;color:#e4e4e7;font-size:14px;margin-bottom:16px}
button{width:100%;padding:10px;background:#3b82f6;border:none;border-radius:8px;color:#fff;font-size:14px;cursor:pointer}
button:hover{background:#2563eb}
.err{color:#ef4444;font-size:12px;margin-top:8px;text-align:center}
</style>
</head>
<body>
<div class="card">
<h1>Token Keeper</h1>
<p class="sub">Codex OAuth Token 自动保鲜</p>
<input type="password" id="pw" placeholder="管理员密码" onkeydown="if(event.key==='Enter')doLogin()">
<button onclick="doLogin()">登录</button>
<div class="err" id="e"></div>
</div>
<script>
async function doLogin(){
  const pw=document.getElementById('pw').value;
  const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
  if(r.ok){const d=await r.json();document.cookie='session='+d.token+';path=/';location.reload();}
  else{document.getElementById('e').textContent='密码错误';}
}
</script>
</body>
</html>"""


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Codex Token Keeper</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,-apple-system,sans-serif}
body{background:#0f1117;color:#e4e4e7}
.nav{background:#1a1d27;border-bottom:1px solid #2a2d37;padding:12px 24px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:10}
.nav h1{font-size:16px}
.stats{font-size:12px;color:#71717a;margin-left:auto}
.btn{padding:6px 14px;border-radius:6px;border:none;cursor:pointer;font-size:13px}
.btn-blue{background:#3b82f6;color:#fff}.btn-blue:hover{background:#2563eb}
.btn-green{background:#22c55e;color:#fff}.btn-green:hover{background:#16a34a}
.btn-red{background:#ef4444;color:#fff}.btn-red:hover{background:#dc2626}
.btn-gray{background:#3f3f46;color:#fff}.btn-gray:hover{background:#52525b}
.btn-sm{padding:4px 10px;font-size:12px}
.container{max-width:1100px;margin:24px auto;padding:0 16px}
.toolbar{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.add-box{background:#1a1d27;border:1px solid #2a2d37;border-radius:10px;padding:16px;margin-bottom:16px}
.add-box textarea{width:100%;background:#0f1117;border:1px solid #2a2d37;border-radius:6px;color:#e4e4e7;padding:10px;font-size:13px;font-family:monospace;resize:vertical}
.add-box input{width:100%;background:#0f1117;border:1px solid #2a2d37;border-radius:6px;color:#e4e4e7;padding:8px 10px;font-size:13px;margin-bottom:8px}
table{width:100%;border-collapse:collapse;background:#1a1d27;border:1px solid #2a2d37;border-radius:10px;overflow:hidden}
th{text-align:left;padding:10px 12px;background:#22252f;font-size:12px;color:#a1a1aa;text-transform:uppercase}
td{padding:10px 12px;border-top:1px solid #2a2d37;font-size:13px;vertical-align:top}
.tag{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;background:#3f3f46}
.tag-free{background:#52525b}.tag-plus{background:#0891b2}.tag-pro{background:#7c3aed}.tag-team{background:#ea580c}
.badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px}
.b-active{background:#166534;color:#4ade80}.b-error{background:#7f1d1d;color:#fca5a5}.b-pending{background:#3f3f46;color:#a1a1aa}
</style>
</head>
<body>
<div class="nav">
<h1>Token Keeper</h1>
<span id="stats" class="stats">加载中...</span>
<button class="btn btn-green" onclick="refreshAll()">刷新全部</button>
<button class="btn btn-gray" onclick="exportAll()">导出全部</button>
</div>
<div class="container">
<div class="add-box">
<input id="newName" placeholder="备注名（可选）">
<textarea id="newToken" rows="4" placeholder="粘贴 refresh_token 或完整 auth.json 内容"></textarea>
<div style="margin-top:8px"><button class="btn btn-blue" onclick="addAccount()">添加账号</button></div>
</div>
<table>
<thead><tr><th>账号</th><th>套餐</th><th>状态</th><th>过期时间</th><th>上次刷新</th><th>Access Token</th><th>操作</th></tr></thead>
<tbody id="tb"><tr><td colspan="7" style="text-align:center;color:#71717a;padding:30px">加载中...</td></tr></tbody>
</table>
</div>
<script>
const TK=()=>document.cookie.split(';').map(c=>c.trim()).find(c=>c.startsWith('session='))?.split('=')[1]||'';
const auth=()=>({'Authorization':'Bearer '+TK()});
const fmtTime=t=>{if(!t)return'—';const d=new Date(t*1000);return d.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})};
const badge=s=>{const m={active:'b-active',error:'b-error',pending:'b-pending',disabled:'b-pending'};return `<span class="badge ${m[s]||'b-pending'}">${s}</span>`};
const planTag=p=>{if(!p)return'—';return `<span class="tag tag-${p}">${p}</span>`};
async function loadAccounts(){
  const r=await fetch('/api/accounts',{headers:auth()});
  if(r.status===401){location.reload();return}
  const data=await r.json();
  const tb=document.getElementById('tb');
  if(!data.length){tb.innerHTML='<tr><td colspan=7 style="text-align:center;color:#71717a;padding:30px">暂无账号，请在上方添加</td></tr>';return}
  tb.innerHTML=data.map(a=>`<tr>
<td><div>${a.name||a.email||'—'}</div><div style="font-size:11px;color:#71717a">${a.email||''}</div></td>
<td>${planTag(a.plan_type)}</td>
<td>${badge(a.status)}</td>
<td style="font-size:12px">${a.expires_at?fmtTime(a.expires_at):'—'}${a.needs_refresh?'<br><span style="color:#fde047">需刷新</span>':''}</td>
<td style="font-size:12px">${fmtTime(a.last_refresh)}</td>
<td style="font-size:11px;color:#71717a;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${a.access_token||'—'}</td>
<td style="white-space:nowrap">
<button class="btn btn-blue btn-sm" onclick="refreshOne('${a.id}')">刷新</button>
<a class="btn btn-gray btn-sm" style="display:inline-block;text-decoration:none" href="/api/accounts/${a.id}/export?_t=${Date.now()}" target="_blank">导出</a>
<button class="btn btn-red btn-sm" onclick="delAccount('${a.id}')">删除</button>
</td></tr>`).join('');
}
async function loadStats(){
  const r=await fetch('/api/stats',{headers:auth()});
  if(r.ok){const d=await r.json();document.getElementById('stats').textContent=`共 ${d.total} 个 · ${d.active} 活跃 · ${d.with_token} 有Token`;}
}
async function addAccount(){
  const name=document.getElementById('newName').value.trim();
  const raw=document.getElementById('newToken').value.trim();
  if(!raw)return;
  let body;
  try{JSON.parse(raw);body={auth_json:raw};}catch{body={refresh_tokens:[raw]};}
  if(name){body.name=name;}
  const r=await fetch('/api/accounts/import',{method:'POST',headers:{'Content-Type':'application/json',...auth()},body:JSON.stringify(body)});
  if(r.ok){document.getElementById('newName').value='';document.getElementById('newToken').value='';loadAccounts();loadStats();}
  else{alert('添加失败');}
}
async function refreshOne(id){
  const r=await fetch(`/api/accounts/${id}/refresh`,{method:'POST',headers:auth()});
  if(r.ok){loadAccounts();loadStats();}
}
async function refreshAll(){
  const r=await fetch('/api/refresh-all',{method:'POST',headers:auth()});
  if(r.ok){const d=await r.json();alert(`刷新完成: ${d.success}成功 / ${d.failed}失败`);loadAccounts();loadStats();}
}
async function delAccount(id){
  if(!confirm('确认删除？'))return;
  const r=await fetch(`/api/accounts/${id}`,{method:'DELETE',headers:auth()});
  if(r.ok){loadAccounts();loadStats();}
}
function exportAll(){
  fetch('/api/accounts',{headers:auth()}).then(r=>r.json()).then(data=>{data.forEach(a=>{if(a.access_token)window.open(`/api/accounts/${a.id}/export?_t=${Date.now()}`)});});
}
loadAccounts();loadStats();
setInterval(()=>{loadAccounts();loadStats();},30000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
