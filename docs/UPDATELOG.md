# UPDATELOG

`v1`/`v2`는 같은 프로젝트(Carima 3D 프린터용 AWS Client — MQTT 기반 디바이스 통신 + 슬라이스 파일 관리 앱)의 버전이다. 이 문서는 **v2에서 새로 추가되거나 바뀐 코드와 기능**을 정리한다.

## v2 업데이트 요약

| # | 기능 | 내용 |
|---|---|---|
| 1 | 기종별 슬라이스 형식 지원 | 폴더형/파일형 슬라이스를 장비 타입별로 구분해 목록·수신·삭제를 모두 처리한다. |
| 2 | JSON 파일 안전 입출력 | 원자적 쓰기와 파일별 Lock으로, 스레드끼리 동시에 접근해도 빈 파일을 읽지 않게 했다(`Expecting value` 오류 해결). |
| 3 | 업로드 대기 목록 유실 방지 | 업로드가 끝난 항목만 목록에서 빼서, 업로드 중에 추가된 로그·출력 이력이 사라지지 않는다. |
| 4 | 스레드 루프 예외 처리 | 예외가 나도 주기대로 쉬고, traceback으로 발생 위치를 출력한다. |
| 5 | 레시피 추가·삭제 조건 수정 | 항상 참이던 장비 타입 조건을 고쳐, X1/DM400 계열에서 레시피 삭제가 실제로 동작한다. |
| 6 | 지원 기종 확대 | STATIC 기종 설정 기준으로 17개 기종을 XML/CFG 두 계열로 묶었다. DM4KH·DM400PRO 등도 슬라이스·레시피·설정이 올라간다. |
| 7 | 웹 목록 업로드 재시도·주기적 재전송 | 업로드에 성공했을 때만 "올렸다"고 기록하고, 실패하면 다시 올린다. 슬라이스·레시피 목록은 5분마다 다시 올려 웹과 어긋나도 저절로 맞춰진다. |
| 8 | 슬라이스 수신 시 임시 폴더 사용 | 웹에서 받은 슬라이스를 임시 이름으로 다 푼 뒤 한 번에 옮긴다. 만드는 도중의 슬라이스가 목록에 보이지 않고, 실패해도 찌꺼기가 남지 않는다. |
| 9 | 갱신 지연 줄이기 | 슬라이스 미리보기를 바뀐 슬라이스만 다시 만들고, 목록 갱신과 로그·이력 업로드를 다른 스레드로 나눴다. |
| 10 | 파일 명령 처리 분리 | 웹의 업로드·삭제 명령을 MQTT 수신 스레드 밖에서 순서대로 처리하고, 명령 처리 중 예외가 통신을 멈추지 않게 했다. |
| 11 | HTTP 요청 제한 시간 | 응답 없는 요청 때문에 스레드가 영영 멈추지 않게 모든 HTTP 요청에 제한 시간을 넣었다. |
| 12 | 파일 명령 처리 결과 전송 | 웹의 업로드·삭제 명령을 처리한 결과(성공/실패)를 웹으로 보낸다. 웹은 실패를 사용자에게 알린다. |

### 변경 파일

| 파일 | v1 → v2 | 관련 기능 |
|---|---|---|
| `AWSClientApp.py` | 552줄 → 657줄 | 2, 3, 4, 6, 7, 9, 10, 12 |
| `lib/file_manager.py` | 395줄 → 540줄 | 1, 2, 3, 5, 6, 8, 9 |
| `lib/aws.py` | 106줄 → 110줄 | 11 |
| `lib/json_file.py` | **신규** (85줄) | 2 |
| `lib/log_manager.py` | 41줄 → 37줄 | 2 |
| `lib/status_manager.py` | 114줄 → 109줄 | 2 |

그 외 파일(`lib/cam_manager.py`, `lib/status.py`, `lib/status_backup.py`, `lib/img_process.py`, `requirements.txt`, `client-config.json`, `test/` 전체)은 v1과 같다. 새 의존성은 없다. 모두 표준 라이브러리(`zipfile`, `io`, `tempfile`, `threading`, `traceback`, `queue`, `uuid`)로 구현했다.

---

## 1. 기종별 슬라이스 형식 지원 (`lib/file_manager.py`)

