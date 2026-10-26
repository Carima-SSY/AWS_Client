# TROUBLE

`lib/cam_manager.py`의 `save_image()`/`capture_image()` 실행 중 발생할 수 있는 오류를 조사한 기록이다. 이 파일은 `v1`/`v2` 양쪽에서 완전히 동일하므로(바이트 단위 일치) 아래 내용은 두 버전 모두에 적용된다. 대부분의 항목은 실제로 재현/검증한 결과이며, 라즈베리파이 실기기·picamera2 라이브러리가 없어 직접 테스트하지 못하고 Picamera2 공식 문서상 동작에 근거한 항목은 본문에 명시해뒀다.

## A. `_get_frame()`에서 발생하는 예외가 어디서도 잡히지 않음

`save_image()`/`capture_image()`는 `_get_frame()` 호출을 try/except로 감싸지 않는다.

- **PICAMERA2 모드** (`_get_frame`의 `self.picam2.capture_array()`): 생성자의 try/except는 **최초 시작 시점만** 보호한다. 시작은 성공했더라도, 이후 리본 케이블 접촉 불량·드라이버 타임아웃 등으로 프레임 캡처 도중 `RuntimeError`가 발생하면 잡히지 않는다.
- **PICAMERA_LEGACY 모드** (`self.legacy_cam.capture(...)`): 마찬가지로 하드웨어 장애 시 `picamera.exc.PiCameraError` 계열 예외를 던질 수 있다.
- **OPENCV 모드** (`self.capture.read()`): 라즈베리파이의 USB 웹캠이든 윈도우의 내장/USB 카메라든 해당. 대부분의 백엔드는 실패 시 예외 없이 `(False, None)`을 반환해 비교적 안전하지만, 100% 보장되는 동작은 아니다.

## B. `cv2.imencode()`가 "비어있는 프레임"에서 예외를 던지는 것을 재현 확인

```python
>>> cv2.imencode('.webp', np.zeros((0, 0, 3), dtype=np.uint8), [cv2.IMWRITE_WEBP_QUALITY, 50])
cv2.error: OpenCV(...) ... error: (-215:Assertion failed) !_img.empty() in function 'imencodeWithMetadata'
```

`save_image()`/`capture_image()`의 유일한 가드는 `if frame is None: return None`뿐이다. 카메라가 일시적으로 글리치를 일으켜 `None`이 아닌 **크기 0인 빈 배열**을 반환하면(위 세 모드 중 어디서든 이론적으로 가능) 이 가드를 통과해 버리고, 바로 다음 줄의 `cv2.imencode()`에서 예외가 발생한다.

추가로 `_, buffer = cv2.imencode(...)`는 **첫 번째 반환값(인코딩 성공 여부)을 무시**한다. 실제 테스트에서는 비정상 입력 대부분이 예외를 던지는 쪽이었지만, 환경에 따라 `False`만 반환하고 예외는 나지 않는 경우까지 완전히 배제할 수는 없다 — 그 경우 빈 버퍼를 그대로 파일에 쓰고 base64 인코딩까지 조용히 진행해버린다.

## C. `save_image()`의 파일 I/O 예외 (`capture_image()`는 디스크에 쓰지 않으므로 해당 없음)

`os.makedirs(...)`/`open(file_path, 'wb')`는 다음 상황에서 `OSError`/`PermissionError`를 던질 수 있고 어디서도 잡히지 않는다.

- **라즈베리파이**: SD카드 용량 초과, 비정상 종료 후 파일시스템이 read-only로 마운트된 경우(흔한 장애 패턴).
- **윈도우**: 권한 부족, 디스크 공간 부족, 경로를 다른 프로세스가 점유 중인 경우.

## D. 호출부(`AWSClientApp.py`)에서 확인한 실질적 영향

`cam_handler()`의 `while True` 루프는 본문 전체를 try/except로 감싸고 있어 위 A/B/C가 터져도 앱 전체가 죽지는 않는다.

