"""应用配置。

所有配置项从环境变量或 backend/.env 读取，密钥类字段永不返回给前端。
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """平台全局配置。"""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------------------------------------------------------------- 应用
    app_name: str = "Veeam Inspection Platform"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    log_dir: str = "logs"
    log_retention_days: int = 30

    # --------------------------------------------------------------- MySQL
    db_host: str = "10.0.54.101"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "veeam_inspection"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # --------------------------------------------------------------- 服务
    api_host: str = "0.0.0.0"
    api_port: int = 18000

    # --------------------------------------------------------------- 密钥
    secret_key: str = ""
    previous_secret_keys: str = ""

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ------------------------------------------------------------- 调度器
    scheduler_enabled: bool = True
    default_timezone: str = "Asia/Shanghai"

    # --------------------------------------------------------- 巡检阈值
    default_max_backup_age_hours: float = 48
    default_min_free_percent: float = 20
    default_min_free_gb: float = 20

    # --------------------------------------------------------- 数据保留
    inspection_retention_days: int = 90

    @field_validator("db_name")
    @classmethod
    def _only_dedicated_schema(cls, value: str) -> str:
        """平台只允许写自己的库，避免误伤同实例上的其他业务库。"""
        if value != "veeam_inspection":
            raise ValueError(
                f"db_name 必须为 'veeam_inspection'，当前为 {value!r}"
            )
        return value

    @property
    def previous_secret_key_list(self) -> list[str]:
        """轮换期间用于解密历史密文的旧密钥列表。"""
        return [k.strip() for k in self.previous_secret_keys.split(",") if k.strip()]

    @property
    def database_url(self) -> str:
        """用 SQLAlchemy 的 URL 构造器生成连接串，正确处理口令里的特殊字符。"""
        from sqlalchemy.engine import URL

        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        ).render_as_string(hide_password=False)

    @property
    def sqlalchemy_url_object(self):
        """返回 SQLAlchemy URL 对象，供 create_engine 使用。"""
        from sqlalchemy.engine import URL

        return URL.create(
            drivername="mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )

    @property
    def log_path(self) -> Path:
        return BACKEND_DIR / self.log_dir


@lru_cache
def get_settings() -> Settings:
    """进程内单例配置。"""
    return Settings()
