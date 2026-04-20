from __future__ import annotations

import re
from urllib.parse import urlparse

from graph_of_god_backend.modules.vk.exceptions import InvalidProfileReferenceError

VK_HOSTS = {"vk.com", "www.vk.com", "m.vk.com", "vkontakte.ru", "www.vkontakte.ru"}
NUMERIC_ID_PATTERN = re.compile(r"id(?P<value>\d+)$")


def normalize_profile_reference(raw_value: str) -> str:
    value = raw_value.strip()
    if not value:
        raise InvalidProfileReferenceError("Профиль VK не задан.")

    if "://" not in value and value.startswith("vk.com/"):
        value = f"https://{value}"

    if "://" in value:
        parsed = urlparse(value)
        if parsed.netloc.lower() not in VK_HOSTS:
            raise InvalidProfileReferenceError("Поддерживаются только ссылки на профили VK.")

        path_parts = [part for part in parsed.path.split("/") if part]
        if not path_parts:
            raise InvalidProfileReferenceError("Не удалось извлечь идентификатор профиля.")

        candidate = path_parts[0]
    else:
        candidate = value.lstrip("@")

    match = NUMERIC_ID_PATTERN.fullmatch(candidate)
    if match:
        return match.group("value")

    return candidate