```python
def cam_handler(cam_client, client_status, client_cam):
    delay_time = CAPTURE_INTERVAL
    while True:
        try:
            ...
            encoded_image = client_cam.save_image(...)   # 또는 capture_image()
            ...
            time.sleep(delay_time)
        except Exception as e:
            print(f"Exception in cam_handler: {str(e)}")
            pass   # <- 여기엔 time.sleep()이 없음
```

**except 분기에는 `time.sleep()`이 없다** — 성공 경로에만 있다. 카메라가 지속적으로 고장 난 상태라면 지연 없이 무한 재시도하는 busy-loop가 되어 CPU 코어 하나를 계속 점유하고 예외 로그를 끊임없이 찍게 된다. `cam_manager.py` 자체의 문제는 아니지만, A/B/C가 실제로 발생했을 때 이어지는 결과이므로 같이 기록한다.

## E. 플랫폼 설치 이슈 — 32비트 라즈베리파이 OS (armv7l)

```
$ pip download opencv-python==4.12.0.88 --no-deps --only-binary=:all: \
    --python-version 3.12 --platform manylinux2014_armv7l
ERROR: Could not find a version that satisfies the requirement opencv-python==4.12.0.88
```

`opencv-python==4.12.0.88`은 **aarch64(64비트 Pi OS)용 prebuilt wheel은 있지만 armv7l(32비트 Pi OS)용은 없다.** 32비트 환경에서는 `cam_manager.py` 최상단의 `import cv2` 자체가 실패할 수 있어, `save_image()`/`capture_image()`에 도달하기 전에 모듈 임포트 단계에서 막힌다.

## F. `AWSClientApp.py`의 `CamManager` 생성자 호출(`width=1280, height=720, fps=30`)과 관련된 문제

```python
self.client_cam = cam.CamManager(camera_index=0, width=1280, height=720, fps=30, webp_quality=50, cam_folder=cam_folder)
```

해상도(1280×720) 자체가 라즈베리파이 카메라 모듈 호환성 문제를 일으킬 가능성은 낮다 — 대부분의 CSI 카메라 모듈이 지원하는 표준적인 크기다. 다만 이 값들이 실제로 어떻게(또는 전혀 안) 쓰이는지 확인한 결과:

### F-1. (코드로 확인됨) `fps=30`이 Picamera2 경로에서 완전히 무시됨

```python
if IS_RPI_LIBCAMERA:
    self.picam2 = Picamera2()
    config = self.picam2.create_still_configuration(main={"size": (self.width, self.height)})
```

`self.fps`가 이 분기 어디에도 쓰이지 않는다. 현재 라즈베리파이 OS(Bookworm 이후)는 기본적으로 libcamera 스택(Picamera2)을 쓰므로, 실제로는 `fps=30`을 줘도 아무 효과가 없고 Picamera2가 알아서 정한 프레임레이트로 동작한다. `fps`는 **레거시 PiCamera**(`self.legacy_cam.framerate = self.fps`)와 **OpenCV**(`cv2.CAP_PROP_FPS`) 경로에서만 실제로 적용된다.

### F-2. (Picamera2 공식 문서상 동작 — 이 환경에 실기기가 없어 직접 테스트는 못 함) `create_still_configuration`은 "1초 간격 연속 캡처"용으로 설계되지 않음

`cam_handler()`는 프린팅 중 `SAVE_INTERVAL = 1`초마다 `save_image()`를 호출한다. 그런데 `create_still_configuration()`은 Picamera2 문서상 **단발성 고화질 촬영**을 위한 모드로, `create_video_configuration()`/`create_preview_configuration()`보다 캡처당 처리 시간이 길도록 설계돼 있고, 기본적으로 `main` 스트림(1280×720)과 별개로 **센서 전체 해상도 raw 스트림**을 함께 캡처하는 것이 디폴트다(명시적으로 `raw=...`를 꺼서 비활성화하지 않는 한). 즉:
- 1초 간격으로 요청해도 실제 캡처가 그보다 느려서 지연이 누적될 수 있다.
- 카메라 모듈 해상도가 높을수록(HQ 카메라 등) raw 버퍼 때문에 메모리/CPU 부담이 "1280×720 하나만 찍는다"는 기대보다 훨씬 커질 수 있다 — Pi Zero/Zero 2 W처럼 RAM이 적은 모델에서 특히 체감될 수 있다.

