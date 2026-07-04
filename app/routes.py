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
from app.oauth import refresh_one, refresh_all, decode_jwt_payload
from app.storage import Account, storage

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

    for i, rt in enumerate(req.refresh_tokens):
        rt = rt.strip()
        if not rt:
            continue
        acct = Account(name=f"import-{i+1}", refresh_token=rt)
        storage.add(acct)
        created.append(acct.safe_dict())

    if req.auth_json:
        acct = _parse_auth_json(req.auth_json)
        if acct:
            storage.add(acct)
            created.append(acct.safe_dict())
        else:
            errors.append("invalid auth_json")

    for i, aj in enumerate(req.auth_json_list):
        acct = _parse_auth_json(aj)
        if acct:
            storage.add(acct)
            created.append(acct.safe_dict())
        else:
            errors.append(f"invalid auth_json #{i+1}")

    return {"created": len(created), "errors": errors, "accounts": created}


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


@router.get("/api/accounts/{account_id}/token")
async def export_token_only(account_id: str, _: bool = Depends(check_admin)):
    acct = storage.get(account_id)
    if not acct:
        raise HTTPException(status_code=404, detail="not found")
    return {"access_token": acct.access_token, "refresh_token": acct.refresh_token}


# ---- 统计 ----
@router.get("/api/stats")
async def stats(_: bool = Depends(check_admin)):
    accounts = storage.list()
    return {
        "total": len(accounts),
        "active": sum(1 for a in accounts if a.status == "active"),
        "with_token": sum(1 for a in accounts if a.access_token),
    }
