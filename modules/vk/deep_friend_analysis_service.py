from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from graph_of_god_backend.core.exceptions import GraphOfGodBackendError
from graph_of_god_backend.modules.vk.entities import (
    DeepFriendAnalysisCycle,
    DeepFriendAnalysisEdge,
    DeepFriendAnalysisNode,
    DeepFriendAnalysisResult,
    DeepFriendAnalysisRootProfile,
    DeepFriendAnalysisStats,
    FriendLink,
)
from graph_of_god_backend.modules.vk.exceptions import VKApiError
from graph_of_god_backend.modules.vk.friend_links_service import (
    DELETED_OR_BANNED_PROFILE_ERROR_CODE,
    FriendLinksService,
    PRIVATE_PROFILE_ERROR_CODE,
)


@dataclass(slots=True)
class _ExploredNode:
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None
    distance_from_root: int
    parent_user_id: int | None
    is_private: bool = False


@dataclass(frozen=True, slots=True)
class _FetchedFriendBatch:
    public_links: tuple[FriendLink, ...]
    total_available_count: int
    private_skipped_count: int
    is_truncated: bool
    is_private: bool = False
    is_unavailable: bool = False


@dataclass(frozen=True, slots=True)
class _CycleDescriptor:
    cycle_id: str
    cycle_user_ids: tuple[int, ...]
    cycle_edge_keys: tuple[tuple[int, int], ...]
    focus_user_ids: tuple[int, ...]
    length: int
    closest_distance_from_root: int
    includes_root: bool


