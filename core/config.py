from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from graph_of_god_backend.core.dotenv import load_dotenv
from graph_of_god_backend.core.exceptions import ConfigurationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOTENV_PATH = BACKEND_ROOT / ".env"


@dataclass(frozen=True, slots=True)
class AppConfig:
    vk_api_token: str | None = None
    vk_app_id: int | None = None
    vk_app_secret: str | None = None
    vk_api_base_url: str = "https://api.vk.com/method"
    vk_oauth_token_url: str = "https://oauth.vk.com/access_token"
    vk_api_version: str = "5.199"
    request_timeout_seconds: float = 15.0
    vk_max_connections_per_profile: int = 5000
    vk_max_graph_connections_per_seed: int = 250
    vk_max_deep_analysis_depth: int = 6
    vk_max_deep_analysis_profiles_to_explore: int = 6000
    vk_max_deep_analysis_connections_per_profile: int = 200
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    job_workers: int = 4
    job_retention_seconds: int = 3600

    @classmethod
    def from_env(cls, *, dotenv_path: Path | None = None) -> "AppConfig":
        load_dotenv(dotenv_path or DEFAULT_DOTENV_PATH)

        token = os.getenv("VK_API_TOKEN", "").strip() or None

        app_id = _parse_optional_int(
            raw_value=os.getenv("VK_APP_ID", "").strip(),
            field_name="VK_APP_ID",
        )
        app_secret = os.getenv("VK_APP_SECRET", "").strip() or None

        if not token and (app_id is None or not app_secret):
            raise ConfigurationError(
                "Укажите либо VK_API_TOKEN, либо VK_APP_ID вместе с VK_APP_SECRET в graph_of_god_backend/.env."
            )

        base_url = os.getenv("VK_API_BASE_URL", "https://api.vk.com/method").strip()
        if not base_url:
            raise ConfigurationError("VK_API_BASE_URL не должен быть пустым.")

        oauth_token_url = os.getenv("VK_OAUTH_TOKEN_URL", "https://oauth.vk.com/access_token").strip()
        if not oauth_token_url:
            raise ConfigurationError("VK_OAUTH_TOKEN_URL не должен быть пустым.")

        api_version = os.getenv("VK_API_VERSION", "5.199").strip() or "5.199"
        timeout = _parse_positive_float(
            raw_value=os.getenv("VK_API_TIMEOUT_SECONDS", "15").strip() or "15",
            field_name="VK_API_TIMEOUT_SECONDS",
        )
        vk_max_connections_per_profile = _parse_positive_int(
            raw_value=os.getenv("VK_MAX_CONNECTIONS_PER_PROFILE", "5000").strip() or "5000",
            field_name="VK_MAX_CONNECTIONS_PER_PROFILE",
        )
        vk_max_graph_connections_per_seed = _parse_positive_int(
            raw_value=os.getenv("VK_MAX_GRAPH_CONNECTIONS_PER_SEED", "250").strip() or "250",
            field_name="VK_MAX_GRAPH_CONNECTIONS_PER_SEED",
        )
        vk_max_deep_analysis_depth = _parse_positive_int(
            raw_value=os.getenv("VK_MAX_DEEP_ANALYSIS_DEPTH", "6").strip() or "6",
            field_name="VK_MAX_DEEP_ANALYSIS_DEPTH",
        )
        vk_max_deep_analysis_profiles_to_explore = _parse_positive_int(
            raw_value=os.getenv("VK_MAX_DEEP_ANALYSIS_PROFILES_TO_EXPLORE", "6000").strip() or "6000",
            field_name="VK_MAX_DEEP_ANALYSIS_PROFILES_TO_EXPLORE",
        )
        vk_max_deep_analysis_connections_per_profile = _parse_positive_int(
            raw_value=os.getenv("VK_MAX_DEEP_ANALYSIS_CONNECTIONS_PER_PROFILE", "200").strip() or "200",
            field_name="VK_MAX_DEEP_ANALYSIS_CONNECTIONS_PER_PROFILE",
        )
        api_host = os.getenv("GRAPH_OF_GOD_BACKEND_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
        api_port = _parse_positive_int(
            raw_value=os.getenv("GRAPH_OF_GOD_BACKEND_API_PORT", "8000").strip() or "8000",
            field_name="GRAPH_OF_GOD_BACKEND_API_PORT",
        )
        job_workers = _parse_positive_int(
            raw_value=os.getenv("GRAPH_OF_GOD_BACKEND_JOB_WORKERS", "4").strip() or "4",
            field_name="GRAPH_OF_GOD_BACKEND_JOB_WORKERS",
        )
        job_retention_seconds = _parse_positive_int(
            raw_value=os.getenv("GRAPH_OF_GOD_BACKEND_JOB_RETENTION_SECONDS", "3600").strip() or "3600",
            field_name="GRAPH_OF_GOD_BACKEND_JOB_RETENTION_SECONDS",
        )

        return cls(
            vk_api_token=token,
            vk_app_id=app_id,
            vk_app_secret=app_secret,
            vk_api_base_url=base_url,
            vk_oauth_token_url=oauth_token_url,
            vk_api_version=api_version,
            request_timeout_seconds=timeout,
            vk_max_connections_per_profile=vk_max_connections_per_profile,
            vk_max_graph_connections_per_seed=vk_max_graph_connections_per_seed,
            vk_max_deep_analysis_depth=vk_max_deep_analysis_depth,
            vk_max_deep_analysis_profiles_to_explore=vk_max_deep_analysis_profiles_to_explore,
            vk_max_deep_analysis_connections_per_profile=vk_max_deep_analysis_connections_per_profile,
            api_host=api_host,
            api_port=api_port,
            job_workers=job_workers,
            job_retention_seconds=job_retention_seconds,
        )


def _parse_optional_int(*, raw_value: str, field_name: str) -> int | None:
    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{field_name} должен быть целым числом.") from error


def _parse_positive_int(*, raw_value: str, field_name: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{field_name} должен быть целым числом.") from error

    if value <= 0:
        raise ConfigurationError(f"{field_name} должен быть больше нуля.")
    return value


def _parse_positive_float(*, raw_value: str, field_name: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{field_name} должен быть числом.") from error

    if value <= 0:
        raise ConfigurationError(f"{field_name} должен быть больше нуля.")
    return value
