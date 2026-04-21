from __future__ import annotations

from dataclasses import dataclass

from graph_of_god_backend.background.job_manager import BackgroundJobManager
from graph_of_god_backend.core.config import AppConfig
from graph_of_god_backend.modules.vk.auth import build_access_token_provider
from graph_of_god_backend.modules.vk.client import VKApiClient
from graph_of_god_backend.modules.vk.friend_links_service import FriendLinksService
from graph_of_god_backend.modules.vk.entities import FriendLinksResult, SocialGraphResult
from graph_of_god_backend.modules.vk.social_graph_service import SocialGraphService


@dataclass(slots=True)
class AppContainer:
    config: AppConfig
    friend_links_service: FriendLinksService
    social_graph_service: SocialGraphService
    friend_links_job_manager: BackgroundJobManager[str, FriendLinksResult]
    social_graph_job_manager: BackgroundJobManager[tuple[str, ...], SocialGraphResult]

    def shutdown(self) -> None:
        self.friend_links_job_manager.shutdown()
        self.social_graph_job_manager.shutdown()


def build_container() -> AppContainer:
    config = AppConfig.from_env()
    vk_api_client = VKApiClient(
        access_token_provider=build_access_token_provider(config),
        api_version=config.vk_api_version,
        timeout_seconds=config.request_timeout_seconds,
        base_url=config.vk_api_base_url,
    )
    friend_links_service = FriendLinksService(
        vk_api_client,
        max_connections_per_profile=config.vk_max_connections_per_profile,
    )
    social_graph_service = SocialGraphService(
        friend_links_service,
        max_connections_per_seed=config.vk_max_graph_connections_per_seed,
    )
    friend_links_job_manager = BackgroundJobManager[str, FriendLinksResult](
        resolver=friend_links_service.collect_friend_links,
        max_workers=config.job_workers,
        retention_seconds=config.job_retention_seconds,
    )
    social_graph_job_manager = BackgroundJobManager[tuple[str, ...], SocialGraphResult](
        resolver=social_graph_service.build_social_graph,
        max_workers=config.job_workers,
        retention_seconds=config.job_retention_seconds,
    )
    return AppContainer(
        config=config,
        friend_links_service=friend_links_service,
        social_graph_service=social_graph_service,
        friend_links_job_manager=friend_links_job_manager,
        social_graph_job_manager=social_graph_job_manager,
    )
