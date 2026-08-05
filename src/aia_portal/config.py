from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def _secret(secrets: Mapping[str, Any] | None, key: str, default: str = "") -> str:
    if secrets:
        try:
            value = secrets.get(key, default)
            if value is not None:
                return str(value)
        except Exception:
            pass
    return os.getenv(key, default)


def _as_bool(value: str, default: bool = False) -> bool:
    if value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_publishable_key: str
    enable_demo_mode: bool
    app_name: str = "AIA Canada Data Portal"
    support_email: str = "data@aiacanada.com"
    max_upload_mb: int = 10

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_publishable_key)


def load_settings(secrets: Mapping[str, Any] | None = None) -> Settings:
    publishable_key = _secret(secrets, "SUPABASE_PUBLISHABLE_KEY") or _secret(
        secrets, "SUPABASE_ANON_KEY"
    )
    return Settings(
        supabase_url=_secret(secrets, "SUPABASE_URL"),
        supabase_publishable_key=publishable_key,
        enable_demo_mode=_as_bool(_secret(secrets, "ENABLE_DEMO_MODE", "true"), True),
        support_email=_secret(secrets, "SUPPORT_EMAIL", "data@aiacanada.com"),
        max_upload_mb=int(_secret(secrets, "MAX_UPLOAD_MB", "10")),
    )
