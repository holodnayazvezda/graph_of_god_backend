from __future__ import annotations

from graph_of_god_backend.core.exceptions import GraphOfGodBackendError
from graph_of_god_backend.modules.vk.client import VKApiClient
from graph_of_god_backend.modules.vk.entities import FriendLink, FriendLinksResult, VKUser
from graph_of_god_backend.modules.vk.exceptions import VKApiError, VKResponseFormatError
from graph_of_god_backend.modules.vk.profile_reference import normalize_profile_reference

DELETED_OR_BANNED_PROFILE_ERROR_CODE = 18
PRIVATE_PROFILE_ERROR_CODE = 30
VK_CONNECTIONS_PAGE_SIZE = 1000


class FriendLinksService:
    def __init__(self, vk_api_client: VKApiClient, *, max_connections_per_profile: int) -> None:
        self._vk_api_client = vk_api_client
        self._max_connections_per_profile = max_connections_per_profile

    def resolve_user(self, profile_reference: str) -> VKUser:
        return self._resolve_user(profile_reference)

    def collect_friend_links(self, profile_reference: str) -> FriendLinksResult:
        user = self.resolve_user(profile_reference)
        friend_result = self.collect_friends_for_user(user)
        if friend_result.is_private:
            return friend_result

        if friend_result.links:
            return friend_result

        if user.followers_count <= 0:
            return friend_result

        try:
            follower_links, total_follower_count = self._list_followers(user)
        except VKApiError as error:
            if error.error_code == PRIVATE_PROFILE_ERROR_CODE:
                return self._build_private_result(user, max_connection_limit=self._max_connections_per_profile)
            raise

        return FriendLinksResult(
            user=user,
            links=tuple(follower_links),
            is_private=False,
            source_kind="followers",
            returned_count=len(follower_links),
            total_available_count=total_follower_count,
            is_truncated=total_follower_count > len(follower_links),
            max_connection_limit=self._max_connections_per_profile,
        )

    def collect_friends_only(
        self,
        profile_reference: str,
        *,
        public_only: bool = False,
        max_connections: int | None = None,
    ) -> FriendLinksResult:
        user = self.resolve_user(profile_reference)
        return self.collect_friends_for_user(
            user,
            public_only=public_only,
            max_connections=max_connections,
        )

    def collect_friends_for_user(
        self,
        user: VKUser,
        *,
        public_only: bool = False,
        max_connections: int | None = None,
    ) -> FriendLinksResult:
        connection_limit = max_connections or self._max_connections_per_profile
        if user.is_unavailable:
            raise GraphOfGodBackendError("Профиль VK удалён или заблокирован.")
        if user.is_private:
            return self._build_private_result(user, max_connection_limit=connection_limit)

        try:
            friend_links, total_friend_count = self._list_friends(user, max_connections=max_connections)
        except VKApiError as error:
            if error.error_code == PRIVATE_PROFILE_ERROR_CODE:
                return self._build_private_result(user, max_connection_limit=connection_limit)
            if error.error_code == DELETED_OR_BANNED_PROFILE_ERROR_CODE:
                raise GraphOfGodBackendError("Профиль VK удалён или заблокирован.") from error
            raise

        if public_only:
            friend_links = [
                friend_link
                for friend_link in friend_links
                if not friend_link.is_private and not friend_link.is_unavailable
            ]

        return FriendLinksResult(
            user=user,
            links=tuple(friend_links),
            is_private=False,
            source_kind="friends",
            returned_count=len(friend_links),
            total_available_count=total_friend_count,
            is_truncated=total_friend_count > len(friend_links),
            max_connection_limit=connection_limit,
        )

    def list_friends_by_user_id(
        self,
        user_id: int,
        *,
        max_connections: int | None = None,
    ) -> tuple[list[FriendLink], int]:
        return self._list_connections(
            method_name="friends.get",
            user_id=user_id,
            max_connections=max_connections,
        )

    def _resolve_user(self, profile_reference: str) -> VKUser:
        normalized_reference = normalize_profile_reference(profile_reference)
        response = self._vk_api_client.call(
            "users.get",
            {
                "user_ids": normalized_reference,
                "fields": "domain,followers_count,photo_100",
            },
        )

        if not isinstance(response, list) or not response:
            raise VKResponseFormatError("VK API вернул неожиданный формат users.get.")

        user_data = response[0]
        if not isinstance(user_data, dict):
            raise VKResponseFormatError("VK API вернул неожиданный формат users.get.")

        return VKUser(
            user_id=user_data["id"],
            full_name=f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
            domain=user_data.get("domain"),
            avatar_url=_parse_optional_string(user_data.get("photo_100"), field_name="users.get.photo_100"),
            followers_count=_parse_non_negative_int(user_data.get("followers_count")),
            is_closed=bool(user_data.get("is_closed", False)),
            can_access_closed=bool(user_data.get("can_access_closed", True)),
            deactivated_status=_parse_optional_deactivated_status(
                user_data.get("deactivated"),
                field_name="users.get.deactivated",
            ),
        )

    def _build_private_result(self, user: VKUser, *, max_connection_limit: int) -> FriendLinksResult:
        return FriendLinksResult(
            user=user,
            links=(),
            is_private=True,
            source_kind="private",
            returned_count=0,
            total_available_count=0,
            is_truncated=False,
            max_connection_limit=max_connection_limit,
        )

    def _list_friends(
        self,
        user: VKUser,
        *,
        max_connections: int | None = None,
    ) -> tuple[list[FriendLink], int]:
        return self.list_friends_by_user_id(user.user_id, max_connections=max_connections)

    def _list_followers(self, user: VKUser) -> tuple[list[FriendLink], int]:
        return self._list_connections(
            method_name="users.getFollowers",
            user_id=user.user_id,
        )

    def _list_connections(
        self,
        *,
        method_name: str,
        user_id: int,
        max_connections: int | None = None,
    ) -> tuple[list[FriendLink], int]:
        collected_links: list[FriendLink] = []
        total_count: int | None = None
        offset = 0
        remaining_limit = max_connections or self._max_connections_per_profile

        while remaining_limit > 0:
            requested_count = min(VK_CONNECTIONS_PAGE_SIZE, remaining_limit)
            response = self._vk_api_client.call(
                method_name,
                {
                    "user_id": user_id,
                    "fields": "domain,photo_100,is_closed,can_access_closed",
                    "count": requested_count,
                    "offset": offset,
                },
            )

            items = response.get("items")
            response_total_count = response.get("count")
            if not isinstance(items, list) or not isinstance(response_total_count, int):
                raise VKResponseFormatError(f"VK API вернул неожиданный формат {method_name}.")

            if total_count is None:
                total_count = response_total_count

            built_links = _build_friend_links(items, method_name=method_name)
            collected_links.extend(built_links)
            offset += len(built_links)
            remaining_limit -= len(built_links)

            if offset >= response_total_count or not built_links:
                break

        return collected_links, total_count or 0


