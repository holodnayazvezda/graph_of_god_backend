from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import RLock
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from graph_of_god_backend.core.config import AppConfig
from graph_of_god_backend.core.exceptions import ConfigurationError
from graph_of_god_backend.modules.vk.exceptions import VKOAuthError, VKResponseFormatError


class AccessTokenProvider(Protocol):
    def get_token(self) -> str:
        """Returns a token that can be used in VK API calls."""


@dataclass(frozen=True, slots=True)
class StaticAccessTokenProvider:
    access_token: str

    def get_token(self) -> str:
        return self.access_token


class ServiceAccessTokenProvider:
    def __init__(
        self,
        *,
        app_id: int,
        app_secret: str,
        oauth_token_url: str,
        api_version: str,
        timeout_seconds: float,
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._oauth_token_url = oauth_token_url
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._cached_token: str | None = None
        self._expires_at_monotonic: float | None = None
        self._lock = RLock()

    def get_token(self) -> str:
        with self._lock:
            if self._cached_token and not self._is_expired():
                return self._cached_token

            payload = self._request_service_token()
            access_token = payload.get("access_token")
            if not isinstance(access_token, str) or not access_token.strip():
                raise VKResponseFormatError("VK OAuth не вернул access_token.")

            self._cached_token = access_token.strip()
            self._expires_at_monotonic = _resolve_expiration(payload)
            return self._cached_token

    def _is_expired(self) -> bool:
        if self._expires_at_monotonic is None:
            return False
        return time.monotonic() >= self._expires_at_monotonic

    def _request_service_token(self) -> dict[str, object]:
        body = urlencode(
            {
                "client_id": self._app_id,
                "client_secret": self._app_secret,
                "grant_type": "client_credentials",
                "v": self._api_version,
            }
        ).encode("utf-8")
        request = Request(
            self._oauth_token_url,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "graph-of-god-backend/0.1",
            },
        )

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise VKOAuthError(f"Ошибка HTTP при получении VK OAuth token: {error.code}") from error
        except URLError as error:
            raise VKOAuthError(f"Сетевой сбой при получении VK OAuth token: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise VKResponseFormatError("VK OAuth вернул невалидный JSON.") from error

        if not isinstance(payload, dict):
            raise VKResponseFormatError("VK OAuth вернул неожиданный формат ответа.")

        if "error" in payload:
            description = payload.get("error_description") or payload["error"]
            raise VKOAuthError(f"VK OAuth error: {description}")

        return payload


def build_access_token_provider(config: AppConfig) -> AccessTokenProvider:
    if config.vk_api_token:
        return StaticAccessTokenProvider(config.vk_api_token)

    if config.vk_app_id is not None and config.vk_app_secret:
        return ServiceAccessTokenProvider(
            app_id=config.vk_app_id,
            app_secret=config.vk_app_secret,
            oauth_token_url=config.vk_oauth_token_url,
            api_version=config.vk_api_version,
            timeout_seconds=config.request_timeout_seconds,
        )

    raise ConfigurationError(
        "Нужно указать либо VK_API_TOKEN, либо пару VK_APP_ID и VK_APP_SECRET в graph_of_god_backend/.env."
    )


def _resolve_expiration(payload: dict[str, object]) -> float | None:
    expires_in = payload.get("expires_in")
    if expires_in in (None, 0, "0"):
        return None

    try:
        expires_in_seconds = int(expires_in)
    except (TypeError, ValueError) as error:
        raise VKResponseFormatError("VK OAuth вернул некорректный expires_in.") from error

    return time.monotonic() + max(expires_in_seconds - 30, 0)