class DeepFriendAnalysisService:
    def __init__(
        self,
        friend_links_service: FriendLinksService,
        *,
        max_depth: int,
        max_profiles_to_explore: int,
        max_connections_per_profile: int,
    ) -> None:
        self._friend_links_service = friend_links_service
        self._max_depth = max_depth
        self._max_profiles_to_explore = max_profiles_to_explore
        self._max_connections_per_profile = max_connections_per_profile

    def build_deep_friend_analysis(self, input_payload: tuple[str, int]) -> DeepFriendAnalysisResult:
        profile_reference, requested_depth = input_payload
        normalized_profile_reference = profile_reference.strip()
        if not normalized_profile_reference:
            raise GraphOfGodBackendError("Нужно указать профиль VK для глубокого анализа.")
        if requested_depth <= 0:
            raise GraphOfGodBackendError("Глубина анализа должна быть больше нуля.")
        if requested_depth > self._max_depth:
            raise GraphOfGodBackendError(
                f"Максимальная глубина анализа в текущей конфигурации: {self._max_depth}."
            )

        root_user = self._friend_links_service.resolve_user(normalized_profile_reference)
        if root_user.is_unavailable:
            raise GraphOfGodBackendError("Указанный профиль VK удалён или заблокирован.")
        root_node = _ExploredNode(
            user_id=root_user.user_id,
            full_name=root_user.full_name,
            profile_url=root_user.profile_url,
            avatar_url=root_user.avatar_url,
            distance_from_root=0,
            parent_user_id=None,
            is_private=root_user.is_private,
        )
        explored_nodes: dict[int, _ExploredNode] = {root_user.user_id: root_node}
        adjacency: dict[int, set[int]] = {root_user.user_id: set()}
        tree_parent_by_user_id: dict[int, int | None] = {root_user.user_id: None}
        expanded_user_ids: set[int] = set()
        queued_user_ids: set[int] = {root_user.user_id}

        explored_profile_count = 0
        private_skipped_count = 0
        truncated_profile_count = 0
        exploration_was_limited = False
        root_direct_connection_count = 0
        root_total_available_connection_count = 0
        root_is_truncated = False

        if not root_user.is_private:
            queue: deque[tuple[int, int]] = deque([(root_user.user_id, 0)])
            while queue:
                user_id, current_depth = queue.popleft()
                queued_user_ids.discard(user_id)
                if user_id in expanded_user_ids or current_depth >= requested_depth:
                    continue

                fetched_batch = self._fetch_public_friend_batch(user_id)
                explored_profile_count += 1

                if fetched_batch.is_private or fetched_batch.is_unavailable:
                    private_skipped_count += 1
                    for neighbor_user_id in list(adjacency.get(user_id, ())):
                        adjacency[neighbor_user_id].discard(user_id)
                    adjacency[user_id].clear()
                    node = explored_nodes[user_id]
                    explored_nodes[user_id] = _ExploredNode(
                        user_id=node.user_id,
                        full_name=node.full_name,
                        profile_url=node.profile_url,
                        avatar_url=node.avatar_url,
                        distance_from_root=node.distance_from_root,
                        parent_user_id=node.parent_user_id,
                        is_private=True,
                    )
                    expanded_user_ids.add(user_id)
                    continue

                private_skipped_count += fetched_batch.private_skipped_count
                if fetched_batch.is_truncated:
                    truncated_profile_count += 1

                if user_id == root_user.user_id:
                    root_direct_connection_count = len(fetched_batch.public_links)
                    root_total_available_connection_count = fetched_batch.total_available_count
                    root_is_truncated = fetched_batch.is_truncated

                for friend_link in fetched_batch.public_links:
                    if friend_link.is_unavailable:
                        private_skipped_count += 1
                        continue

                    if friend_link.user_id not in explored_nodes:
                        if len(explored_nodes) >= self._max_profiles_to_explore:
                            exploration_was_limited = True
                            continue

                        explored_nodes[friend_link.user_id] = _ExploredNode(
                            user_id=friend_link.user_id,
                            full_name=friend_link.full_name,
                            profile_url=friend_link.url,
                            avatar_url=friend_link.avatar_url,
                            distance_from_root=current_depth + 1,
                            parent_user_id=user_id,
                        )
                        tree_parent_by_user_id[friend_link.user_id] = user_id
                        adjacency[friend_link.user_id] = set()
                    else:
                        existing_node = explored_nodes[friend_link.user_id]
                        if not existing_node.avatar_url and friend_link.avatar_url:
                            existing_node = _ExploredNode(
                                user_id=existing_node.user_id,
                                full_name=existing_node.full_name or friend_link.full_name,
                                profile_url=existing_node.profile_url or friend_link.url,
                                avatar_url=friend_link.avatar_url,
                                distance_from_root=existing_node.distance_from_root,
                                parent_user_id=existing_node.parent_user_id,
                                is_private=existing_node.is_private,
                            )
                            explored_nodes[friend_link.user_id] = existing_node

                    adjacency[user_id].add(friend_link.user_id)
                    adjacency[friend_link.user_id].add(user_id)

                    next_depth = current_depth + 1
                    if (
                        next_depth < requested_depth
                        and friend_link.user_id not in expanded_user_ids
                        and friend_link.user_id not in queued_user_ids
                    ):
                        queue.append((friend_link.user_id, next_depth))
                        queued_user_ids.add(friend_link.user_id)

                expanded_user_ids.add(user_id)

        cycle_descriptors = _build_cycle_descriptors(
            root_user_id=root_user.user_id,
            adjacency=adjacency,
            tree_parent_by_user_id=tree_parent_by_user_id,
            explored_nodes=explored_nodes,
        )

        rendered_user_ids: set[int] = {root_user.user_id}
        rendered_edge_keys: set[tuple[int, int]] = set()
        cycle_edge_keys: set[tuple[int, int]] = set()
        cycle_count_by_user_id: dict[int, int] = {}

        for cycle in cycle_descriptors:
            rendered_user_ids.update(cycle.focus_user_ids)
            rendered_edge_keys.update(cycle.cycle_edge_keys)
            cycle_edge_keys.update(cycle.cycle_edge_keys)
            rendered_edge_keys.update(_collect_path_edge_keys(cycle.focus_user_ids, tree_parent_by_user_id))
            for user_id in cycle.cycle_user_ids:
                cycle_count_by_user_id[user_id] = cycle_count_by_user_id.get(user_id, 0) + 1

        if not cycle_descriptors:
            rendered_user_ids = {root_user.user_id}
            rendered_edge_keys = set()

        rendered_nodes = tuple(
            DeepFriendAnalysisNode(
                node_id=_node_id(user_id),
                user_id=user_id,
                full_name=node.full_name,
                profile_url=node.profile_url,
                avatar_url=node.avatar_url,
                is_seed=user_id == root_user.user_id,
                seed_indices=(0,) if user_id == root_user.user_id else (),
                connected_seed_indices=() if user_id == root_user.user_id else (0,),
                shared_seed_count=2 if cycle_count_by_user_id.get(user_id, 0) > 0 else 1,
                is_private=node.is_private,
                distance_from_root=node.distance_from_root,
                is_cycle_member=cycle_count_by_user_id.get(user_id, 0) > 0,
                cycle_count=cycle_count_by_user_id.get(user_id, 0),
            )
            for user_id, node in sorted(
                explored_nodes.items(),
                key=lambda item: (
                    0 if item[0] == root_user.user_id else 1,
                    0 if cycle_count_by_user_id.get(item[0], 0) > 0 else 1,
                    item[1].distance_from_root,
                    item[1].full_name.lower(),
                    item[0],
                ),
            )
            if user_id in rendered_user_ids
        )

        rendered_edges = tuple(
            DeepFriendAnalysisEdge(
                edge_id=_edge_id(left_user_id, right_user_id),
                source_node_id=_node_id(left_user_id),
                target_node_id=_node_id(right_user_id),
                connected_seed_indices=(0,),
                is_cycle_edge=edge_key in cycle_edge_keys,
            )
            for edge_key in sorted(rendered_edge_keys)
            for left_user_id, right_user_id in [edge_key]
            if left_user_id in rendered_user_ids and right_user_id in rendered_user_ids
        )

        cycles = tuple(
            DeepFriendAnalysisCycle(
                cycle_id=cycle.cycle_id,
                node_ids=tuple(_node_id(user_id) for user_id in cycle.cycle_user_ids),
                edge_ids=tuple(_edge_id(left_user_id, right_user_id) for left_user_id, right_user_id in cycle.cycle_edge_keys),
                focus_node_ids=tuple(_node_id(user_id) for user_id in cycle.focus_user_ids),
                length=cycle.length,
                closest_distance_from_root=cycle.closest_distance_from_root,
                includes_root=cycle.includes_root,
            )
            for cycle in cycle_descriptors
        )

        root_profile = DeepFriendAnalysisRootProfile(
            input_profile=normalized_profile_reference,
            node_id=_node_id(root_user.user_id),
            user_id=root_user.user_id,
            full_name=root_user.full_name,
            profile_url=root_user.profile_url,
            avatar_url=root_user.avatar_url,
            is_private=root_user.is_private,
            requested_depth=requested_depth,
            direct_connection_count=root_direct_connection_count,
            total_available_connection_count=root_total_available_connection_count,
            is_truncated=root_is_truncated,
        )
        stats = DeepFriendAnalysisStats(
            requested_depth=requested_depth,
            explored_profile_count=explored_profile_count,
            discovered_profile_count=len(explored_nodes),
            rendered_node_count=len(rendered_nodes),
            rendered_edge_count=len(rendered_edges),
            cycle_count=len(cycles),
            cycle_node_count=sum(1 for node in rendered_nodes if node.is_cycle_member),
            cycle_edge_count=sum(1 for edge in rendered_edges if edge.is_cycle_edge),
            private_skipped_count=private_skipped_count,
            truncated_profile_count=truncated_profile_count,
            max_discovered_depth=max((node.distance_from_root for node in explored_nodes.values()), default=0),
            exploration_was_limited=exploration_was_limited,
        )

        return DeepFriendAnalysisResult(
            root_profile=root_profile,
            nodes=rendered_nodes,
            edges=rendered_edges,
            cycles=cycles,
            stats=stats,
        )

    def _fetch_public_friend_batch(self, user_id: int) -> _FetchedFriendBatch:
        try:
            links, total_count = self._friend_links_service.list_friends_by_user_id(
                user_id,
                max_connections=self._max_connections_per_profile,
            )
        except VKApiError as error:
            if error.error_code == PRIVATE_PROFILE_ERROR_CODE:
                return _FetchedFriendBatch(
                    public_links=(),
                    total_available_count=0,
                    private_skipped_count=0,
                    is_truncated=False,
                    is_private=True,
                )
            if error.error_code == DELETED_OR_BANNED_PROFILE_ERROR_CODE:
                return _FetchedFriendBatch(
                    public_links=(),
                    total_available_count=0,
                    private_skipped_count=0,
                    is_truncated=False,
                    is_unavailable=True,
                )
            raise

        public_links = tuple(link for link in links if not link.is_private and not link.is_unavailable)
        private_skipped_count = len(links) - len(public_links)
        return _FetchedFriendBatch(
            public_links=public_links,
            total_available_count=total_count,
            private_skipped_count=private_skipped_count,
            is_truncated=total_count > len(public_links),
        )


