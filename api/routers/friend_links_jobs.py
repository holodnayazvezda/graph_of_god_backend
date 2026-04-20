from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from graph_of_god_backend.api.dependencies import get_friend_links_job_manager
from graph_of_god_backend.background.job_manager import BackgroundJob, BackgroundJobManager
from graph_of_god_backend.api.schemas.friend_links import (
    FriendLinkResponse,
    FriendLinksJobCreateRequest,
    FriendLinksJobResponse,
    FriendLinksResultResponse,
    ProfileSummaryResponse,
)
from graph_of_god_backend.modules.vk.entities import FriendLinksResult

router = APIRouter(prefix="/friend-links/jobs", tags=["friend-links"])


@router.post(
    "",
    response_model=FriendLinksJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить фоновую задачу на сбор друзей или подписчиков профиля",
)
async def create_friend_links_job(
    payload: FriendLinksJobCreateRequest,
    request: Request,
    job_manager: BackgroundJobManager[str, FriendLinksResult] = Depends(get_friend_links_job_manager),
) -> FriendLinksJobResponse:
    job = job_manager.submit(payload.profile)
    return _to_job_response(job, request)


@router.get(
    "/{job_id}",
    response_model=FriendLinksJobResponse,
    summary="Получить статус и результат фоновой задачи",
)
async def get_friend_links_job(
    job_id: str,
    request: Request,
    job_manager: BackgroundJobManager[str, FriendLinksResult] = Depends(get_friend_links_job_manager),
) -> FriendLinksJobResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return _to_job_response(job, request)


def _to_job_response(
    job: BackgroundJob[str, FriendLinksResult],
    request: Request,
) -> FriendLinksJobResponse:
    return FriendLinksJobResponse(
        job_id=job.job_id,
        profile_reference=job.input_payload,
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        result=_to_result_response(job.result),
        error_message=job.error_message,
        status_url=str(request.url_for("get_friend_links_job", job_id=job.job_id)),
    )


def _to_result_response(result: FriendLinksResult | None) -> FriendLinksResultResponse | None:
    if result is None:
        return None

    return FriendLinksResultResponse(
        profile=ProfileSummaryResponse(
            user_id=result.user.user_id,
            full_name=result.user.full_name,
            url=result.user.profile_url,
            avatar_url=result.user.avatar_url,
        ),
        links=[
            FriendLinkResponse(
                user_id=friend_link.user_id,
                full_name=friend_link.full_name,
                url=friend_link.url,
                avatar_url=friend_link.avatar_url,
            )
            for friend_link in result.links
        ],
        is_private=result.is_private,
        source_kind=result.source_kind,
        returned_count=result.returned_count,
        total_available_count=result.total_available_count,
        is_truncated=result.is_truncated,
        max_connection_limit=result.max_connection_limit,
    )
