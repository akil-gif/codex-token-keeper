"""账号管理 API 路由"""
from __future__ import annotations

import json
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from app.config import config
from app.logger import logger
from app.oauth import refresh_one, refresh_all, decode_jwt_payload, query_usage
from app.storage import Account, storage
import zipfile
import io

router = APIRouter()


# ---- 鉴权 ----
def check_admin(request: Request):
    """简单 session 校验"""
    auth = request.headers.get("Authorization", "")
    token = request.cookies.get("session", "")
    expected = request.app.state.session_token
    if auth == f"Bearer {expected}" or token == expected:
        return True
    raise HTTPException(status_code=401, detail="unauthorized")


# ---- 请求模型 ----
class LoginReq(BaseModel):
    password: str


class AccountCreate(BaseModel):
    name: str = ""
    refresh_token: str
    auto_refresh: bool = True


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    refresh_token: Optional[str] = None
    auto_refresh: Optional[bool] = None
    status: Optional[str] = None


class ImportReq(BaseModel):
    refresh_tokens: list[str] = Field(default_factory=list)
    auth_json: Optional[str] = None
    auth_json_list: list[str] = Field(default_factory=list)


# ---- 登录 ----
@router.post("/api/login")
async def login(req: LoginReq, request: Request):
    if req.password != config.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="wrong password")
    token = uuid.uuid4().hex
    request.app.state.session_token = token
    return {"token": token}


# ---- 账号 CRUD ----
@router.get("/api/accounts")
async def list_accounts(_: bool = Depends(check_admin)):
    return [a.safe_dict() for a in storage.list()]


@router.post("/api/accounts")
async def create_account(req: AccountCreate, _: bool = Depends(check_admin)):
    acct = Account(name=req.name, refresh_token=req.refresh_token, auto_refresh=req.auto_refresh)
    storage.add(acct)
    await refresh_one(acct, force=True)
    return acct.safe_dict()


@router.patch("/api/accounts/{account_id}")
async def update_account(account_id: str, req: AccountUpdate, _: bool = Depends(check_admin)):
    acct = storage.update(account_id, **req.model_dump(exclude_none=True))
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    return acct.safe_dict()


@router.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str, _: bool = Depends(check_admin)):
    if not storage.delete(account_id):
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True}


# ---- 批量导入 ----
@router.post("/api/accounts/import")
async def import_accounts(req: ImportReq, _: bool = Depends(check_admin)):
    created = []
    errors = []
    duplicates = []

    def _is_duplicate(rt: str, email: str = "", acct_id: str = "") -> Optional[Account]:
        """检查是否重复，以 refresh_token 为主，email/account_id 辅助"""
        rt = (rt or "").strip()
        for existing in storage.list():
            if rt and existing.refresh_token == rt:
                return existing
            if email and existing.email and existing.email == email:
                return existing
            if acct_id and existing.account_id and existing.account_id == acct_id:
                return existing
        return None

    def _dup_label(a: Account) -> str:
        return a.name or a.email or a.id

    for i, rt in enumerate(req.refresh_tokens):
        rt = rt.strip()
        if not rt:
            continue
        dup = _is_duplicate(rt)
        if dup:
            duplicates.append({"refresh_token": rt[:8] + "...", "existing": _dup_label(dup)})
            continue
        acct = Account(name=f"import-{i+1}", refresh_token=rt)
        storage.add(acct)
        created.append(acct.safe_dict())

    if req.auth_json:
        acct = _parse_auth_json(req.auth_json)
        if acct:
            dup = _is_duplicate(acct.refresh_token, acct.email, acct.account_id)
            if dup:
                duplicates.append({"refresh_token": acct.refresh_token[:8] + "...", "existing": _dup_label(dup)})
            else:
                storage.add(acct)
                created.append(acct.safe_dict())
        else:
            errors.append("invalid auth_json")

    for i, aj in enumerate(req.auth_json_list):
        acct = _parse_auth_json(aj)
        if acct:
            dup = _is_duplicate(acct.refresh_token, acct.email, acct.account_id)
            if dup:
                duplicates.append({"refresh_token": acct.refresh_token[:8] + "...", "existing": _dup_label(dup)})
            else:
                storage.add(acct)
                created.append(acct.safe_dict())
        else:
            errors.append(f"invalid auth_json #{i+1}")

    return {"created": len(created), "errors": errors, "duplicates": duplicates, "accounts": created}


def _parse_auth_json(content: str) -> Optional[Account]:
    try:
        data = json.loads(content)
        tokens = data.get("tokens", data)
        rt = tokens.get("refresh_token", "")
        at = tokens.get("access_token", "")
        idt = tokens.get("id_token", "")
        acct_id = tokens.get("account_id", "")

        email = ""
        plan = ""
        if at:
            payload = decode_jwt_payload(at)
            auth_info = payload.get("https://api.openai.com/auth", {})
            acct_id = auth_info.get("chatgpt_account_id", acct_id)
            plan = auth_info.get("chatgpt_plan_type", "")
        if idt:
            id_payload = decode_jwt_payload(idt)
            email = id_payload.get("email", "")

        return Account(
            name=email or f"import-{int(time.time())}",
            email=email,
            plan_type=plan,
            refresh_token=rt,
            access_token=at,
            id_token=idt,
            account_id=acct_id,
            last_refresh=time.time() if at else 0,
            status="active" if at else "pending",
        )
    except Exception as e:
        logger.error(f"parse auth_json failed: {e}")
        return None