def _build_cycle_descriptors(
    *,
    root_user_id: int,
    adjacency: dict[int, set[int]],
    tree_parent_by_user_id: dict[int, int | None],
    explored_nodes: dict[int, _ExploredNode],
) -> tuple[_CycleDescriptor, ...]:
    tree_edge_keys = {
        _edge_key(user_id, parent_user_id)
        for user_id, parent_user_id in tree_parent_by_user_id.items()
        if parent_user_id is not None
    }
    all_edge_keys = {
        _edge_key(left_user_id, right_user_id)
        for left_user_id, neighbors in adjacency.items()
        for right_user_id in neighbors
        if left_user_id < right_user_id
    }
    if not all_edge_keys:
        return ()

    descriptors: list[_CycleDescriptor] = []
    seen_signatures: set[tuple[tuple[int, int], ...]] = set()

    for left_user_id, right_user_id in sorted(all_edge_keys):
        edge_key = _edge_key(left_user_id, right_user_id)
        if edge_key in tree_edge_keys:
            continue

        cycle_user_ids = _build_tree_path_user_ids(
            left_user_id=left_user_id,
            right_user_id=right_user_id,
            tree_parent_by_user_id=tree_parent_by_user_id,
        )
        if len(cycle_user_ids) < 2:
            continue

        cycle_edge_keys = {
            _edge_key(cycle_user_ids[index - 1], cycle_user_ids[index])
            for index in range(1, len(cycle_user_ids))
        }
        cycle_edge_keys.add(edge_key)
        cycle_signature = tuple(sorted(cycle_edge_keys))
        if cycle_signature in seen_signatures:
            continue
        seen_signatures.add(cycle_signature)

        representative_user_id = min(
            cycle_user_ids,
            key=lambda user_id: (
                explored_nodes[user_id].distance_from_root,
                user_id,
            ),
        )
        focus_user_ids = tuple(
            dict.fromkeys(
                [
                    *_build_root_path_user_ids(
                        root_user_id=root_user_id,
                        user_id=representative_user_id,
                        tree_parent_by_user_id=tree_parent_by_user_id,
                    ),
                    *cycle_user_ids,
                ]
            )
        )
        descriptors.append(
            _CycleDescriptor(
                cycle_id=f"cycle:{len(descriptors) + 1}",
                cycle_user_ids=cycle_user_ids,
                cycle_edge_keys=cycle_signature,
                focus_user_ids=focus_user_ids,
                length=len(cycle_user_ids),
                closest_distance_from_root=explored_nodes[representative_user_id].distance_from_root,
                includes_root=root_user_id in cycle_user_ids,
            )
        )

    return tuple(
        sorted(
            descriptors,
            key=lambda item: (
                item.closest_distance_from_root,
                item.length,
                item.cycle_id,
            ),
        )
    )


