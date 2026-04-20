from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Iterable

from graph_of_god_backend.core.exceptions import GraphOfGodBackendError
from graph_of_god_backend.modules.vk.entities import (
    FriendLink,
    FriendLinksResult,
    SocialGraphEdge,
    SocialGraphNode,
    SocialGraphOverlap,
    SocialGraphResult,
    SocialGraphSeedProfile,
    SocialGraphStats,
    VKUser,
)
from graph_of_god_backend.modules.vk.friend_links_service import FriendLinksService

MAX_GRAPH_PROFILES = 5


class SocialGraphService:
    def __init__(self, friend_links_service: FriendLinksService) -> None:
        self._friend_links_service = friend_links_service

    def build_social_graph(self, profile_references: Iterable[str]) -> SocialGraphResult:
        normalized_references = [profile_reference.strip() for profile_reference in profile_references]
        if not normalized_references:
            raise GraphOfGodBackendError("Нужно передать хотя бы один профиль VK.")
        if len(normalized_references) > MAX_GRAPH_PROFILES:
            raise GraphOfGodBackendError(
                f"За один запрос можно передать не больше {MAX_GRAPH_PROFILES} профилей VK."
            )
        if any(not profile_reference for profile_reference in normalized_references):
            raise GraphOfGodBackendError("Список профилей не должен содержать пустые значения.")

        with ThreadPoolExecutor(max_workers=min(len(normalized_references), MAX_GRAPH_PROFILES)) as executor:
            seed_results = list(
                executor.map(self._friend_links_service.collect_friend_links, normalized_references)
            )

        self._ensure_unique_seed_users(seed_results)
        return _build_social_graph(normalized_references, seed_results)

    def _ensure_unique_seed_users(self, seed_results: list[FriendLinksResult]) -> None:
        seen_user_ids: set[int] = set()
        duplicate_user_ids: set[int] = set()

        for result in seed_results:
            if result.user.user_id in seen_user_ids:
                duplicate_user_ids.add(result.user.user_id)
            seen_user_ids.add(result.user.user_id)

        if duplicate_user_ids:
            duplicate_ids = ", ".join(str(user_id) for user_id in sorted(duplicate_user_ids))
            raise GraphOfGodBackendError(
                f"Профили в запросе должны быть уникальны. Повторяются user_id: {duplicate_ids}."
            )


@dataclass(slots=True)
class _NodeAccumulator:
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None
    is_seed: bool = False
    seed_indices: set[int] = field(default_factory=set)
    connected_seed_indices: set[int] = field(default_factory=set)
    is_private: bool = False


@dataclass(slots=True)
class _EdgeAccumulator:
    edge_id: str
    source_node_id: str
    target_node_id: str
    connected_seed_indices: set[int] = field(default_factory=set)


