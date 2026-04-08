"""
Discovery 사이클 락 — collection별 fcntl flock.

목적:
    - 같은 collection을 동시에 두 번 돌리는 것을 방지 (LOCK_EX | LOCK_NB)
    - 다른 collection은 병렬 진행 가능 (락 파일이 collection별로 분리)
    - 프로세스가 죽으면 OS가 자동으로 락 해제 (fcntl 특성)

사용:
    with discovery_lock("CF4"):
        run_discovery_cycle("CF4", ...)

호출부 변환:
    LockedError → HTTP 409 Conflict (dashboard router)
    LockedError → exit 1 + stderr 메시지 (CLI)

Phase E §1 — Mac Mini, single host single worker, fcntl 사용 가능.
data/ 하위 락 파일 OK (iCloud 동기화 아님).
"""
from __future__ import annotations

import errno
import fcntl
import logging
import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


# 프로젝트 루트의 data/ 디렉토리. database.py와 같은 규약.
_BASE_DIR = Path(__file__).resolve().parent.parent.parent
_LOCK_DIR = _BASE_DIR / "data"


class LockedError(RuntimeError):
    """이미 같은 collection의 사이클이 진행 중일 때 raise."""

    def __init__(self, collection_id: str, lock_path: str):
        self.collection_id = collection_id
        self.lock_path = lock_path
        super().__init__(
            f"Discovery 사이클이 이미 실행 중입니다 (collection={collection_id}, lock={lock_path})"
        )


def _sanitize(collection_id: str) -> str:
    """파일시스템 안전 이름. 영숫자/underscore/hyphen만 허용."""
    if not collection_id:
        raise ValueError("collection_id는 비어있을 수 없습니다")
    safe = re.sub(r"[^A-Za-z0-9_\-]", "_", collection_id)
    if not safe:
        raise ValueError(f"collection_id가 유효하지 않습니다: {collection_id!r}")
    return safe


def lock_path_for(collection_id: str) -> Path:
    """주어진 collection_id에 해당하는 락 파일 경로."""
    safe = _sanitize(collection_id)
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    return _LOCK_DIR / f"discovery_{safe}.lock"


@contextmanager
def discovery_lock(collection_id: str) -> Iterator[Path]:
    """fcntl flock 기반 컨텍스트 매니저.

    LOCK_EX | LOCK_NB 로 즉시 획득 시도, 실패 시 LockedError raise.
    예외 발생/정상 종료 어떤 경우든 락은 자동 해제 (fd close).

    락 파일에는 hostname:pid 를 기록하여 디버깅에 활용.
    """
    path = lock_path_for(collection_id)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno in (errno.EWOULDBLOCK, errno.EAGAIN):
                os.close(fd)
                raise LockedError(collection_id, str(path)) from e
            os.close(fd)
            raise

        # 잠금 성공 → 메타 기록
        try:
            os.ftruncate(fd, 0)
            stamp = f"{os.uname().nodename}:{os.getpid()}\n".encode("utf-8")
            os.write(fd, stamp)
            os.fsync(fd)
        except OSError as e:
            logger.warning(f"discovery_lock 메타 기록 실패: {e}")

        logger.info(f"[discovery_lock] 획득: {path} ({os.getpid()})")
        try:
            yield path
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError as e:
                logger.warning(f"discovery_lock 해제 실패: {e}")
            logger.info(f"[discovery_lock] 해제: {path} ({os.getpid()})")
    finally:
        try:
            os.close(fd)
        except OSError:
            pass


def locked_by(collection_id: str) -> str | None:
    """현재 락 파일의 소유자 메타 (hostname:pid). 없으면 None."""
    path = lock_path_for(collection_id)
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None
