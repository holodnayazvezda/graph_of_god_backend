from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DeepFriendAnalysisJobCreateRequest(BaseModel):
    profile: str = Field(..., min_length=1)
    depth: int = Field(..., ge=1)


class DeepFriendAnalysisRootProfileResponse(BaseModel):
    input_profile: str
    node_id: str
    user_id: int
    full_name: str
    profile_url: str
    avatar_url: str | None = None
    is_private: bool
    requested_depth: int
    direct_connection_count: int
    total_available_connection_count: int
    is_truncated: bool


class DeepFriendAnalysisNodeResponse(BaseModel):
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
    distance_from_root: int
    is_cycle_member: bool
    cycle_count: int


class DeepFriendAnalysisEdgeResponse(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    connected_seed_indices: list[int]
    is_cycle_edge: bool


class DeepFriendAnalysisCycleResponse(BaseModel):
    cycle_id: str
    node_ids: list[str]
    edge_ids: list[str]
    focus_node_ids: list[str]
    length: int
    closest_distance_from_root: int
    includes_root: bool


class DeepFriendAnalysisStatsResponse(BaseModel):
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


class DeepFriendAnalysisResultResponse(BaseModel):
    root_profile: DeepFriendAnalysisRootProfileResponse
    nodes: list[DeepFriendAnalysisNodeResponse]
    edges: list[DeepFriendAnalysisEdgeResponse]
    cycles: list[DeepFriendAnalysisCycleResponse]
    stats: DeepFriendAnalysisStatsResponse


class DeepFriendAnalysisJobResponse(BaseModel):
    job_id: str
    profile: str
    depth: int
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    result: DeepFriendAnalysisResultResponse | None = None
    error_message: str | None = None
    status_url: str