def _build_social_graph(
    input_profiles: list[str],
    seed_results: list[FriendLinksResult],
) -> SocialGraphResult:
    node_accumulators: dict[int, _NodeAccumulator] = {}
    edge_accumulators: dict[tuple[int, int], _EdgeAccumulator] = {}
    friend_user_ids_by_seed: list[set[int]] = []
    connection_node_ids_by_seed: list[list[str]] = []

    for seed_index, result in enumerate(seed_results):
        seed_node = _upsert_node_from_user(node_accumulators, result.user)
        seed_node.is_seed = True
        seed_node.seed_indices.add(seed_index)
        seed_node.is_private = seed_node.is_private or result.is_private

        friend_user_ids: set[int] = set()
        connection_node_ids: list[str] = []
        for friend_link in result.links:
            friend_node = _upsert_node_from_friend_link(node_accumulators, friend_link.user_id, friend_link)
            friend_node.connected_seed_indices.add(seed_index)
            friend_user_ids.add(friend_link.user_id)
            connection_node_ids.append(friend_node.node_id)

            edge_key = tuple(sorted((result.user.user_id, friend_link.user_id)))
            edge = edge_accumulators.get(edge_key)
            if edge is None:
                source_user_id, target_user_id = edge_key
                edge = _EdgeAccumulator(
                    edge_id=f"edge:{source_user_id}:{target_user_id}",
                    source_node_id=_node_id(source_user_id),
                    target_node_id=_node_id(target_user_id),
                )
                edge_accumulators[edge_key] = edge
            edge.connected_seed_indices.add(seed_index)

        friend_user_ids_by_seed.append(friend_user_ids)
        connection_node_ids_by_seed.append(sorted(set(connection_node_ids)))

    seed_profiles = tuple(
        SocialGraphSeedProfile(
            seed_index=seed_index,
            input_profile=input_profiles[seed_index],
            node_id=_node_id(result.user.user_id),
            user_id=result.user.user_id,
            full_name=result.user.full_name,
            profile_url=result.user.profile_url,
            avatar_url=result.user.avatar_url,
            source_kind=result.source_kind,
            is_private=result.is_private,
            connection_count=result.returned_count,
            total_available_connection_count=result.total_available_count,
            is_truncated=result.is_truncated,
            connection_node_ids=tuple(connection_node_ids_by_seed[seed_index]),
        )
        for seed_index, result in enumerate(seed_results)
    )

    nodes = tuple(
        SocialGraphNode(
            node_id=node.node_id,
            user_id=node.user_id,
            full_name=node.full_name,
            profile_url=node.profile_url,
            avatar_url=node.avatar_url,
            is_seed=node.is_seed,
            seed_indices=tuple(sorted(node.seed_indices)),
            connected_seed_indices=tuple(sorted(node.connected_seed_indices)),
            shared_seed_count=len(node.connected_seed_indices),
            is_private=node.is_private,
        )
        for node in sorted(
            node_accumulators.values(),
            key=lambda item: (
                0 if item.is_seed else 1,
                -len(item.connected_seed_indices),
                item.full_name.lower(),
                item.user_id,
            ),
        )
    )

    edges = tuple(
        SocialGraphEdge(
            edge_id=edge.edge_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            connected_seed_indices=tuple(sorted(edge.connected_seed_indices)),
        )
        for edge in sorted(
            edge_accumulators.values(),
            key=lambda item: (item.source_node_id, item.target_node_id),
        )
    )

    overlaps = tuple(
        _build_overlap(left_seed_index, right_seed_index, friend_user_ids_by_seed)
        for left_seed_index in range(len(seed_results))
        for right_seed_index in range(left_seed_index + 1, len(seed_results))
    )

    shared_node_count = sum(1 for node in nodes if node.shared_seed_count >= 2)
    stats = SocialGraphStats(
        seed_count=len(seed_profiles),
        node_count=len(nodes),
        edge_count=len(edges),
        overlap_pair_count=len(overlaps),
        shared_node_count=shared_node_count,
        truncated_seed_count=sum(1 for seed_profile in seed_profiles if seed_profile.is_truncated),
    )
    return SocialGraphResult(
        seed_profiles=seed_profiles,
        nodes=nodes,
        edges=edges,
        overlaps=overlaps,
        stats=stats,
    )


def _build_overlap(
    left_seed_index: int,
    right_seed_index: int,
    friend_user_ids_by_seed: list[set[int]],
) -> SocialGraphOverlap:
    shared_user_ids = sorted(friend_user_ids_by_seed[left_seed_index] & friend_user_ids_by_seed[right_seed_index])
    return SocialGraphOverlap(
        left_seed_index=left_seed_index,
        right_seed_index=right_seed_index,
        shared_node_ids=tuple(_node_id(user_id) for user_id in shared_user_ids),
        shared_count=len(shared_user_ids),
    )


def _upsert_node_from_user(
    node_accumulators: dict[int, _NodeAccumulator],
    user: VKUser,
) -> _NodeAccumulator:
    node = node_accumulators.get(user.user_id)
    if node is None:
        node = _NodeAccumulator(
            node_id=_node_id(user.user_id),
            user_id=user.user_id,
            full_name=user.full_name,
            profile_url=user.profile_url,
            avatar_url=user.avatar_url,
        )
        node_accumulators[user.user_id] = node
        return node

    if not node.avatar_url and user.avatar_url:
        node.avatar_url = user.avatar_url
    if not node.full_name and user.full_name:
        node.full_name = user.full_name
    if user.profile_url and node.profile_url != user.profile_url:
        node.profile_url = user.profile_url
    return node


def _upsert_node_from_friend_link(
    node_accumulators: dict[int, _NodeAccumulator],
    user_id: int,
    friend_link: FriendLink,
) -> _NodeAccumulator:
    node = node_accumulators.get(user_id)
    if node is None:
        node = _NodeAccumulator(
            node_id=_node_id(user_id),
            user_id=user_id,
            full_name=friend_link.full_name,
            profile_url=friend_link.url,
            avatar_url=friend_link.avatar_url,
        )
        node_accumulators[user_id] = node
        return node

    if not node.avatar_url and friend_link.avatar_url:
        node.avatar_url = friend_link.avatar_url
    if not node.full_name and friend_link.full_name:
        node.full_name = friend_link.full_name
    if friend_link.url and node.profile_url != friend_link.url:
        node.profile_url = friend_link.url
    return node


def _node_id(user_id: int) -> str:
    return f"vk:{user_id}"
