from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from graph_of_god_backend.api.dependencies import get_deep_friend_analysis_job_manager
from graph_of_god_backend.api.schemas.deep_friend_analysis import (
    DeepFriendAnalysisCycleResponse,
    DeepFriendAnalysisEdgeResponse,
    DeepFriendAnalysisJobCreateRequest,
    DeepFriendAnalysisJobResponse,
    DeepFriendAnalysisNodeResponse,
    DeepFriendAnalysisResultResponse,
    DeepFriendAnalysisRootProfileResponse,
    DeepFriendAnalysisStatsResponse,
)
from graph_of_god_backend.background.job_manager import BackgroundJob, BackgroundJobManager
from graph_of_god_backend.modules.vk.entities import DeepFriendAnalysisResult

router = APIRouter(prefix="/deep-friend-analysis/jobs", tags=["deep-friend-analysis"])


@router.post(
    "",
    response_model=DeepFriendAnalysisJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Запустить глубокий анализ друзей и поиск циклов",
)
async def create_deep_friend_analysis_job(
    payload: DeepFriendAnalysisJobCreateRequest,
    request: Request,
    job_manager: BackgroundJobManager[tuple[str, int], DeepFriendAnalysisResult] = Depends(
        get_deep_friend_analysis_job_manager
    ),
) -> DeepFriendAnalysisJobResponse:
    job = job_manager.submit((payload.profile, payload.depth))
    return _to_job_response(job, request)


@router.get(
    "/{job_id}",
    response_model=DeepFriendAnalysisJobResponse,
    summary="Получить статус и результат глубокого анализа друзей",
)
async def get_deep_friend_analysis_job(
    job_id: str,
    request: Request,
    job_manager: BackgroundJobManager[tuple[str, int], DeepFriendAnalysisResult] = Depends(
        get_deep_friend_analysis_job_manager
    ),
) -> DeepFriendAnalysisJobResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return _to_job_response(job, request)


def _to_job_response(
    job: BackgroundJob[tuple[str, int], DeepFriendAnalysisResult],
    request: Request,
) -> DeepFriendAnalysisJobResponse:
    return DeepFriendAnalysisJobResponse(
        job_id=job.job_id,
        profile=job.input_payload[0],
        depth=job.input_payload[1],
        status=job.status,
        created_at=job.created_at,
        updated_at=job.updated_at,
        finished_at=job.finished_at,
        result=_to_result_response(job.result),
        error_message=job.error_message,
        status_url=str(request.url_for("get_deep_friend_analysis_job", job_id=job.job_id)),
    )


def _to_result_response(result: DeepFriendAnalysisResult | None) -> DeepFriendAnalysisResultResponse | None:
    if result is None:
        return None

    return DeepFriendAnalysisResultResponse(
        root_profile=DeepFriendAnalysisRootProfileResponse(
            input_profile=result.root_profile.input_profile,
            node_id=result.root_profile.node_id,
            user_id=result.root_profile.user_id,
            full_name=result.root_profile.full_name,
            profile_url=result.root_profile.profile_url,
            avatar_url=result.root_profile.avatar_url,
            is_private=result.root_profile.is_private,
            requested_depth=result.root_profile.requested_depth,
            direct_connection_count=result.root_profile.direct_connection_count,
            total_available_connection_count=result.root_profile.total_available_connection_count,
            is_truncated=result.root_profile.is_truncated,
        ),
        nodes=[
            DeepFriendAnalysisNodeResponse(
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
                distance_from_root=node.distance_from_root,
                is_cycle_member=node.is_cycle_member,
                cycle_count=node.cycle_count,
            )
            for node in result.nodes
        ],
        edges=[
            DeepFriendAnalysisEdgeResponse(
                edge_id=edge.edge_id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                connected_seed_indices=list(edge.connected_seed_indices),
                is_cycle_edge=edge.is_cycle_edge,
            )
            for edge in result.edges
        ],
        cycles=[
            DeepFriendAnalysisCycleResponse(
                cycle_id=cycle.cycle_id,
                node_ids=list(cycle.node_ids),
                edge_ids=list(cycle.edge_ids),
                focus_node_ids=list(cycle.focus_node_ids),
                length=cycle.length,
                closest_distance_from_root=cycle.closest_distance_from_root,
                includes_root=cycle.includes_root,
            )
            for cycle in result.cycles
        ],
        stats=DeepFriendAnalysisStatsResponse(
            requested_depth=result.stats.requested_depth,
            explored_profile_count=result.stats.explored_profile_count,
            discovered_profile_count=result.stats.discovered_profile_count,
            rendered_node_count=result.stats.rendered_node_count,
            rendered_edge_count=result.stats.rendered_edge_count,
            cycle_count=result.stats.cycle_count,
            cycle_node_count=result.stats.cycle_node_count,
            cycle_edge_count=result.stats.cycle_edge_count,
            private_skipped_count=result.stats.private_skipped_count,
            truncated_profile_count=result.stats.truncated_profile_count,
            max_discovered_depth=result.stats.max_discovered_depth,
            exploration_was_limited=result.stats.exploration_was_limited,
        ),
    )
