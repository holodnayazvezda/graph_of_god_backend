from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from graph_of_god_backend.modules.vk.auth import AccessTokenProvider
from graph_of_god_backend.modules.vk.exceptions import VKApiError, VKResponseFormatError


class VKApiClient:
    def __init__(
        self,
        *,
        access_token_provider: AccessTokenProvider,
        api_version: str,
        timeout_seconds: float,
        base_url: str,
    ) -> None:
        self._access_token_provider = access_token_provider
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._base_url = base_url.rstrip("/")

    def call(self, method: str, params: dict[str, Any]) -> Any:
        query_params = {
            "access_token": self._access_token_provider.get_token(),
            "v": self._api_version,
            **params,
        }
        url = f"{self._base_url}/{method}?{urlencode(query_params)}"
        request = Request(url, headers={"User-Agent": "graph-of-god-backend/0.1"})

        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise VKApiError(f"Ошибка HTTP при обращении к VK API: {error.code}") from error
        except URLError as error:
            raise VKApiError(f"Сетевой сбой при обращении к VK API: {error.reason}") from error
        except json.JSONDecodeError as error:
            raise VKResponseFormatError("VK API вернул невалидный JSON.") from error

        if "error" in payload:
            error_payload = payload["error"]
            error_code = error_payload.get("error_code")
            error_message = error_payload.get("error_msg", "Неизвестная ошибка VK API.")
            raise VKApiError(
                f"VK API error {error_code}: {error_message}",
                error_code=error_code,
            )

        if "response" not in payload:
            raise VKResponseFormatError("VK API не вернул поле response.")

        return payload["response"]