### 배경

슬라이서가 내보내는 슬라이스 형식은 기종마다 다르다.
- **XML 계열**(X1/X1PRO/DM400/DM400PRO): 슬라이스를 **폴더**로 내보낸다.
- **CFG 계열**(DM4K 계열/IML 계열/IMD/IMDC/ZENESIS/BISON2000): `.crmaslice`/`.cws`/`.cmz`를 **압축 파일 하나**로 내보낸다.

v1은 이 구분 없이 모든 슬라이스를 폴더로 취급했다. 파일형 슬라이스를 처리하는 자리(`get_print_data`의 `slices["files"]` 루프)는 `pass`만 있는 미완성 상태였다. 그래서 파일형 기종의 슬라이스는 목록에 나타나지 않았다.

### 1-1. 기종별 슬라이스 모드 매핑 — `SLICE_FORMAT_MODE_BY_DEVICE`, `get_slice_mode()`

장비 타입과 확장자로 `"folder"`(폴더형) 또는 `"file"`(파일형)을 정한다. 확장자는 대소문자를 구분하지 않는다. 매핑에 없는 조합은 `None`이다. 매핑은 기종 계열 목록(6장)에서 만든다.

```python
_FOLDER_SLICE_MODE = {".slice": "folder", ".crmaslice": "folder"}
_FILE_SLICE_MODE = {".slice": "folder", ".crmaslice": "file", ".cws": "file", ".cmz": "file"}
SLICE_FORMAT_MODE_BY_DEVICE = {
    **{t: _FOLDER_SLICE_MODE for t in XML_DEVICE_TYPES},
    **{t: _FILE_SLICE_MODE for t in CFG_DEVICE_TYPES},
}

def get_slice_mode(self, ext: str):
    return SLICE_FORMAT_MODE_BY_DEVICE.get(self.device_type, {}).get(ext.lower())
```

이 매핑이 v1의 `is_slicefolder()`/`is_slicefile()`를 대신한다. v1의 두 함수는 이름에 확장자 문자열이 들어 있는지만 검사했다. 두 함수는 v2에서 삭제했다. 두 함수가 쓰던 `SLICE_FORMAT` 상수는 남아 있지만 더 이상 쓰는 곳이 없다.

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
- `encode_previewimg`에 주석으로 남아 있던 예전 방식(임시 `output.webp` 파일에 저장 후 읽기) 코드는 지웠다.

### 1-4. 폴더 실제 용량 계산 — `get_folder_size(path)`

- 폴더 안의 모든 파일 크기를 합산한다. 폴더형 슬라이스의 `size` 필드에 쓴다.
- v1은 `os.path.getsize(폴더)`를 써서 폴더 항목 자체의 크기를 보고했다. 수 KB 수준의 값(Windows는 0)이라 실제 슬라이스 용량이 아니었다.

### 1-5. 슬라이스 목록 — `get_print_data()`

- 폴더형은 `"folder"` 모드인 확장자의 폴더만, 파일형은 `"file"` 모드인 확장자의 파일만 목록에 넣는다. 폴더형은 `get_foldertype_slice_data()`, 파일형은 `get_filetype_slice_data()`로 정보를 만든다. 장비에 맞지 않는 형식은 목록에서 빠진다.
- 같은 슬라이스의 정보는 바뀌기 전까지 다시 만들지 않는다(9장).
- **동작 변경 (데이터 손실 방지)**
  - v1: preview, idx/gcode가 없는 폴더형 슬라이스를 발견하면 `shutil.rmtree()`로 **바로 삭제**했다.
  - v2: 삭제하지 않고 **목록에서만 제외**한다.
- **동작 변경 (매핑에 없는 기종) — 주의**
  - v1: 장비 타입과 관계없이, 이름에 슬라이스 확장자가 들어 있는 폴더는 모두 목록에 넣었다.
  - v2: 기종 계열 목록(6장)에 없는 장비 타입은 `get_slice_mode()`가 항상 `None`이다. 그래서 **슬라이스 목록이 비게 된다.**
  - 시작할 때 이런 타입이면 `WARNING: 지원 목록에 없는 장비 타입`을 출력한다.

### 1-6. 슬라이스 수신 — `add_print_data()`

