"""
统一配置管理模块

集中管理所有环境变量，提供默认值和类型转换。
在应用启动时加载一次，各模块直接导入使用。
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# 只在首次导入时加载环境变量
load_dotenv()


class Config:
    """应用配置类，集中管理所有环境变量"""

    # ========== 长桥 API（可选）==========
    LONGBRIDGE_APP_KEY: Optional[str] = os.getenv("LONGBRIDGE_APP_KEY")
    LONGBRIDGE_APP_SECRET: Optional[str] = os.getenv("LONGBRIDGE_APP_SECRET")
    LONGBRIDGE_ACCESS_TOKEN: Optional[str] = os.getenv("LONGBRIDGE_ACCESS_TOKEN")

    # ========== 搜索 API（可选）==========
    SERPAPI_KEY: Optional[str] = os.getenv("SERPAPI_KEY")

    # ========== Obsidian Vault 路径 ==========
    WIKI_BASE_DIR: Path = Path(os.getenv("WIKI_BASE_DIR", ""))
    WIKI_SUBDIR: str = os.getenv("WIKI_SUBDIR", "Analysis")
    MATERIALS_SUBDIR: str = os.getenv("MATERIALS_SUBDIR", "Materials")

    # ========== Obsidian 通用目录 ==========
    OBSIDIAN_INBOX_DIR: Path = Path(os.getenv("OBSIDIAN_INBOX_DIR", ""))
    OBSIDIAN_TASKS_DIR: Path = Path(os.getenv("OBSIDIAN_TASKS_DIR", ""))
    OBSIDIAN_DASHBOARD_PATH: Path = Path(os.getenv("OBSIDIAN_DASHBOARD_PATH", ""))

    # ========== 超时配置 ==========
    ANALYSIS_TIMEOUT: int = int(os.getenv("ANALYSIS_TIMEOUT", "30"))

    # ========== Web 平台 ==========
    WEB_DB_PATH: Path = Path(os.getenv("WEB_DB_PATH", "data/web.db"))
    USERS_DATA_DIR: Path = Path(os.getenv("USERS_DATA_DIR", "data/users"))
    SESSION_TTL_DAYS: int = int(os.getenv("SESSION_TTL_DAYS", "7"))
    ANALYSIS_DAILY_QUOTA: int = int(os.getenv("ANALYSIS_DAILY_QUOTA", "10"))
    # 注册邀请码（可选；留空则不校验，直接开放注册）
    INVITE_CODE: Optional[str] = os.getenv("INVITE_CODE")

    # ========== LLM 报告增强（可选，缺失时静默降级为确定性文本）==========
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")

    # ========== 定时任务配置（可选）==========
    SCHEDULE_SCAN_INBOX: Optional[str] = os.getenv("SCHEDULE_SCAN_INBOX")
    SCHEDULE_REVIEW: Optional[str] = os.getenv("SCHEDULE_REVIEW")
    SCHEDULE_DASHBOARD: Optional[str] = os.getenv("SCHEDULE_DASHBOARD")
    SCHEDULE_BRIEF: Optional[str] = os.getenv("SCHEDULE_BRIEF")
    SCHEDULE_NOTIFY: Optional[str] = os.getenv("SCHEDULE_NOTIFY")

    # ========== 每日简报（Daily Brief）==========
    BRIEF_LOOKBACK_DAYS: int = int(os.getenv("BRIEF_LOOKBACK_DAYS", "7"))
    BRIEF_TOP_N: int = int(os.getenv("BRIEF_TOP_N", "3"))
    BRIEF_MATERIALS_LIMIT: int = int(os.getenv("BRIEF_MATERIALS_LIMIT", "5"))

    # ========== 通知通道（可选，填 webhook URL 即启用）==========
    FEISHU_WEBHOOK_URL: Optional[str] = os.getenv("FEISHU_WEBHOOK_URL")
    WECOM_WEBHOOK_URL: Optional[str] = os.getenv("WECOM_WEBHOOK_URL")

    @classmethod
    def validate(cls) -> list[str]:
        """
        验证必需的配置项

        Returns:
            错误信息列表，空列表表示验证通过
        """
        errors = []

        if not cls.WIKI_BASE_DIR:
            errors.append("WIKI_BASE_DIR is required")

        if not cls.OBSIDIAN_INBOX_DIR:
            errors.append("OBSIDIAN_INBOX_DIR is required")

        if not cls.OBSIDIAN_TASKS_DIR:
            errors.append("OBSIDIAN_TASKS_DIR is required")

        if not cls.OBSIDIAN_DASHBOARD_PATH:
            errors.append("OBSIDIAN_DASHBOARD_PATH is required")

        return errors

    @classmethod
    def get_wiki_dir(cls) -> Path:
        """获取 Wiki 目录完整路径"""
        return cls.WIKI_BASE_DIR / cls.WIKI_SUBDIR

    @classmethod
    def get_materials_dir(cls) -> Path:
        """获取 Materials 目录完整路径"""
        return cls.WIKI_BASE_DIR / cls.MATERIALS_SUBDIR


# 验证配置（可选，在需要时调用）
def ensure_config() -> None:
    """确保配置有效，否则抛出异常"""
    errors = Config.validate()
    if errors:
        raise ValueError(f"Configuration errors: {', '.join(errors)}")


# 导出便捷访问
config = Config
