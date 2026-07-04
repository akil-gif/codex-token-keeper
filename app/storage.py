"""数据模型与存储层"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.config import config
from app.logger import logger


@dataclass
class Account:
    """一个 Codex / ChatGPT 账号"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""                       # 备注名
    email: str = ""                      # 账号邮箱（从 token 解析）
    plan_type: str = ""                  # free / plus / pro / team
    refresh_token: str = ""              # 用于刷新的 refresh_token
    access_token: str = ""               # 最新的 access_token
    id_token: str = ""                   # 最新的 id_token（可选）
    account_id: str = ""                 # ChatGPT account_id
    last_refresh: float = 0.0            # 上次刷新成功的时间戳
    last_error: str = ""                 # 最近一次错误信息
    status: str = "pending"              # pending / active / error / disabled
    auto_refresh: bool = True            # 是否参与自动刷新
    created_at: float = field(default_factory=time.time)

    def access_token_expires_at(self) -> float:
        """从 JWT 中解析 exp 字段；失败返回 0 表示立即刷新"""
        try:
            import base64
            payload = self.access_token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload))
            return float(data.get("exp", 0))
        except Exception:
            return 0

    def needs_refresh(self) -> bool:
        if not self.access_token:
            return True
        exp = self.access_token_expires_at()
        if exp <= 0:
            return True
        return time.time() > (exp - config.REFRESH_THRESHOLD_SECONDS)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["expires_at"] = self.access_token_expires_at()
        d["needs_refresh"] = self.needs_refresh()
        return d

    def safe_dict(self) -> dict:
        """脱敏输出（用于 API 返回，隐藏完整 token）"""
        d = self.to_dict()
        d["refresh_token"] = mask(d["refresh_token"])
        d["access_token"] = mask(d["access_token"])
        d["id_token"] = mask(d["id_token"])
        return d


def mask(s: str, visible: int = 8) -> str:
    if not s or len(s) <= visible * 2:
        return "*" * len(s) if s else ""
    return s[:visible] + "*" * (len(s) - visible * 2) + s[-visible:]


class Storage:
    """线程安全的账号存储"""

    def __init__(self):
        self._lock = threading.RLock()
        self._accounts: dict[str, Account] = {}
        self._load()

    # ---- 持久化 ----
    def _load(self):
        if not os.path.exists(config.ACCOUNTS_FILE):
            return
        try:
            with open(config.ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                acct = Account(**{k: v for k, v in item.items() if k in Account.__dataclass_fields__})
                self._accounts[acct.id] = acct
            logger.info(f"Loaded {len(self._accounts)} accounts from disk")
        except Exception as e:
            logger.error(f"Failed to load accounts: {e}")

    def _save(self):
        try:
            os.makedirs(os.path.dirname(config.ACCOUNTS_FILE), exist_ok=True)
            with open(config.ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump([asdict(a) for a in self._accounts.values()], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")

    # ---- CRUD ----
    def list(self) -> list[Account]:
        with self._lock:
            return list(self._accounts.values())

    def get(self, account_id: str) -> Optional[Account]:
        with self._lock:
            return self._accounts.get(account_id)

    def add(self, acct: Account) -> Account:
        with self._lock:
            self._accounts[acct.id] = acct
            self._save()
            return acct

    def update(self, account_id: str, **kwargs) -> Optional[Account]:
        with self._lock:
            acct = self._accounts.get(account_id)
            if not acct:
                return None
            for k, v in kwargs.items():
                if hasattr(acct, k) and v is not None:
                    setattr(acct, k, v)
            self._save()
            return acct

    def delete(self, account_id: str) -> bool:
        with self._lock:
            if account_id in self._accounts:
                del self._accounts[account_id]
                self._save()
                return True
            return False

    def save_one(self, acct: Account):
        with self._lock:
            self._save()


storage = Storage()
