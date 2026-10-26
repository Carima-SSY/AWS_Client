# AWS_Client

Carima 3D 프린터(라즈베리파이 기반 디바이스)와 AWS를 연결하는 클라이언트. AWS IoT Core(MQTT)로 장비 상태/카메라 프레임을 발행하고 원격 명령을 수신하며, API Gateway를 통해 슬라이스 파일/레시피/로그를 주고받는다(`AWSClientApp.py`의 `AWSClient` 클래스가 진입점).

## 폴더 구조

```
AWS_Client/
├── README.md
├── docs/
│   ├── INSTALL.md      # 설치 및 빌드(PyInstaller) 절차
│   ├── UPDATELOG.md     # v1 → v2 변경 내역
│   └── TROUBLE.md       # cam_manager.py save_image/capture_image 오류 가능 지점 조사
└── src/
    ├── v1/              # 기존 운영 버전
    └── v2/              # 파일형 슬라이스(.cws/.cmz 등) 지원이 추가된 버전
```

`v1`/`v2`는 파일 트리가 완전히 동일하고, 실질적인 차이는 `lib/file_manager.py` 한 파일에 집중돼 있다. 자세한 변경 내역은 [docs/UPDATELOG.md](docs/UPDATELOG.md) 참고.

## 버전 선택 기준

- **X1 / DM400** — 슬라이서가 슬라이스를 폴더로 내보내는 기종. `v1`/`v2` 어느 쪽을 써도 동작은 동일.
- **DM4K / IML / IML16K / IMDC / IMD / ZENESIS** — 슬라이서가 `.crmaslice`/`.cws`/`.cmz`를 압축 파일 하나로 내보내는 기종. 이 경우 **`v2`를 사용해야 한다** — `v1`은 해당 처리 경로가 미완성이었다.

## 주요 구성 요소 (`src/v1`, `src/v2` 공통)

- `AWSClientApp.py` — `AWSClient` 클래스. AWS IoT Core(상태/카메라 MQTT 발행, 원격 명령 수신)와 API Gateway(파일 송수신) 연동을 묶는 진입점.
- `lib/aws.py` — AWS IoT Core / API Gateway 통신.
- `lib/file_manager.py` — 슬라이스/레시피 파일 관리(버전 간 차이 지점).
- `lib/status_manager.py`, `lib/status.py` — 장비 상태 수집.
- `lib/cam_manager.py` — 카메라 프레임 캡처(Picamera2 → Picamera(legacy) → OpenCV 순으로 자동 폴백).
- `lib/log_manager.py` — 로그 관리.
- `lib/img_process.py` — 이미지 처리(슬라이스 미리보기 인코딩 등).
- `client-config.json` — 디바이스/AWS 연결 설정.
- `requirements.txt` — Python 의존성(Raspberry Pi 카메라 패키지 포함).
- `test/` — 단위 테스트.

## 설치 및 빌드

[docs/INSTALL.md](docs/INSTALL.md) 참고 — GitHub에서 내려받은 뒤 `src/v1/` 또는 `src/v2/`로 이동해 `pip install -r requirements.txt`, 실행 파일이 필요하면 `pyinstaller --onefile AWSClientApp.py`로 빌드한다(Python 3.12.8 기준).

## 알려진 이슈

[docs/TROUBLE.md](docs/TROUBLE.md) 참고 — `lib/cam_manager.py`의 `save_image()`/`capture_image()` 실행 중 발생할 수 있는 예외(카메라 하드웨어 장애, 빈 프레임, 디스크 I/O 오류)와 32비트 라즈베리파이 OS에서의 `opencv-python` 설치 제약을 정리.
