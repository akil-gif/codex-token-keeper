"""OAuth 刷新核心逻辑"""
from __future__ import annotations

import base64
import json
import time
from typing import Optional

import httpx

from app.config import config
from app.logger import logger
from app.storage import Account, storage


def decode_jwt_payload(token: str) -> dict:
    """解析 JWT payload（不验证签名）"""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return {}


async def refresh_one(account: Account, force: bool = False) -> tuple[bool, str]:
    """
    用 refresh_token 刷新 access_token。
    成功返回 (True, "")，失败返回 (False, error_msg)。
    """
    if not account.refresh_token:
        return False, "missing refresh_token"

    if not force and not account.needs_refresh():
        return True, "still fresh"

    data = {
        "client_id": config.OAUTH_CLIENT_ID,
        "grant_type": "refresh_token",
        "redirect_uri": config.OAUTH_REDIRECT_URI,
        "refresh_token": account.refresh_token,
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "codex-cli/1.0",
        "Accept": "application/json",
    }

    proxy = config.PROXY_URL or None
    timeout = httpx.Timeout(config.REQUEST_TIMEOUT)

    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
            resp = await client.post(
                config.OAUTH_TOKEN_URL,
                json=data,
                headers=headers,
            )

        if resp.status_code != 200:
            body = resp.text[:500]
            logger.error(f"[{account.name or account.id}] refresh failed HTTP {resp.status_code}: {body}")

            if "invalid_grant" in body or "access_denied" in body:
                storage.update(account.id, status="error", last_error="refresh_token invalid or revoked")
                return False, "refresh_token invalid or revoked"

            storage.update(account.id, last_error=f"HTTP {resp.status_code}: {body}")
            return False, f"HTTP {resp.status_code}"

        result = resp.json()
        new_access = result.get("access_token", "")
        new_refresh = result.get("refresh_token", account.refresh_token)
        new_id_token = result.get("id_token", "")

        if not new_access:
            return False, "no access_token in response"

        # 解析账号信息
        payload = decode_jwt_payload(new_access)
        auth_info = payload.get("https://api.openai.com/auth", {})
        profile = decode_jwt_payload(new_id_token).get("https://api.openai.com/profile", {}) if new_id_token else {}

        updates = {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "id_token": new_id_token,
            "last_refresh": time.time(),
            "last_error": "",
            "status": "active",
            "plan_type": auth_info.get("chatgpt_plan_type", account.plan_type),
            "account_id": auth_info.get("chatgpt_account_id", account.account_id),
            "email": profile.get("email", account.email),
        }
        storage.update(account.id, **updates)

        logger.info(f"[{account.name or account.email or account.id}] refreshed OK, plan={updates['plan_type']}")
        return True, ""

    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.error(f"[{account.name or account.id}] refresh exception: {err}")
        storage.update(account.id, status="error", last_error=err)
        return False, err


async def refresh_all(force: bool = False) -> dict:
    """刷新所有 auto_refresh=True 的账号"""
    accounts = [a for a in storage.list() if a.auto_refresh and a.status != "disabled"]
    total = len(accounts)
    ok, fail = 0, 0
    for acct in accounts:
        success, _ = await refresh_one(acct, force=force)
        if success:
            ok += 1
        else:
            fail += 1
    logger.info(f"refresh_all done: {ok}/{total} ok, {fail} failed")
    return {"total": total, "success": ok, "failed": fail}


async def query_usage(account: Account) -> dict:
    """查 ChatGPT/Codex 额度（参考 sub2api 的 wham/usage 接口）"""
    if not account.access_token:
        return {"error": "no access_token"}

    headers = {
        "authorization": f"Bearer {account.access_token}",
        "chatgpt-account-id": account.account_id or "",
        "openai-beta": "codex-1",
        "oai-language": "zh-CN",
        "originator": "Codex Desktop",
        "accept": "application/json",
        "sec-fetch-site": "none",
        "sec-fetch-mode": "no-cors",
        "sec-fetch-dest": "empty",
        "priority": "u=4, i",
    }

    proxy = config.PROXY_URL or None
    timeout = httpx.Timeout(config.REQUEST_TIMEOUT)

    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=timeout) as client:
            resp = await client.get(
                "https://chatgpt.com/backend-api/wham/usage",
                headers=headers,
            )
        if resp.status_code != 200:
            return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

        data = resp.json()
        result = {
            "plan_type": data.get("plan_type", account.plan_type),
            "fetched_at": time.time(),
        }

        rl = data.get("rate_limit") or {}
        if rl:
            result["rate_limit_allowed"] = rl.get("allowed", True)
            result["rate_limit_reached"] = rl.get("limit_reached", False)
            pw = rl.get("primary_window")
            if pw:
                result["primary_used_percent"] = pw.get("used_percent", 0)
                result["primary_reset_after_seconds"] = pw.get("reset_after_seconds", 0)
                result["primary_window_seconds"] = pw.get("limit_window_seconds", 0)
            sw = rl.get("secondary_window")
            if sw:
                result["secondary_used_percent"] = sw.get("used_percent", 0)
                result["secondary_reset_after_seconds"] = sw.get("reset_after_seconds", 0)
                result["secondary_window_seconds"] = sw.get("limit_window_seconds", 0)

        for a in (data.get("additional_rate_limits") or []):
            if a.get("metered_feature") == "codex_bengalfox":
                srl = a.get("rate_limit", {})
                spw = srl.get("primary_window")
                if spw:
                    result["spark_5h_used_percent"] = spw.get("used_percent", 0)
                    result["spark_5h_reset_after_seconds"] = spw.get("reset_after_seconds", 0)
                ssw = srl.get("secondary_window")
                if ssw:
                    result["spark_7d_used_percent"] = ssw.get("used_percent", 0)
                    result["spark_7d_reset_after_seconds"] = ssw.get("reset_after_seconds", 0)
                break

        return result
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