- 전송용으로 붙은 `.zip` 접미사를 뗀 이름의 확장자로 `get_slice_mode()`를 조회한다.
- `"file"` 모드면 받은 바이트를 압축 해제 없이 그대로 파일로 저장한다.
- 그 외(폴더형, 또는 매핑에 없는 확장자)는 v1과 같이 zip을 풀어 폴더로 만든다. 안쪽 폴더가 하나뿐이면 그 폴더를 슬라이스로 쓴다.
- v1은 모든 데이터를 zip으로 간주해 항상 압축을 풀었다.
- `.zip` 접미사는 대소문자 구분 없이 뗀다. v1은 `.zip`(소문자)만 뗐다.
- 파일·폴더는 임시 이름으로 다 만든 뒤 한 번에 옮긴다(8장).

### 1-7. 슬라이스 삭제 — `delete_print_data()`

- 대상이 폴더면 `shutil.rmtree()`, 파일이면 `os.remove()`로 삭제한다.
- v1은 항상 `shutil.rmtree()`를 불렀다. 파일형 슬라이스를 삭제하면 예외가 나는 구조였다. 당시엔 파일형 슬라이스가 저장되지 않아 드러나지 않았을 뿐이다.
- **동작 변경:** 대상이 없으면 v2는 아무것도 하지 않고 `True`를 돌려준다. v1은 `rmtree()` 예외가 나서 `False`를 돌려줬다.

---

## 2. JSON 파일 안전 입출력 (`lib/json_file.py` 신규)

### 배경

상태·업로드·카메라 스레드와 IoT Core 메시지 핸들러가 같은 JSON 파일을 동시에 읽고 쓴다. 대상은 `device-log.json`, 이력 폴더 `print-history.json`, 로그 파일, 상태 파일 등이다.

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
  - 예외: v1의 로그 파일 생성(`create_log_file`)만 `ensure_ascii`를 지정하지 않아 한글 등을 `\uXXXX`로 썼다. v2는 다른 파일과 같이 그대로 쓴다. 이후 로그 추가는 v1도 `ensure_ascii=False`였으므로 실제 영향은 없다.
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
- 업로드 스레드(v1 `file_handler`, v2 `upload_handler`)가 목록을 읽고 업로드한 뒤 목록을 정리한다.

v1은 업로드가 끝나면 목록을 **빈 목록으로 덮어썼다.** 그래서 업로드하는 동안 `status_handler`가 새로 추가한 항목은 업로드되지 않고 사라졌다.

### 변경

- `reset_device_log_updatelist(done=None)`, `reset_print_history_updatelist(done=None)`
  - `done`에 정리할 항목을 넘기면 그 항목만 목록에서 뺀다.
  - `done`이 없으면 v1처럼 전부 비운다.
  - 공통 처리는 `_remove_from_updatelist()`가 `update_json`(Lock 안에서 읽기-수정-쓰기)으로 한다.
  - 파일이 없거나 깨져 있으면 빈 목록으로 새로 만든다.
- `upload_handler`는 **업로드에 성공한 항목과 읽을 수 없는 항목만** `done`으로 넘긴다. 업로드에 실패한 항목은 목록에 남아 다시 올라간다(7장).

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
  - `status_handler`·`file_sync_handler`: 1초
  - `upload_handler`: 1초(업로드 실패 시 `RETRY_INTERVAL`, 7장)
  - `cam_handler`: `delay_time`(촬영 주기)
- 기존 `Exception in <handler>: <메시지>` 줄은 유지하고, 그 아래에 `traceback.format_exc()`를 함께 출력한다.

---

## 5. 레시피 추가·삭제 조건 수정 (`lib/file_manager.py`)

### 배경

`add_print_recipe`·`delete_print_recipe`는 레시피를 `.xml` 파일로 관리하는 기종에서만 동작하도록 장비 타입을 검사한다. 그런데 v1의 조건은 `device_type != "X1" or device_type != "DM400"`이었다. 이 조건은 어떤 값이든 항상 참이다. 그래서 **모든 장비에서 레시피 삭제가 실행되지 않고 바로 `False`를 돌려줬다.** 웹에서 레시피 삭제 명령을 보내도 장비의 레시피 파일은 그대로 남았다.

### 변경

