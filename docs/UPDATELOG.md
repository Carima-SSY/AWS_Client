# UPDATELOG

`v1`/`v2`는 같은 프로젝트(Carima 3D 프린터용 AWS Client — MQTT 기반 디바이스 통신 + 슬라이스 파일 관리 앱)의 버전이다. 이 문서는 **v2에서 새로 추가되거나 바뀐 코드와 기능**을 정리한다.

## v2 업데이트 요약

| # | 기능 | 내용 |
|---|---|---|
| 1 | 기종별 슬라이스 형식 지원 | 폴더형/파일형 슬라이스를 장비 타입별로 구분해 목록·수신·삭제를 모두 처리한다. |
| 2 | JSON 파일 안전 입출력 | 원자적 쓰기와 파일별 Lock으로, 스레드끼리 동시에 접근해도 빈 파일을 읽지 않게 했다(`Expecting value` 오류 해결). |
| 3 | 업로드 대기 목록 유실 방지 | 업로드가 끝난 항목만 목록에서 빼서, 업로드 중에 추가된 로그·출력 이력이 사라지지 않는다. |
| 4 | 스레드 루프 예외 처리 | 예외가 나도 주기대로 쉬고, traceback으로 발생 위치를 출력한다. |

### 변경 파일

| 파일 | v1 → v2 | 관련 기능 |
|---|---|---|
| `lib/file_manager.py` | 395줄 → 449줄 | 1, 2, 3 |
| `lib/json_file.py` | **신규** (85줄) | 2 |
| `lib/log_manager.py` | 41줄 → 37줄 | 2 |
| `lib/status_manager.py` | 114줄 → 109줄 | 2 |
| `AWSClientApp.py` | 552줄 → 554줄 | 2, 3, 4 |

그 외 파일(`lib/aws.py`, `lib/cam_manager.py`, `lib/status.py`, `lib/img_process.py`, `requirements.txt`, `client-config.json`, `test/` 전체)은 v1과 같다. 새 의존성은 없다. 모두 표준 라이브러리(`zipfile`, `io`, `tempfile`, `threading`, `traceback`)로 구현했다.

---

## 1. 기종별 슬라이스 형식 지원 (`lib/file_manager.py`)

### 배경

슬라이서가 내보내는 슬라이스 형식은 기종마다 다르다.
- **X1/DM400**: 슬라이스를 **폴더**로 내보낸다.
- **그 외 기종**(DM4K/IML/IML16K/IMDC/IMD/ZENESIS): `.crmaslice`/`.cws`/`.cmz`를 **압축 파일 하나**로 내보낸다.

v1은 이 구분 없이 모든 슬라이스를 폴더로 취급했다. 파일형 슬라이스를 처리하는 자리(`get_print_data`의 `slices["files"]` 루프)는 `pass`만 있는 미완성 상태였다. 그래서 파일형 기종의 슬라이스는 목록에 나타나지 않았다.

### 1-1. 기종별 슬라이스 모드 매핑 — `SLICE_FORMAT_MODE_BY_DEVICE`, `get_slice_mode()`

장비 타입과 확장자로 `"folder"`(폴더형) 또는 `"file"`(파일형)을 정한다. 확장자는 대소문자를 구분하지 않는다. 매핑에 없는 조합은 `None`이다. 기준은 `get_print_recipe`/`get_device_setting`에 이미 있던 `device_type` 분기와 같다.

```python
SLICE_FORMAT_MODE_BY_DEVICE = {
    "X1":      {".slice": "folder", ".crmaslice": "folder"},
    "DM400":   {".slice": "folder", ".crmaslice": "folder"},
    "DM4K":    {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"},
    "IML":     {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"},
    "IML16K":  {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"},
    "IMDC":    {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"},
    "IMD":     {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"},
    "ZENESIS": {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"},
}

def get_slice_mode(self, ext: str):
    return SLICE_FORMAT_MODE_BY_DEVICE.get(self.device_type, {}).get(ext.lower())
```

이 매핑이 v1의 `is_slicefolder()`/`is_slicefile()`를 대신한다. v1의 두 함수는 이름에 확장자 문자열이 들어 있는지만 검사했다.

### 1-2. 파일형 슬라이스 정보 추출 — `get_filetype_slice_data(path)`

- 압축을 **풀지 않고** zip 내부 파일 목록만 읽어 다음 두 가지를 확인한다.
  - preview 이미지가 있는지
  - `.idx` 또는 `.gcode`가 있는지
- 유효성 기준은 폴더형 슬라이스와 같다.
- 유효하면 `{"preview": <120px WEBP base64>, "size": <파일 크기>}`를 반환한다.
- 유효하지 않거나 zip을 읽지 못하면 `None`을 반환한다.