def _build_friend_links(items: list[object], *, method_name: str) -> list[FriendLink]:
    friend_links: list[FriendLink] = []
    for item in items:
        if not isinstance(item, dict):
            raise VKResponseFormatError(f"VK API вернул неожиданный формат {method_name}.")

        friend_id = item.get("id")
        if not isinstance(friend_id, int):
            raise VKResponseFormatError(f"VK API вернул неожиданный формат {method_name}.")

        domain = item.get("domain")
        if domain is not None and not isinstance(domain, str):
            raise VKResponseFormatError(f"VK API вернул неожиданный формат {method_name}.")

        friend_links.append(
            FriendLink(
                user_id=friend_id,
                full_name=f"{item.get('first_name', '')} {item.get('last_name', '')}".strip(),
                url=_build_profile_url(domain=domain, user_id=friend_id),
                avatar_url=_parse_optional_string(
                    item.get("photo_100"),
                    field_name=f"{method_name}.photo_100",
                ),
                is_closed=_parse_optional_bool(
                    item.get("is_closed"),
                    field_name=f"{method_name}.is_closed",
                    default=False,
                ),
                can_access_closed=_parse_optional_bool(
                    item.get("can_access_closed"),
                    field_name=f"{method_name}.can_access_closed",
                    default=True,
                ),
                deactivated_status=_parse_optional_deactivated_status(
                    item.get("deactivated"),
                    field_name=f"{method_name}.deactivated",
                ),
            )
        )

    return friend_links


def _build_profile_url(*, domain: str | None, user_id: int) -> str:
    if domain:
        return f"https://vk.com/{domain}"
    return f"https://vk.com/id{user_id}"


def _parse_non_negative_int(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    raise VKResponseFormatError("VK API вернул неожиданный формат users.get.")


def _parse_optional_string(value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise VKResponseFormatError(f"VK API вернул неожиданный формат {field_name}.")


def _parse_optional_bool(value: object, *, field_name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    raise VKResponseFormatError(f"VK API вернул неожиданный формат {field_name}.")


def _parse_optional_deactivated_status(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    if value in {"deleted", "banned"}:
        return value
    raise VKResponseFormatError(f"VK API вернул неожиданный формат {field_name}.")
