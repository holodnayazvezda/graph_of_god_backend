from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SocialGraphSeedProfileResponse(BaseModel):
    seed_index: int
    input_profile: str
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None = None
    source_kind: Literal["friends", "followers", "private"]
    is_private: bool
    connection_count: int
    total_available_connection_count: int
    is_truncated: bool
    connection_node_ids: list[str]


class SocialGraphNodeResponse(BaseModel):
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None = None
    is_seed: bool
    seed_indices: list[int]
    connected_seed_indices: list[int]
    shared_seed_count: int
    is_private: bool


class SocialGraphEdgeResponse(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    connected_seed_indices: list[int]


class SocialGraphOverlapResponse(BaseModel):
    left_seed_index: int
    right_seed_index: int
    shared_node_ids: list[str]
    shared_count: int


class SocialGraphStatsResponse(BaseModel):
    seed_count: int
    node_count: int
    edge_count: int
    overlap_pair_count: int
    shared_node_count: int
    truncated_seed_count: int


class SocialGraphResultResponse(BaseModel):
    seed_profiles: list[SocialGraphSeedProfileResponse]
    nodes: list[SocialGraphNodeResponse]
    edges: list[SocialGraphEdgeResponse]
    overlaps: list[SocialGraphOverlapResponse]
    stats: SocialGraphStatsResponse


class SocialGraphJobResponse(BaseModel):
    job_id: str
    profiles: list[str]
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    result: SocialGraphResultResponse | None = None
    error_message: str | None = None
    status_url: str