- 두 함수의 조건을 `device_type not in XML_DEVICE_TYPES`로 고쳤다(6장).
- 이제 XML 계열(X1/X1PRO/DM400/DM400PRO)에서는 레시피가 실제로 삭제된다. 그 외 기종은 v1과 같이 `False`를 돌려주고 아무것도 하지 않는다.
- `add_print_recipe`는 지금 호출하는 곳이 없다. 레시피 수신은 `save_json_to_xml`이 처리한다. 같은 조건이라 함께 고쳤다.

### 참고

v1의 `request_file_deletion`은 삭제 결과와 관계없이 항상 `True`를 돌려줘, 삭제 실패가 드러나지 않았다. v2는 실제 삭제 결과를 돌려주고, 그 결과를 웹으로 보낸다(12장).

---

## 6. 지원 기종 확대 (`lib/file_manager.py`, `AWSClientApp.py`)

### 배경

v1은 기종 이름을 코드 곳곳에 직접 적었다(`== "X1" or == "DM400"`, `in ["DM4K", "IML", ...]`, `== "DM400"`). 여기에 없는 기종(DM4KH, DM4KDS, DM4KRS, DM4KBD, DM4KULTRA, IML16KULTRA, X1PRO, DM400PRO, BISON2000)은 다음과 같이 동작했다.
- 레시피·장비 설정 목록이 올라가지 않았다.
- v2 초기 버전에서는 슬라이스 목록까지 비었다(1-5).

### 변경

STATIC 기종 설정(`STATIC/config/*.json`의 `file` 항목)을 기준으로 기종을 두 계열로 묶고, 장비 타입 검사를 모두 이 목록으로 바꿨다.

| 상수 | 기종 | 슬라이스 | 레시피·설정 |
|---|---|---|---|
| `XML_DEVICE_TYPES` | X1, X1PRO, DM400, DM400PRO | 폴더형 | `.xml` 레시피, `SaveFile.xml` 설정 |
| `CFG_DEVICE_TYPES` | DM4K, DM4KH, DM4KDS, DM4KRS, DM4KBD, DM4KULTRA, IML, IML16K, IML16KULTRA, IMD, IMDC, ZENESIS, BISON2000 | 파일형 | `resin.cfg` 레시피 목록, 설정 없음 |
| `PRINT_QUEUE_DEVICE_TYPES` | DM400, DM400PRO | – | 출력 대기열 요청(add/change/delete-printing) 허용 |

- 적용 위치
  - `file_manager.py`: `SLICE_FORMAT_MODE_BY_DEVICE`, `is_settingfile`, `get_print_recipe`, `get_device_setting`, `add_print_recipe`, `delete_print_recipe`
  - `AWSClientApp.py`: `request_add/change/delete_printing`, `request_change_file`
- `request_change_file`에 있던 도달할 수 없는 `elif device_type == "DM400"` 분기를 지웠다.
- 시작할 때 장비 타입이 두 계열 어디에도 없으면 경고를 출력한다(`is_supported_device()`).
- 새 기종은 해당 계열 목록에 이름을 추가하면 된다.

---

## 7. 웹 목록 업로드 재시도·주기적 재전송 (`AWSClientApp.py`)

### 배경

v1은 슬라이스·레시피·장비 설정 목록을 "마지막으로 올린 목록"과 비교해 바뀌었을 때만 올렸다. 그런데 업로드하기 **전에** 이 값을 새 목록으로 바꿔 두고, 업로드 결과는 확인하지 않았다.
- 업로드 URL 발급이 실패하면 `None["data"]`에서 예외가 났다.
- S3 업로드가 실패해도 성공으로 취급했다.

그래서 네트워크가 잠깐만 끊겨도, 장비 목록이 다시 바뀔 때까지 웹은 예전 목록을 계속 보여 줬다. 로그·출력 이력도 업로드 실패와 관계없이 대기 목록에서 빠져 다시 올라가지 않았다.

### 변경

