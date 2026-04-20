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

    @property
    def profile_url(self) -> str:
        if self.domain:
            return f"https://vk.com/{self.domain}"
        return f"https://vk.com/id{self.user_id}"

    @property
    def is_private(self) -> bool:
        return self.is_closed and not self.can_access_closed


@dataclass(frozen=True, slots=True)
class FriendLink:
    user_id: int
    full_name: str
    url: str
    avatar_url: str | None = None


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