# ---- 刷新操作 ----
@router.post("/api/accounts/{account_id}/refresh")
async def manual_refresh(account_id: str, _: bool = Depends(check_admin)):
    acct = storage.get(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    ok, err = await refresh_one(acct, force=True)
    return {"ok": ok, "error": err, "account": acct.safe_dict()}


@router.post("/api/refresh-all")
async def manual_refresh_all(_: bool = Depends(check_admin)):
    return await refresh_all(force=True)


# ---- 导出 ----
@router.get("/api/accounts/{account_id}/export")
async def export_account(account_id: str, _: bool = Depends(check_admin)):
    """导出 Codex CLI 兼容的 auth.json 格式"""
    acct = storage.get(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "auth_mode": "browser",
        "tokens": {
            "access_token": acct.access_token,
            "refresh_token": acct.refresh_token,
            "id_token": acct.id_token,
            "account_id": acct.account_id,
        },
    }


@router.get("/api/accounts/export-all")
async def export_all_accounts(_: bool = Depends(check_admin)):
    """打包导出全部账号为 ZIP，每个账号一个 auth.json 文件"""
    from fastapi.responses import StreamingResponse

    accounts = storage.list()
    if not accounts:
        raise HTTPException(status_code=404, detail="no accounts")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        used_names: dict[str, int] = {}
        for acct in accounts:
            base = (acct.name or acct.email or acct.id).strip()
            safe_base = "".join(c if c.isalnum() or c in "-_" else "_" for c in base) or "account"
            name = f"{safe_base}.json"
            if name in used_names:
                used_names[name] += 1
                name = f"{safe_base}_{used_names[name]}.json"
            else:
                used_names[name] = 1
            content = {
                "auth_mode": "browser",
                "tokens": {
                    "access_token": acct.access_token,
                    "refresh_token": acct.refresh_token,
                    "id_token": acct.id_token,
                    "account_id": acct.account_id,
                },
            }
            zf.writestr(name, json.dumps(content, ensure_ascii=False, indent=2))
    buf.seek(0)

    headers = {"Content-Disposition": 'attachment; filename="codex-accounts.zip"'}
    return StreamingResponse(buf, media_type="application/zip", headers=headers)


@router.get("/api/accounts/{account_id}/token")
async def export_token_only(account_id: str, _: bool = Depends(check_admin)):
    acct = storage.get(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    return {"access_token": acct.access_token, "refresh_token": acct.refresh_token}


@router.get("/api/accounts/{account_id}/usage")
async def get_usage(account_id: str, _: bool = Depends(check_admin)):
    acct = storage.get(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    result = await query_usage(acct)
    if "error" in result:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=502, content=result)
    return result


@router.get("/api/usage-all")
async def get_usage_all(_: bool = Depends(check_admin)):
    """批量查询所有账号额度"""
    accounts = storage.list()
    results = {}
    for acct in accounts:
        if acct.access_token and acct.status != "disabled":
            results[acct.id] = await query_usage(acct)
    return results


@router.get("/api/stats")
async def stats(_: bool = Depends(check_admin)):
    accounts = storage.list()
    return {
        "total": len(accounts),
        "active": sum(1 for a in accounts if a.status == "active"),
        "with_token": sum(1 for a in accounts if a.access_token),
    }


# ---- 借用接口（本地轮询系统调用）----
@router.get("/api/borrow")
async def borrow_token(_: bool = Depends(check_admin)):
    """返回一个额度未满的账号 access_token，按 primary_used_percent 升序选最优账号"""
    accounts = [a for a in storage.list() if a.access_token and a.status == "active"]
    if not accounts:
        raise HTTPException(status_code=503, detail="no available accounts")

    best = None
    best_pct = 999
    for acct in accounts:
        usage = await query_usage(acct)
        if "error" in usage:
            continue
        if usage.get("rate_limit_reached"):
            continue
        pct = usage.get("primary_used_percent", 0)
        if pct < best_pct:
            best_pct = pct
            best = acct
        if best_pct == 0:
            break

    if not best:
        raise HTTPException(status_code=429, detail="all accounts rate limited")

    return {
        "account_id": best.id,
        "email": best.email or best.name,
        "access_token": best.access_token,
        "account_id_openai": best.account_id,
        "plan_type": best.plan_type,
        "primary_used_percent": best_pct,
    }


@router.post("/api/borrow/{account_id}/release")
async def release_token(account_id: str, _: bool = Depends(check_admin)):
    """本地系统用完后通知 Railway，可选触发即时刷新"""
    acct = storage.get(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    return {"ok": True, "account_id": account_id}