- `upload_json(apig_client, data_name, data, name=None)`: 업로드 URL 발급과 S3 업로드를 함께 처리하고, **둘 다 성공했을 때만 `True`**를 돌려준다. 예외도 안에서 잡아 `False`로 돌려준다.
- `file_sync_handler`(슬라이스·레시피·장비 설정)
  - 업로드에 성공했을 때만 "올린 목록"을 바꾼다.
  - 실패하면 `RETRY_INTERVAL`(10초) 뒤 다시 올린다. 네트워크가 끊긴 동안 매초 요청하지 않는다.
  - **슬라이스·레시피 목록은 바뀌지 않아도 `RESYNC_INTERVAL`(300초)마다 다시 올린다.** 어떤 이유로든(서버 알림 누락, 웹 쪽 갱신 실패 등) 웹과 어긋나도 5분 안에 다시 맞춰진다. 시작 직후에도 한 번 올린다.
  - 장비 설정은 웹에서 편집 중일 수 있어 주기적으로 다시 올리지 않고, 바뀔 때만 올린다.
- `upload_handler`(로그·출력 이력)
  - 업로드에 성공한 항목만 대기 목록에서 뺀다. 실패하면 그 회차를 멈추고 `RETRY_INTERVAL` 뒤 다시 올린다.
  - 파일을 읽을 수 없는 항목(지워졌거나 깨짐)은 다시 시도해도 소용없으므로 로그를 남기고 목록에서 뺀다. v1은 이 경우 예외로 루프가 멈춰 같은 실패를 계속 반복했다.
  - 타임랩스·미리보기 업로드(`captureimg_handler`)는 출력 이력 업로드에 성공한 뒤에만 시작한다.

---

## 8. 슬라이스 수신 시 임시 폴더 사용 (`lib/file_manager.py`)

### 배경

v1은 웹에서 받은 슬라이스를 최종 폴더에 바로 풀었다. 레이어 이미지가 많은 DM400 슬라이스는 푸는 데 몇 초가 걸린다. 그 사이 목록 확인(1초마다)이 덜 풀린 폴더를 만났다.
- v1은 미리보기·idx가 아직 없는 폴더를 지웠다. 그래서 푸는 도중 슬라이스가 지워지거나 일부만 남았다.
- v2 초기 버전은 지우지는 않았다. 하지만 미리보기·idx가 먼저 풀리면 나머지 파일이 다 풀리기 전에 목록에 나타났다. 압축 풀기가 중간에 실패하면 불완전한 폴더가 그대로 남았다.

### 변경

- `add_print_data()`는 데이터 폴더 안에 `.awsclient-partial-<uuid>` 이름으로 파일을 쓰거나 압축을 푼다.
  - 이 이름은 확장자가 없어 슬라이스 목록에 잡히지 않는다.
- 다 만든 뒤 `_replace_path()`로 최종 이름에 한 번에 옮긴다(`os.replace`).
  - 압축 안에 폴더가 하나뿐이면 그 폴더를 바로 옮긴다. v1의 "한 단계 위로 올리기"와 결과가 같다.
  - 같은 이름이 이미 있으면 기존 것을 임시 이름으로 비켜 두고 새 것을 넣은 뒤 지운다. 옮기기에 실패하면 기존 것을 되돌린다.
- 실패하면 임시본만 지워지고 기존 슬라이스는 그대로 남는다.
- 시작할 때 지난 실행에서 남은 `.awsclient-partial-*`를 지운다(`clean_partial_slices()`).
- **동작 변경:** 같은 이름의 슬라이스를 다시 받으면 v1은 기존 폴더 위에 덧풀어 파일이 섞였다. v2는 새 슬라이스로 **바꾼다.**

---

## 9. 갱신 지연 줄이기 (`lib/file_manager.py`, `AWSClientApp.py`)

### 배경

v1은 한 스레드(`file_handler`)가 1초마다 다음을 차례로 처리했다.
- 슬라이스 목록 → 레시피 → 장비 설정 → 로그 업로드 → 출력 이력 업로드

슬라이스 목록을 만들 때마다 모든 슬라이스의 미리보기 이미지를 다시 읽어 축소·인코딩하고, 폴더 용량도 다시 계산했다. 슬라이스가 많거나 로그·이력 업로드가 밀리면 한 바퀴가 1초를 크게 넘어, 웹 반영이 늦어졌다.

### 변경

