from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from graph_of_god_backend.api.dependencies import get_social_graph_job_manager
from graph_of_god_backend.api.schemas.social_graph import (
    SocialGraphEdgeResponse,
    SocialGraphJobResponse,
    SocialGraphNodeResponse,
    SocialGraphOverlapResponse,
    SocialGraphResultResponse,
    SocialGraphSeedProfileResponse,
    SocialGraphStatsResponse,
)
from graph_of_god_backend.background.job_manager import BackgroundJob, BackgroundJobManager
from graph_of_god_backend.modules.vk.entities import SocialGraphResult

router = APIRouter(prefix="/social-graphs/jobs", tags=["social-graphs"])


@router.post(
    "",
    response_model=SocialGraphJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить фоновую задачу на построение графа социальных связей",
)
async def create_social_graph_job(
    request: Request,
    profiles: Annotated[
        list[str],
        Query(
            ...,
            min_length=1,
            max_length=5,
            description=(
                "Список VK-профилей для построения social graph. "
                "В Swagger UI можно добавлять и удалять элементы через Add item."
            ),
            openapi_examples={
                "two_profiles": {
                    "summary": "Два профиля VK",
                    "value": ["https://vk.com/durov", "https://vk.com/id1"],
                }
            },
        ),
    ],
    job_manager: BackgroundJobManager[tuple[str, ...], SocialGraphResult] = Depends(
        get_social_graph_job_manager
    ),
) -> SocialGraphJobResponse:
    job = job_manager.submit(tuple(profiles))
    return _to_job_response(job, request)


@router.get(
    "/{job_id}",
    response_model=SocialGraphJobResponse,
    summary="Получить статус и результат задачи построения social graph",
)
async def get_social_graph_job(
    job_id: str,
    request: Request,
    job_manager: BackgroundJobManager[tuple[str, ...], SocialGraphResult] = Depends(
        get_social_graph_job_manager
    ),
) -> SocialGraphJobResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return _to_job_response(job, request)


def _to_job_response(
    job: BackgroundJob[tuple[str, ...], SocialGraphResult],
    request: Request,
) -> SocialGraphJobResponse:
    return SocialGraphJobResponse(
        job_id=job.job_id,
        profiles=list(job.input_payload),
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        result=_to_result_response(job.result),
        error_message=job.error_message,
        status_url=str(request.url_for("get_social_graph_job", job_id=job.job_id)),
    )


def _to_result_response(result: SocialGraphResult | None) -> SocialGraphResultResponse | None:
    if result is None:
        return None

    return SocialGraphResultResponse(
        seed_profiles=[
            SocialGraphSeedProfileResponse(
                seed_index=seed_profile.seed_index,
                input_profile=seed_profile.input_profile,
                node_id=seed_profile.node_id,
                user_id=seed_profile.user_id,
                full_name=seed_profile.full_name,
                profile_url=seed_profile.profile_url,
                avatar_url=seed_profile.avatar_url,
                source_kind=seed_profile.source_kind,
                is_private=seed_profile.is_private,
                connection_count=seed_profile.connection_count,
                total_available_connection_count=seed_profile.total_available_connection_count,
                is_truncated=seed_profile.is_truncated,
                connection_node_ids=list(seed_profile.connection_node_ids),
            )
            for seed_profile in result.seed_profiles
        ],
        nodes=[
            SocialGraphNodeResponse(
                node_id=node.node_id,
                user_id=node.user_id,
                full_name=node.full_name,
                profile_url=node.profile_url,
                avatar_url=node.avatar_url,
                is_seed=node.is_seed,
                seed_indices=list(node.seed_indices),
                connected_seed_indices=list(node.connected_seed_indices),
                shared_seed_count=node.shared_seed_count,
                is_private=node.is_private,
            )
            for node in result.nodes
        ],
        edges=[
            SocialGraphEdgeResponse(
                edge_id=edge.edge_id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                connected_seed_indices=list(edge.connected_seed_indices),
            )
            for edge in result.edges
        ],
        overlaps=[
            SocialGraphOverlapResponse(
                left_seed_index=overlap.left_seed_index,
                right_seed_index=overlap.right_seed_index,
                shared_node_ids=list(overlap.shared_node_ids),
                shared_count=overlap.shared_count,
            )
            for overlap in result.overlaps
        ],
        stats=SocialGraphStatsResponse(
            seed_count=result.stats.seed_count,
            node_count=result.stats.node_count,
            edge_count=result.stats.edge_count,
            overlap_pair_count=result.stats.overlap_pair_count,
            shared_node_count=result.stats.shared_node_count,
            truncated_seed_count=result.stats.truncated_seed_count,
        ),
    )