def _build_tree_path_user_ids(
    *,
    left_user_id: int,
    right_user_id: int,
    tree_parent_by_user_id: dict[int, int | None],
) -> tuple[int, ...]:
    left_ancestors: list[int] = []
    ancestor_positions: dict[int, int] = {}
    current_user_id: int | None = left_user_id
    while current_user_id is not None:
        ancestor_positions[current_user_id] = len(left_ancestors)
        left_ancestors.append(current_user_id)
        current_user_id = tree_parent_by_user_id.get(current_user_id)

    right_branch: list[int] = []
    current_user_id = right_user_id
    while current_user_id is not None and current_user_id not in ancestor_positions:
        right_branch.append(current_user_id)
        current_user_id = tree_parent_by_user_id.get(current_user_id)

    if current_user_id is None:
        return ()

    lca_user_id = current_user_id
    left_segment = left_ancestors[: ancestor_positions[lca_user_id] + 1]
    return tuple(left_segment + list(reversed(right_branch)))


def _build_root_path_user_ids(
    *,
    root_user_id: int,
    user_id: int,
    tree_parent_by_user_id: dict[int, int | None],
) -> tuple[int, ...]:
    chain: list[int] = []
    current_user_id: int | None = user_id
    while current_user_id is not None:
        chain.append(current_user_id)
        if current_user_id == root_user_id:
            break
        current_user_id = tree_parent_by_user_id.get(current_user_id)
    return tuple(reversed(chain))


def _collect_path_edge_keys(
    focus_user_ids: tuple[int, ...],
    tree_parent_by_user_id: dict[int, int | None],
) -> set[tuple[int, int]]:
    edge_keys: set[tuple[int, int]] = set()
    for user_id in focus_user_ids:
        parent_user_id = tree_parent_by_user_id.get(user_id)
        if parent_user_id is None:
            continue
        edge_keys.add(_edge_key(user_id, parent_user_id))
    return edge_keys


def _node_id(user_id: int) -> str:
    return f"vk:{user_id}"


def _edge_id(left_user_id: int, right_user_id: int) -> str:
    source_user_id, target_user_id = _edge_key(left_user_id, right_user_id)
    return f"edge:{source_user_id}:{target_user_id}"


def _edge_key(left_user_id: int, right_user_id: int) -> tuple[int, int]:
    return (left_user_id, right_user_id) if left_user_id < right_user_id else (right_user_id, left_user_id)