- **슬라이스 정보 캐시** — `_get_cached_slice_data()`
  - 슬라이스 경로별로 수정 시각·크기(`os.stat`)와 결과(미리보기·용량, 유효하지 않으면 `None`)를 기억한다.
  - 수정 시각·크기가 그대로면 이전 결과를 쓴다. 미리보기 인코딩과 용량 계산은 슬라이스가 바뀌었을 때만 한다.
  - 수정 시각을 정확히 남기지 않는 파일시스템이나 하위 폴더 안의 변경에 대비해, `SLICE_CACHE_MAX_AGE`(60초)가 지나면 다시 만든다.
  - 사라진 슬라이스의 캐시는 바로 버린다.
- **스레드 분리**
  - `file_sync_handler`: 슬라이스·레시피·장비 설정 목록 갱신
  - `upload_handler`: 로그·출력 이력 업로드
  - 큰 로그·이력 업로드가 슬라이스·레시피 목록 갱신을 늦추지 않는다.

### 검증

같은 슬라이스로 목록을 6번 만들 때 미리보기 인코딩은 1번만 일어났다. 슬라이스 폴더에 파일을 추가하면 다시 인코딩했다.

---

## 10. 파일 명령 처리 분리 (`AWSClientApp.py`)

### 배경

v1은 웹의 `file-transfer`(슬라이스·레시피 보내기)와 `file-deletion`을 MQTT 수신 콜백(`iotcore_onmessage_handler`) 안에서 바로 처리했다.
- 큰 슬라이스를 내려받고 푸는 동안 MQTT 수신 스레드가 막혔다. 다른 명령이 밀렸고, 길어지면 접속 유지(keepalive)를 못 해 연결이 끊길 수 있었다. 끊긴 사이에 온 명령은 다시 오지 않는다(QoS 0).
- 다운로드가 실패하면(URL 5분 만료 등) `get_file_from_s3()`가 `None`을 돌려줘 `None.get()` 예외가 났다. paho-mqtt는 기본 설정에서 콜백 예외를 다시 던지므로 수신 스레드가 멈춰 이후 명령을 받지 못할 수 있었다.

### 변경

- `iotcore_onmessage_handler`는 실제 처리(`_handle_iotcore_message`)를 `try`로 감싼다. 어떤 명령에서 예외가 나도 로그(traceback 포함)만 남기고 수신 스레드는 계속 돈다.
- `file-transfer`·`file-deletion`은 큐(`self.file_commands`)에 넣기만 하고 바로 돌아온다.
- `file_command_worker` 스레드가 큐에서 꺼내 **받은 순서대로** 처리한다. 업로드 직후 보낸 삭제가 업로드보다 먼저 실행되지 않는다.
  - 다운로드에 실패하면 로그를 남기고 그 명령만 건너뛴다.
  - 명령 하나의 예외는 다음 명령 처리에 영향을 주지 않는다.
- `file-deletion`에서 이미 읽은 메시지를 한 번 더 파싱하던 중복 코드를 지웠다.

### 검증

다음 네 메시지를 차례로 넣었다.
- 업로드
- 만료된 URL의 업로드
- 삭제
- JSON이 아닌 메시지

결과는 다음과 같았다.
- 콜백은 즉시 돌아왔고 예외가 밖으로 나가지 않았다.
- 업로드 → 삭제 순서로 처리됐다.
- 만료된 업로드는 건너뛰었다.

---

## 11. HTTP 요청 제한 시간 (`lib/aws.py`)

### 배경

v1의 HTTP 요청(`requests.get`/`requests.put`)에는 제한 시간이 없었다. 서버나 네트워크가 응답 없이 멈추면 그 요청을 부른 스레드(목록 갱신·업로드·파일 명령)가 영영 멈춰, 이후 갱신이 전혀 일어나지 않았다.

### 변경

- 모든 요청에 `HTTP_TIMEOUT = (10, 60)`을 넣었다(연결 10초, 응답 대기 60초).
  - 대상: `get_presigned_url`, `get_file_from_s3`, `put_file_to_s3`, `put_data_to_s3`
- 응답 대기 60초는 데이터가 오가는 사이의 최대 공백이다. 큰 파일 업로드·다운로드도 데이터가 계속 오가면 끊기지 않는다.
- 제한 시간을 넘기면 예외가 나고, 각 호출부의 실패 처리(7장 재시도, 10장 건너뛰기)를 따른다.

