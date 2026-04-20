from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str


class FriendLinksJobCreateRequest(BaseModel):
    profile: str = Field(..., min_length=1, description="Ссылка на профиль VK, screen name или id.")


class ProfileSummaryResponse(BaseModel):
    user_id: int
    full_name: str
    url: str
    avatar_url: str | None = None


class FriendLinkResponse(BaseModel):
    user_id: int
    full_name: str
    url: str
    avatar_url: str | None = None


class FriendLinksResultResponse(BaseModel):
    profile: ProfileSummaryResponse
    links: list[FriendLinkResponse]
    is_private: bool
    source_kind: Literal["friends", "followers", "private"]
    returned_count: int
    total_available_count: int
    is_truncated: bool
    max_connection_limit: int


class FriendLinksJobResponse(BaseModel):
    job_id: str
    profile_reference: str
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    result: FriendLinksResultResponse | None = None
    error_message: str | None = None
    status_url: str
