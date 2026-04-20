from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Callable, Generic, TypeVar
from uuid import uuid4

from graph_of_god_backend.core.exceptions import GraphOfGodBackendError

InputT = TypeVar("InputT")
ResultT = TypeVar("ResultT")


@dataclass(slots=True)
class BackgroundJob(Generic[InputT, ResultT]):
    job_id: str
    input_payload: InputT
    status: str
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
    result: ResultT | None = None
    error_message: str | None = None


class BackgroundJobManager(Generic[InputT, ResultT]):
    def __init__(
        self,
        *,
        resolver: Callable[[InputT], ResultT],
        max_workers: int,
        retention_seconds: int,
    ) -> None:
        self._resolver = resolver
        self._retention_seconds = retention_seconds
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="graph-of-god-backend-job",
        )
        self._jobs: dict[str, BackgroundJob[InputT, ResultT]] = {}
        self._lock = RLock()

    def submit(self, input_payload: InputT) -> BackgroundJob[InputT, ResultT]:
        now = _utcnow()
        job = BackgroundJob(
            job_id=uuid4().hex,
            input_payload=input_payload,
            status="queued",
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            self._cleanup_expired_locked(now)
            self._jobs[job.job_id] = job

        self._executor.submit(self._run_job, job.job_id)
        return replace(job)

    def get(self, job_id: str) -> BackgroundJob[InputT, ResultT] | None:
        with self._lock:
            self._cleanup_expired_locked(_utcnow())
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return replace(job)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.status = "running"
            job.updated_at = _utcnow()
            input_payload = job.input_payload

        try:
            result = self._resolver(input_payload)
        except GraphOfGodBackendError as error:
            self._mark_failed(job_id, str(error))
            return
        except Exception as error:
            self._mark_failed(job_id, f"Unexpected backend error: {error}")
            return

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = _utcnow()
            job.status = "succeeded"
            job.updated_at = now
            job.finished_at = now
            job.result = result
            job.error_message = None

    def _mark_failed(self, job_id: str, error_message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            now = _utcnow()
            job.status = "failed"
            job.updated_at = now
            job.finished_at = now
            job.result = None
            job.error_message = error_message

    def _cleanup_expired_locked(self, now: datetime) -> None:
        expire_before = now - timedelta(seconds=self._retention_seconds)
        expired_job_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.finished_at is not None and job.finished_at < expire_before
        ]
        for job_id in expired_job_ids:
            del self._jobs[job_id]


def _utcnow() -> datetime:
    return datetime.now(UTC)