---

## 12. 파일 명령 처리 결과 전송 (`AWSClientApp.py`)

### 배경

웹에서 보낸 `file-transfer`·`file-deletion`은 Lambda가 AWS IoT로 보내기만 하고 끝난다. 장비가 처리에 실패해도(다운로드 실패, 압축 해제 실패, 삭제 실패 등) 웹은 알 방법이 없었다. 그래서 웹에서는 업로드·삭제가 된 것처럼 보이는데 장비에는 반영되지 않는 일이 생겼다.

### 변경

- `file_command_worker`가 명령 하나를 처리할 때마다 `publish_file_command_result()`로 결과를 보낸다.

  ```json
  {
    "target": ["browser"],
    "action": "file-command-result",
    "device": {"type": "DM400", "number": 1},
    "data": {
      "request": "file-transfer",
      "type": "data",
      "name": "part.slice.zip",
      "success": false,
      "error": "download-failed",
      "timestamp": 1761700000000
    }
  }
  ```

  - 장비 알람(`device-alarm`)과 같은 경로다. `Carima-Hub_IoTCore_Handler`가 장비 권한 사용자의 브라우저에 `name: "file-command-result"`로 그대로 전달하므로 **Lambda 수정은 필요 없다.**
  - `target`이 `["browser"]`뿐이라 DynamoDB에는 저장하지 않는다.
- 결과에 싣는 파일 종류·이름
  - 업로드: 내려받은 내용의 `type`·`name`을 쓴다.
  - 내려받기에 실패해 내용을 모르면, URL 경로(`FILES/{type}/{number}/{data|recipe}/{파일명}.json`)에서 꺼낸다(`parse_transfer_url()`).
- `success` 판단
  - 업로드: 저장까지 예외 없이 끝나면 성공이다. 내려받기 실패(`error: "download-failed"`)나 처리 중 예외(`error`에 예외 메시지)는 실패다.
  - 삭제: `request_file_deletion`이 이제 실제 삭제 결과를 돌려준다. v1은 항상 `True`였다.
    - 슬라이스: `delete_print_data()` 결과
    - 레시피: `delete_print_recipe()` 결과. CFG 계열은 레시피 삭제를 지원하지 않으므로 항상 실패다.
- 결과 전송이 실패해도 다음 명령 처리에는 영향을 주지 않는다.

### 웹 쪽 처리 (WebFront v2)

- 슬라이스·레시피 화면이 실패 결과를 받으면 "장비가 저장하지 못함 / 삭제하지 못함" 알림을 띄운다.
- 실패한 업로드는 업로드 중 표시에서도 바로 뺀다.
- 결과를 보내지 않는 v1 장비에서도 웹은 그대로 동작한다. 업로드 중 표시는 최대 10분 뒤 정리된다.

### 검증

다음 6개 명령을 차례로 넣었다.
- 업로드 성공
- 만료된 URL의 업로드
- 압축이 깨진 업로드
- 있는 슬라이스 삭제
- 없는 슬라이스 삭제
- CFG 레시피 삭제

결과가 같은 순서로 6건 발행됐고, `success`와 `error`가 각각 맞게 실렸다.

---

## 운영 참고

- **v2로 올리기 전에 장비 타입을 확인한다.** `client-config.json`의 `device.type`이 6장의 17개 기종 중 하나여야 한다. 아니면 슬라이스·레시피 목록이 올라가지 않는다. 시작할 때 경고가 출력되며, 계열 목록에 타입을 추가한 뒤 올린다.
- 이력 폴더(`dir.history`)의 `print-history.json`과 로그 폴더(`dir.log`)의 `device-log.json`은 앱이 처음에 만들어 주지 않는다. 설치할 때 `{"updated-list": []}` 내용으로 미리 만들어 둬야 한다. 없으면 업로드 목록을 읽지 못해 업로드를 건너뛴다.
- 슬라이스·레시피 목록을 5분마다 다시 올리므로, 장비마다 5분에 한 번씩 S3 업로드와 웹 알림이 추가로 생긴다.
- 데이터 폴더에 `.awsclient-partial-`로 시작하는 항목이 보이면 슬라이스를 받는 중이다. 앱을 다시 시작하면 남은 것은 지워진다.
