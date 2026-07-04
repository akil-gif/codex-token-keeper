"""配置模块"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # 服务配置
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # 管理员密码（用于 Web 界面登录）
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "admin123")

    # OAuth 配置（Codex CLI 官方参数）
    OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "app_EMoamEEZ73f0CkXaXp7hrann")
    OAUTH_TOKEN_URL: str = os.getenv("OAUTH_TOKEN_URL", "https://auth.openai.com/oauth/token")
    OAUTH_REDIRECT_URI: str = os.getenv("OAUTH_REDIRECT_URI", "com.openai.chat://auth0.openai.com/ios/com.openai.chat/callback")

    # 刷新间隔（秒），默认 8 小时
    REFRESH_INTERVAL_HOURS: int = int(os.getenv("REFRESH_INTERVAL_HOURS", "8"))

    # access_token 提前刷新的阈值（秒），默认提前 1 小时
    REFRESH_THRESHOLD_SECONDS: int = int(os.getenv("REFRESH_THRESHOLD_SECONDS", "3600"))

    # 数据存储路径
    DATA_DIR: str = os.getenv("DATA_DIR", "/app/data")
    ACCOUNTS_FILE: str = ""
    LOG_FILE: str = ""

    # 代理配置（可选，用于访问 OpenAI）
    PROXY_URL: str = os.getenv("PROXY_URL", "")

    # 请求超时
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))

    def __post_init__(self):
        os.makedirs(self.DATA_DIR, exist_ok=True)
        self.ACCOUNTS_FILE = os.path.join(self.DATA_DIR, "accounts.json")
        self.LOG_FILE = os.path.join(self.DATA_DIR, "keeper.log")


config = Config()
