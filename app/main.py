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
.btn{padding:6px 14px;border-radius:6px;border:none;cursor:pointer;font-size:13px;transition:.15s}
.btn:disabled{opacity:.5;cursor:not-allowed}
.btn-blue{background:#3b82f6;color:#fff}.btn-blue:hover:not(:disabled){background:#2563eb}
.btn-green{background:#22c55e;color:#fff}.btn-green:hover:not(:disabled){background:#16a34a}
.btn-red{background:#ef4444;color:#fff}.btn-red:hover:not(:disabled){background:#dc2626}
.btn-gray{background:#3f3f46;color:#fff}.btn-gray:hover:not(:disabled){background:#52525b}
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
.toast{position:fixed;top:16px;right:16px;z-index:999;display:flex;flex-direction:column;gap:8px;pointer-events:none}
.toast-item{padding:10px 20px;border-radius:8px;font-size:13px;box-shadow:0 4px 12px rgba(0,0,0,.4);animation:slideIn .2s ease;pointer-events:auto;min-width:200px;text-align:center}
.toast-info{background:#2563eb;color:#fff}
.toast-ok{background:#16a34a;color:#fff}
.toast-err{background:#dc2626;color:#fff}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
</style>
</head>
<body>
<div class="nav">
<h1>Token Keeper</h1>
<span id="stats" class="stats">加载中...</span>
<button class="btn btn-green" id="btnRefreshAll" onclick="refreshAll()">刷新全部</button>
<button class="btn btn-blue" id="btnRefreshQueryAll" onclick="refreshQueryAll()">刷新+查额度</button>
<button class="btn btn-gray" onclick="exportAll()">导出全部</button>
</div>
<div class="toast" id="toastBox"></div>
<div class="container">
<div class="add-box">
<input id="newName" placeholder="备注名（可选）">
<textarea id="newToken" rows="4" placeholder="粘贴 refresh_token 或完整 auth.json 内容"></textarea>
<div style="margin-top:8px"><button class="btn btn-blue" id="btnAdd" onclick="addAccount()">添加账号</button></div>
</div>
<table>
<thead><tr><th>账号</th><th>套餐</th><th>额度（重置时间）</th><th>状态</th><th>过期时间</th><th>上次刷新</th><th>操作</th></tr></thead>
<tbody id="tb"><tr><td colspan="7" style="text-align:center;color:#71717a;padding:30px">加载中...</td></tr></tbody>
</table>
</div>
<script>
const TK=()=>document.cookie.split(';').map(c=>c.trim()).find(c=>c.startsWith('session='))?.split('=')[1]||'';
const auth=()=>({'Authorization':'Bearer '+TK()});

function toast(msg, type='info', duration=2500){
  const box=document.getElementById('toastBox');
  const el=document.createElement('div');
  el.className='toast-item toast-'+type;
  el.textContent=msg;
  box.appendChild(el);
  setTimeout(()=>{el.style.transition='opacity .3s';el.style.opacity='0';setTimeout(()=>el.remove(),300)},duration);
}

const fmtTime=t=>{if(!t)return'—';const d=new Date(t*1000);return d.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})};
const fmtAgo=t=>{if(!t)return'—';const s=(Date.now()/1000-t);if(s<60)return'刚刚';if(s<3600)return Math.floor(s/60)+'分钟前';if(s<86400)return Math.floor(s/3600)+'小时前';return Math.floor(s/86400)+'天前'};
const badge=s=>{const m={active:'b-active',error:'b-error',pending:'b-pending',disabled:'b-pending'};return`<span class="badge ${m[s]||'b-pending'}">${s}</span>`};
const planTag=p=>{if(!p)return'—';return`<span class="tag tag-${p}">${p}</span>`};

const usageCache={};
const fmtPct=p=>p!=null?Math.round(p)+'%':'—';
const fmtReset=s=>{if(!s||s<=0)return'';const d=new Date(Date.now()+s*1000);return d.toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})+'可重置'};
const quotaCell=a=>{
  const u=usageCache[a.id];
  if(!u)return'<span style="color:#71717a">未查询</span>';
  if(u.error)return`<span style="color:#fca5a5;font-size:11px">${u.error.substring(0,30)}</span>`;
  let html='';
  if(u.rate_limit_reached){html+='<span style="color:#fca5a5;font-size:11px">已达限速</span><br>'}
  if(u.primary_used_percent!=null){
    const p=u.primary_used_percent;const c=p>=80?'#fca5a5':p>=50?'#fde047':'#4ade80';
    html+=`<div style="font-size:11px">5h: ${fmtPct(p)}`;
    if(u.primary_reset_after_seconds)html+=` · ${fmtReset(u.primary_reset_after_seconds)}`;
    html+='</div><div style="width:80px;height:4px;background:#2a2d37;border-radius:2px;margin:2px 0"><div style="width:'+Math.min(p,100)+'%;height:100%;background:'+c+';border-radius:2px"></div></div>';
  }
  if(u.spark_7d_used_percent!=null){
    const p=u.spark_7d_used_percent;const c=p>=80?'#fca5a5':p>=50?'#fde047':'#4ade80';
    html+=`<div style="font-size:11px">7d: ${fmtPct(p)}`;
    if(u.spark_7d_reset_after_seconds)html+=` · ${fmtReset(u.spark_7d_reset_after_seconds)}`;
    html+='</div><div style="width:80px;height:4px;background:#2a2d37;border-radius:2px;margin:2px 0"><div style="width:'+Math.min(p,100)+'%;height:100%;background:'+c+';border-radius:2px"></div></div>';
  }
  return html||'<span style="color:#71717a">无数据</span>';
};

async function loadAccounts(){
  const r=await fetch('/api/accounts',{headers:auth()});
  if(r.status===401){location.reload();return}
  const data=await r.json();
  const tb=document.getElementById('tb');
  if(!data.length){tb.innerHTML='<tr><td colspan=7 style="text-align:center;color:#71717a;padding:30px">暂无账号，请在上方添加</td></tr>';return}
  tb.innerHTML=data.map(a=>`<tr>
<td><div>${a.name||a.email||'—'}</div><div style="font-size:11px;color:#71717a">${a.email||''}</div></td>
<td>${planTag(a.plan_type)}</td>
<td>${quotaCell(a)}</td>
<td>${badge(a.status)}</td>
<td style="font-size:12px">${a.expires_at?fmtTime(a.expires_at):'—'}${a.needs_refresh?'<br><span style="color:#fde047">需刷新</span>':''}</td>
<td style="font-size:12px" title="${fmtTime(a.last_refresh)}">${fmtAgo(a.last_refresh)}</td>
<td style="white-space:nowrap">
<button class="btn btn-blue btn-sm" id="r_${a.id}" onclick="refreshOne('${a.id}')">刷新</button>
<button class="btn btn-gray btn-sm" id="u_${a.id}" onclick="usageOne('${a.id}')">查额度</button>
<a class="btn btn-gray btn-sm" style="display:inline-block;text-decoration:none" href="/api/accounts/${a.id}/export?_t=${Date.now()}" target="_blank">导出</a>
<button class="btn btn-red btn-sm" onclick="delAccount('${a.id}')">删除</button>
</td></tr>`).join('');
}
async function loadStats(){
  const r=await fetch('/api/stats',{headers:auth()});
  if(r.ok){const d=await r.json();document.getElementById('stats').textContent=`共 ${d.total} 个 · ${d.active} 活跃 · ${d.with_token} 有Token`;}
}
async function addAccount(){
  const btn=document.getElementById('btnAdd');btn.disabled=true;
  const name=document.getElementById('newName').value.trim();
  const raw=document.getElementById('newToken').value.trim();
  if(!raw){toast('请输入 refresh_token 或 auth.json','err');btn.disabled=false;return}
  let body;
  try{JSON.parse(raw);body={auth_json:raw};}catch{body={refresh_tokens:[raw]};}
  if(name){body.name=name;}
  const r=await fetch('/api/accounts/import',{method:'POST',headers:{'Content-Type':'application/json',...auth()},body:JSON.stringify(body)});
  btn.disabled=false;
  if(r.ok){document.getElementById('newName').value='';document.getElementById('newToken').value='';loadAccounts();loadStats();toast('添加成功','ok')}
  else{const e=await r.json().catch(()=>({}));toast(e.detail||'添加失败','err')}
}
async function refreshOne(id){
  const btn=document.getElementById('r_'+id);if(!btn)return;
  const orig=btn.textContent;btn.textContent='...';btn.disabled=true;
  const r=await fetch(`/api/accounts/${id}/refresh`,{method:'POST',headers:auth()});
  btn.textContent=orig;btn.disabled=false;
  if(r.ok){loadAccounts();loadStats();toast('刷新成功','ok')}
  else{const e=await r.json().catch(()=>({}));toast(e.detail||'刷新失败','err')}
}
async function refreshAll(){
  const btn=document.getElementById('btnRefreshAll');
  const orig=btn.textContent;btn.textContent='刷新中...';btn.disabled=true;
  toast('正在刷新全部账号...','info',5000);
  const r=await fetch('/api/refresh-all',{method:'POST',headers:auth()});
  btn.textContent=orig;btn.disabled=false;
  if(r.ok){const d=await r.json();loadAccounts();loadStats();toast(`刷新完成: ${d.success}成功 / ${d.failed}失败`,d.failed?'err':'ok')}
  else{toast('刷新请求失败','err')}
}
async function refreshQueryAll(){
  const btn=document.getElementById('btnRefreshQueryAll');
  const orig=btn.textContent;btn.textContent='执行中...';btn.disabled=true;
  toast('1/2 正在刷新全部Token...','info',5000);
  const r1=await fetch('/api/refresh-all',{method:'POST',headers:auth()});
  if(!r1.ok){btn.textContent=orig;btn.disabled=false;toast('刷新失败','err');return}
  const d1=await r1.json();
  loadAccounts();loadStats();
  toast(`刷新完成: ${d1.success}/${d1.total}，开始查额度...`,'info',4000);
  toast('2/2 正在查询全部额度...','info',8000);
  const r2=await fetch('/api/usage-all',{headers:auth()});
  btn.textContent=orig;btn.disabled=false;
  if(r2.ok){
    const d2=await r2.json();
    Object.assign(usageCache,d2);
    loadAccounts();
    let ok=0,fail=0;
    for(const k in d2){if(d2[k].error){fail++}else{ok++}}
    toast(`查询完成: ${ok}成功 / ${fail}失败`,fail?'err':'ok',4000);
  }else{toast('查询额度失败','err')}
}
async function delAccount(id){
  if(!confirm('确认删除？'))return;
  const r=await fetch(`/api/accounts/${id}`,{method:'DELETE',headers:auth()});
  if(r.ok){loadAccounts();loadStats();toast('已删除','ok')}
  else{toast('删除失败','err')}
}
async function usageOne(id){
  const btn=document.getElementById('u_'+id);if(!btn)return;
  const orig=btn.textContent;btn.textContent='查询中...';btn.disabled=true;
  toast('正在查询额度...','info',3000);
  const r=await fetch(`/api/accounts/${id}/usage`,{headers:auth()});
  btn.textContent=orig;btn.disabled=false;
  if(r.ok){
    const d=await r.json();
    usageCache[id]=d;
    loadAccounts();
    if(d.error){toast('查额度失败: '+d.error.substring(0,60),'err')}
    else{
      const parts=[];
      if(d.primary_used_percent!=null)parts.push('5h: '+Math.round(d.primary_used_percent)+'%');
      if(d.spark_7d_used_percent!=null)parts.push('7d: '+Math.round(d.spark_7d_used_percent)+'%');
      toast('额度: '+(parts.join(' · ')||'无数据'),'ok',4000);
    }
  }else{const e=await r.json().catch(()=>({}));usageCache[id]={error:e.detail||e.error||'查询失败'};loadAccounts();toast('查询失败','err')}
}
function exportAll(){
  fetch('/api/accounts',{headers:auth()}).then(r=>r.json()).then(data=>{data.forEach(a=>{if(a.access_token)window.open(`/api/accounts/${a.id}/export?_t=${Date.now()}`)});toast('导出完成','ok')});
}
loadAccounts();loadStats();
setInterval(()=>{loadAccounts();loadStats();},30000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
