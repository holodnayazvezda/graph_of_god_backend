from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class VKUser:
    user_id: int
    full_name: str
    domain: str | None = None
    avatar_url: str | None = None
    followers_count: int = 0
    is_closed: bool = False
    can_access_closed: bool = True
    deactivated_status: Literal["deleted", "banned"] | None = None

    @property
    def profile_url(self) -> str:
        if self.domain:
            return f"https://vk.com/{self.domain}"
        return f"https://vk.com/id{self.user_id}"

    @property
    def is_private(self) -> bool:
        return self.is_closed and not self.can_access_closed

    @property
    def is_unavailable(self) -> bool:
        return self.deactivated_status is not None


@dataclass(frozen=True, slots=True)
class FriendLink:
    user_id: int
    full_name: str
    url: str
    avatar_url: str | None = None
    is_closed: bool = False
    can_access_closed: bool = True
    deactivated_status: Literal["deleted", "banned"] | None = None

    @property
    def is_private(self) -> bool:
        return self.is_closed and not self.can_access_closed

    @property
    def is_unavailable(self) -> bool:
        return self.deactivated_status is not None


@dataclass(frozen=True, slots=True)
class FriendLinksResult:
    user: VKUser
    links: tuple[FriendLink, ...]
    is_private: bool
    source_kind: Literal["friends", "followers", "private"]
    returned_count: int
    total_available_count: int
    is_truncated: bool
    max_connection_limit: int


@dataclass(frozen=True, slots=True)
class SocialGraphSeedProfile:
    seed_index: int
    input_profile: str
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None
    source_kind: Literal["friends", "followers", "private"]
    is_private: bool
    connection_count: int
    total_available_connection_count: int
    is_truncated: bool
    connection_node_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SocialGraphNode:
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None
    is_seed: bool
    seed_indices: tuple[int, ...]
    connected_seed_indices: tuple[int, ...]
    shared_seed_count: int
    is_private: bool


@dataclass(frozen=True, slots=True)
class SocialGraphEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    connected_seed_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class SocialGraphOverlap:
    left_seed_index: int
    right_seed_index: int
    shared_node_ids: tuple[str, ...]
    shared_count: int


@dataclass(frozen=True, slots=True)
class SocialGraphStats:
    seed_count: int
    node_count: int
    edge_count: int
    overlap_pair_count: int
    shared_node_count: int
    truncated_seed_count: int


@dataclass(frozen=True, slots=True)
class SocialGraphResult:
    seed_profiles: tuple[SocialGraphSeedProfile, ...]
    nodes: tuple[SocialGraphNode, ...]
    edges: tuple[SocialGraphEdge, ...]
    overlaps: tuple[SocialGraphOverlap, ...]
    stats: SocialGraphStats


@dataclass(frozen=True, slots=True)
class DeepFriendAnalysisRootProfile:
    input_profile: str
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None
    is_private: bool
    requested_depth: int
    direct_connection_count: int
    total_available_connection_count: int
    is_truncated: bool


@dataclass(frozen=True, slots=True)
class DeepFriendAnalysisNode:
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None
    is_seed: bool
    seed_indices: tuple[int, ...]
    connected_seed_indices: tuple[int, ...]
    shared_seed_count: int
    is_private: bool
    distance_from_root: int
    is_cycle_member: bool
    cycle_count: int


@dataclass(frozen=True, slots=True)
class DeepFriendAnalysisEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    connected_seed_indices: tuple[int, ...]
    is_cycle_edge: bool


@dataclass(frozen=True, slots=True)
class DeepFriendAnalysisCycle:
    cycle_id: str
    node_ids: tuple[str, ...]
    edge_ids: tuple[str, ...]
    focus_node_ids: tuple[str, ...]
    length: int
    closest_distance_from_root: int
    includes_root: bool


@dataclass(frozen=True, slots=True)
class DeepFriendAnalysisStats:
    requested_depth: int
    explored_profile_count: int
    discovered_profile_count: int
    rendered_node_count: int
    rendered_edge_count: int
    cycle_count: int
    cycle_node_count: int
    cycle_edge_count: int
    private_skipped_count: int
    truncated_profile_count: int
    max_discovered_depth: int
    exploration_was_limited: bool


@dataclass(frozen=True, slots=True)
class DeepFriendAnalysisResult:
    root_profile: DeepFriendAnalysisRootProfile
    nodes: tuple[DeepFriendAnalysisNode, ...]
    edges: tuple[DeepFriendAnalysisEdge, ...]
    cycles: tuple[DeepFriendAnalysisCycle, ...]
    stats: DeepFriendAnalysisStats