### 1-3. 메모리 데이터로 미리보기 인코딩 — `encode_previewimg_bytes(data, width)`

- zip 내부의 preview는 파일 경로 없이 바이트로만 읽힌다. 그래서 바이트 데이터를 받아 리사이즈하고 WEBP base64로 인코딩하는 함수를 따로 두었다.
- 기존 `encode_previewimg(file, width)`는 파일을 읽어 이 함수에 넘기는 래퍼가 되었다.

### 1-4. 폴더 실제 용량 계산 — `get_folder_size(path)`

- 폴더 안의 모든 파일 크기를 합산한다. 폴더형 슬라이스의 `size` 필드에 쓴다.
- v1은 `os.path.getsize(폴더)`를 써서 폴더 항목 자체의 크기를 보고했다. 수 KB 수준의 값이라 실제 슬라이스 용량이 아니었다.

### 1-5. 슬라이스 목록 — `get_print_data()`

- 폴더형은 `"folder"` 모드인 확장자의 폴더만, 파일형은 `"file"` 모드인 확장자의 파일만 목록에 넣는다(`get_filetype_slice_data()` 사용). 장비에 맞지 않는 형식은 목록에서 빠진다.
- **동작 변경 (데이터 손실 방지)**
  - v1: preview, idx/gcode가 없는 폴더형 슬라이스를 발견하면 `shutil.rmtree()`로 **바로 삭제**했다.
  - v2: 삭제하지 않고 **목록에서만 제외**한다.

### 1-6. 슬라이스 수신 — `add_print_data()`

- 전송용으로 붙은 `.zip` 접미사를 뗀 이름의 확장자로 `get_slice_mode()`를 조회한다.
- `"file"` 모드면 받은 바이트를 압축 해제 없이 그대로 파일로 저장한다.
- 그 외(폴더형, 또는 매핑에 없는 확장자)는 v1과 같이 zip을 풀어 폴더로 만든다. 안쪽 폴더가 하나뿐이면 그 내용을 한 단계 위로 올린다.
- v1은 모든 데이터를 zip으로 간주해 항상 압축을 풀었다.

### 1-7. 슬라이스 삭제 — `delete_print_data()`

- 대상이 폴더면 `shutil.rmtree()`, 파일이면 `os.remove()`로 삭제한다.
- v1은 항상 `shutil.rmtree()`를 불렀다. 파일형 슬라이스를 삭제하면 예외가 나는 구조였다. 당시엔 파일형 슬라이스가 저장되지 않아 드러나지 않았을 뿐이다.

---

## 2. JSON 파일 안전 입출력 (`lib/json_file.py` 신규)

### 배경

`status_handler`·`file_handler`·`cam_handler` 스레드와 IoT Core 메시지 핸들러가 같은 JSON 파일을 동시에 읽고 쓴다. 대상은 `device-log.json`, 이력 폴더 `print-history.json`, 로그 파일, 상태 파일 등이다.

v1은 `open(..., 'w')`로 썼다. 이 방식은 파일을 먼저 0바이트로 비운 뒤 내용을 쓴다. 그래서 두 가지 문제가 있었다.
- 그 사이에 다른 스레드가 읽으면 빈 파일을 읽어 `Exception in status_handler: Expecting value: line 1 column 1 (char 0)`이 난다.
- 쓰는 중에 전원이 꺼지면 빈 파일이 그대로 남는다.

### 제공 함수

| 함수 | 역할 |
|---|---|
| `write_json(path, data)` | 같은 폴더의 임시 파일에 끝까지 쓰고 `fsync`한 뒤 `os.replace()`로 바꿔치기한다. 읽는 쪽은 항상 이전 내용 전체 아니면 새 내용 전체를 본다. 쓰다가 꺼져도 이전 내용이 남는다. |
| `read_json(path)` | Lock을 잡고 읽는다. |
| `update_json(path, fn)` | Lock 안에서 읽기 → `fn(data)`로 수정 → 쓰기. 두 스레드가 같은 파일을 읽고-고쳐-쓸 때 한쪽 변경이 덮여 사라지지 않는다. |
| `lock(path)` | 경로별 `RLock`. 어느 모듈에서 부르든 같은 파일이면 같은 Lock이다. |

**세부 동작**
- 기본 직렬화 옵션은 v1과 같다(`ensure_ascii=False`, `indent=4`).
- 바꿔치기 후에도 기존 파일 권한을 유지한다(임시 파일 기본값 0600 → 기존 권한, 새 파일은 0644).
- Windows에서는 다른 프로세스가 대상 파일을 열고 있으면 `os.replace()`가 `PermissionError`를 낸다. 이 경우 50ms 간격으로 최대 10회 재시도한다.
- 실패하면 임시 파일을 지운다.

