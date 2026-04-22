from __future__ import annotations

from fastapi import Request

from graph_of_god_backend.background.job_manager import BackgroundJobManager
from graph_of_god_backend.container import AppContainer
from graph_of_god_backend.modules.vk.entities import (
    DeepFriendAnalysisResult,
    FriendLinksResult,
    SocialGraphResult,
)


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_friend_links_job_manager(
    request: Request,
) -> BackgroundJobManager[str, FriendLinksResult]:
    return get_container(request).friend_links_job_manager


def get_social_graph_job_manager(
    request: Request,
) -> BackgroundJobManager[tuple[str, ...], SocialGraphResult]:
    return get_container(request).social_graph_job_manager


def get_deep_friend_analysis_job_manager(
    request: Request,
) -> BackgroundJobManager[tuple[str, int], DeepFriendAnalysisResult]:
    return get_container(request).deep_friend_analysis_job_manager