확실히 하려면 실기기에서 `capture_array()` 한 번 호출에 걸리는 시간을 로그로 찍어 `SAVE_INTERVAL`(1초)과 비교해보는 것을 권한다.

### F-3. (코드로 확인됨) 어느 경로든 실제로 캡처된 프레임 크기를 검증/보정하지 않음

- OpenCV 경로의 `self.capture.set(cv2.CAP_PROP_FRAME_WIDTH/HEIGHT/FPS, ...)`는 반환값(성공 여부)을 확인하지 않는다 — USB 웹캠이 1280×720@30을 지원하지 않으면 드라이버가 요청을 조용히 무시하고 다른 해상도로 찍힐 수 있는데, 코드는 이를 전혀 감지하지 못한다.
- 어떤 경로든 `_get_frame()`이 돌려준 배열이 실제로 1280×720인지 확인하는 코드가 없다. 당장 에러를 내지는 않지만, 설정한 해상도와 실제 저장되는 이미지 해상도가 다를 수 있다는 뜻이다.

### F-4. 레거시 PiCamera 경로의 플랫폼 호환성

`width=1280, height=720, fps=30`(720p30) 자체는 레거시 `picamera` 패키지가 지원하는 표준적인 조합이라 설정값 자체는 문제가 안 된다. 다만 `picamera`(레거시) 패키지는 라즈베리파이 OS Bullseye 이전 카메라 스택(legacy camera stack) 기준이라, 현재 기본값인 Bookworm 이후 OS에서는 애초에 `import picamera` 자체가 실패하거나 정상 동작하지 않을 수 있다 — 설정값 문제가 아니라 OS 버전 호환성 문제다.

## 확인됐지만 문제 없는 것으로 판명된 항목 (오탐 배제)

- **Picamera2의 4채널(XBGR8888) 프레임 → `cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)` 깨짐 의심**: 직접 테스트한 결과 OpenCV는 4채널 입력도 정상 처리한다(3채널로 변환). 문제 없음.
  ```python
  >>> cv2.cvtColor(np.zeros((480, 640, 4), dtype=np.uint8), cv2.COLOR_RGB2BGR).shape
  (480, 640, 3)
  ```
- **`self.stream`(PICAMERA_LEGACY 모드) 동시 접근으로 인한 경쟁 조건 의심**: `AWSClientApp.py`를 확인한 결과 `save_image()`/`capture_image()`는 `cam_handler()` 스레드 하나에서만 순차 호출되고(`captureimg_handler()`는 `client_cam`을 건드리지 않음), 현재 사용 범위 내에서는 실제로 발생하지 않는다.

## 권장 조치 (참고용 — 아직 반영 전)

- `_get_frame()` 호출부를 try/except로 감싸서 캡처 실패를 `None` 반환으로 정규화.
- `if frame is None` 가드를 `if frame is None or frame.size == 0`로 보강.
- `cv2.imencode()`의 성공 여부(`ok`)를 확인해서 실패 시 `None`을 반환.
- `cam_handler()`의 except 분기에도 지연(`time.sleep`)을 추가해 busy-loop 방지.
- 32비트 라즈베리파이 OS를 지원 대상에 포함한다면, `opencv-python` 대신 시스템 패키지(`sudo apt install python3-opencv`)를 쓰거나 64비트 Pi OS로 전환을 권장하는 안내가 필요.
- Picamera2 경로를 `create_video_configuration()`(또는 `create_preview_configuration()`)으로 바꾸거나, `create_still_configuration(main={...}, raw=None)`처럼 raw 스트림을 꺼서 1초 주기 반복 캡처에 맞는 설정으로 전환.
- Picamera2 경로에서도 `self.fps`를 실제로 반영할 방법을 검토(예: `controls={"FrameRate": self.fps}`로 configure).
- OpenCV 경로의 `.set()` 호출 결과를 확인하거나, 캡처된 프레임의 실제 크기를 `self.width`/`self.height`와 대조해 불일치를 로그로 남기기.