### 적용 범위

v2의 상태·로그·이력 JSON 읽기/쓰기는 모두 이 모듈을 쓴다.

| 파일 | 적용 위치 |
|---|---|
| `lib/log_manager.py` | 로그 파일 생성(`create_log_file`), 로그 추가(`update_log_file`, Lock 안에서 읽기-추가-쓰기), `device-log.json` 목록 추가(`save_log_file`, `update_json`) |
| `lib/status_manager.py` | 상태 파일 읽기/쓰기(`get_json_content`/`set_json_content`), `device-request.json` 요청 추가(`add_device_request`, `update_json`) |
| `lib/file_manager.py` | 업로드 대기 목록 읽기/정리, 로그·출력 이력 파일 읽기, 출력 이력 상세 저장(`get_print_history`, `set_print_history`) |
| `AWSClientApp.py` | `control_print_history`의 출력 이력 파일 저장과 이력 폴더 `print-history.json` 목록 추가(`update_json`) |

### 한계

Lock은 이 앱 안의 스레드끼리만 순서를 맞춘다. 장비 프로그램처럼 다른 프로세스와 함께 쓰는 파일(`device-status.json`, `device-request.json` 등)의 동시 쓰기는 막지 못한다. 다만 이 앱의 쓰기가 원자적이라 상대 프로세스가 빈 파일을 읽는 일은 없다.

---

## 3. 업로드 대기 목록 유실 방지 (`lib/file_manager.py`, `AWSClientApp.py`)

### 배경

`device-log.json`(로그)과 이력 폴더 `print-history.json`(출력 이력)의 `updated-list`는 S3 업로드를 기다리는 파일 목록이다.
- `status_handler`가 목록에 항목을 추가한다.
- `file_handler`가 목록을 읽고 업로드한 뒤 목록을 정리한다.

v1은 업로드가 끝나면 목록을 **빈 목록으로 덮어썼다.** 그래서 업로드하는 동안 `status_handler`가 새로 추가한 항목은 업로드되지 않고 사라졌다.

### 변경

- `reset_device_log_updatelist(done=None)`, `reset_print_history_updatelist(done=None)`
  - `done`에 이번에 업로드한 항목을 넘기면 그 항목만 목록에서 뺀다.
  - `done`이 없으면 v1처럼 전부 비운다.
  - 공통 처리는 `_remove_from_updatelist()`가 `update_json`(Lock 안에서 읽기-수정-쓰기)으로 한다.
  - 파일이 없거나 깨져 있으면 빈 목록으로 새로 만든다.
- `file_handler`는 이번에 읽은 목록을 `done`으로 넘긴다.

### 검증

세 스레드가 동시에 로그 400건을 추가하고, 업로드하고, 읽는 시험을 v1 방식 코드와 v2 코드에 똑같이 돌렸다.

| | v1 방식 | v2 |
|---|---|---|
| `Expecting value` 오류 | 다수 발생 | 0건 |
| 목록 400건 중 업로드된 항목 | 2건 | 400건, 중복 없음 |
| 남은 임시 파일 | – | 없음 |

---

## 4. 스레드 루프 예외 처리 (`AWSClientApp.py`)

### 배경

v1의 `status_handler`·`file_handler`·`cam_handler`는 `try` 블록 안에만 `time.sleep()`이 있었다. 예외가 나면 쉬지 않고 바로 다음 반복으로 넘어간다. 예를 들어 파일이 깨져 같은 예외가 계속 나면, 루프가 쉬지 않고 돌아 CPU를 많이 쓰고 콘솔에 오류가 쏟아졌다. 출력도 예외 메시지 한 줄뿐이라 발생 위치를 알 수 없었다.

### 변경

- 예외가 나도 원래 주기만큼 쉰 뒤 다음 반복으로 넘어간다.
  - `status_handler`·`file_handler`: 1초
  - `cam_handler`: `delay_time`(촬영 주기)
- 기존 `Exception in <handler>: <메시지>` 줄은 유지하고, 그 아래에 `traceback.format_exc()`를 함께 출력한다.

---

## 운영 참고

- 이력 폴더(`dir.history`)의 `print-history.json`과 로그 폴더(`dir.log`)의 `device-log.json`은 앱이 처음에 만들어 주지 않는다. 설치할 때 `{"updated-list": []}` 내용으로 미리 만들어 둬야 한다. 없으면 업로드 목록을 읽지 못해 업로드를 건너뛴다.
