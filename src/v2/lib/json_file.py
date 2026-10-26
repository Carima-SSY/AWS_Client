"""
JSON 파일 안전 읽기/쓰기 (lib/json_file.py)

status/file/cam 스레드와 IoT Core 메시지 핸들러가 같은 JSON 파일(device-log.json,
print-history.json, 로그 파일, 상태 파일 등)을 동시에 읽고 쓴다. open(..., 'w')는
파일을 먼저 0바이트로 비운 뒤 쓰기 때문에, 그 사이에 다른 스레드가 읽으면 빈 파일을
읽어 "Expecting value: line 1 column 1 (char 0)"이 나고, 쓰다가 꺼지면 빈 파일이 남는다.

- write_json : 같은 폴더의 임시 파일에 끝까지 쓴 뒤 os.replace()로 바꿔치기 — 읽는 쪽은
               항상 이전 내용 또는 새 내용 전체만 보고, 쓰다가 꺼져도 이전 내용이 남는다.
- lock(path) : 경로별 Lock — 어느 모듈에서 부르든 같은 파일이면 같은 Lock이다.
- update_json: Lock을 잡은 채 읽기 → fn(data)로 수정 → 쓰기. 두 스레드가 같은 파일을
               읽고-고쳐-쓸 때 한쪽 변경이 덮여 사라지지 않게 한다.

Lock은 이 프로세스 안의 스레드끼리만 순서를 맞춘다. 장비 프로그램처럼 다른 프로세스가
같은 파일을 쓰는 경우는 막지 못하지만, 이쪽 쓰기가 원자적이라 상대가 빈 파일을 읽지는 않는다.
"""

import json
import os
import stat
import tempfile
import threading
import time

_locks: dict = {}
_locks_guard = threading.Lock()


def lock(path: str) -> threading.RLock:
    """경로별 Lock(재진입 가능 — update_json 안에서 read_json/write_json을 다시 불러도 됨)."""
    key = os.path.normcase(os.path.abspath(path))
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


def read_json(path: str):
    with lock(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)


def write_json(path: str, data, **dump_kwargs) -> None:
    dump_kwargs.setdefault("ensure_ascii", False)
    dump_kwargs.setdefault("indent", 4)
    directory = os.path.dirname(os.path.abspath(path))
    with lock(path):
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=f".{os.path.basename(path)}.", suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(data, f, **dump_kwargs)
                f.flush()
                os.fsync(f.fileno())
            # mkstemp는 0600으로 만든다 — 바꿔치기 후에도 기존 파일 권한(없으면 0644)을 유지
            mode = stat.S_IMODE(os.stat(path).st_mode) if os.path.exists(path) else 0o644
            os.chmod(tmp, mode)
            _replace(tmp, path)
        except BaseException:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise


def update_json(path: str, fn):
    """Lock 안에서 읽기 → fn(data)(제자리 수정) → 쓰기. 수정된 data를 반환한다."""
    with lock(path):
        data = read_json(path)
        fn(data)
        write_json(path, data)
        return data


def _replace(src: str, dst: str, retries: int = 10) -> None:
    # Windows에서는 다른 프로세스가 dst를 열어 둔 순간 os.replace가 PermissionError를
    # 낸다 — 잠깐 기다렸다 다시 시도한다.
    for attempt in range(retries):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(0.05)
