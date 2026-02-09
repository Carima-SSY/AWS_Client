import os, io, base64, cv2, time
import numpy as np

# 1. 라이브러리 체크 (우선순위: Picamera2 -> Picamera -> OpenCV)
try:
    from picamera2 import Picamera2
    IS_RPI_LIBCAMERA = True
    IS_RPI_LEGACY = False
except (ImportError, RuntimeError):
    IS_RPI_LIBCAMERA = False
    try:
        import picamera
        IS_RPI_LEGACY = True
    except (ImportError, RuntimeError):
        IS_RPI_LEGACY = False

class CamManager:
    def __init__(self, camera_index=0, width=640, height=480, fps=30, webp_quality=50, cam_folder=""):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.webp_quality = webp_quality
        self.cam_folder = cam_folder
        self.mode = "OPENCV"  
        
        # 2. 모드 결정 및 초기화
        if IS_RPI_LIBCAMERA:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_still_configuration(main={"size": (self.width, self.height)})
                self.picam2.configure(config)
                self.picam2.start()
                self.mode = "PICAMERA2"
                print("Mode: Raspberry Pi CSI (Picamera2)")
            except Exception as e:
                print(f"Picamera2 fail: {e}")
                self._init_opencv()

        elif IS_RPI_LEGACY:
            try:
                import picamera
                self.legacy_cam = picamera.PiCamera()
                self.legacy_cam.resolution = (self.width, self.height)
                self.legacy_cam.framerate = self.fps
                # 메모리 스트림을 위한 버퍼 준비
                self.stream = io.BytesIO()
                self.mode = "PICAMERA_LEGACY"
                print("Mode: Raspberry Pi CSI (Legacy Picamera)")
            except Exception as e:
                print(f"Legacy Picamera fail: {e}")
                self._init_opencv()
        else:
            self._init_opencv()

    def _init_opencv(self):
        self.capture = cv2.VideoCapture(self.camera_index)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.fps)
        if self.capture.isOpened():
            self.mode = "OPENCV"
            print(f"Mode: Standard OpenCV (Index: {self.camera_index})")
        else:
            print("Error: No camera detected.")

    def _get_frame(self):
        if self.mode == "PICAMERA2":
            frame = self.picam2.capture_array()
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        elif self.mode == "PICAMERA_LEGACY":
            # Legacy Picamera는 배열로 직접 받기보다 스트림을 통해 numpy로 변환하는 게 안정적입니다.
            self.stream.seek(0)
            self.legacy_cam.capture(self.stream, format='jpeg', use_video_port=True)
            data = np.frombuffer(self.stream.getvalue(), dtype=np.uint8)
            self.stream.truncate(0)
            return cv2.imdecode(data, cv2.IMREAD_COLOR)

        else:
            ret, frame = self.capture.read()
            return frame if ret else None

    def save_image(self, sub_folder):
        frame = self._get_frame()
        if frame is None: return None
        
        _, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, self.webp_quality])
        
        save_path = os.path.join(self.cam_folder, sub_folder)
        os.makedirs(save_path, exist_ok=True)
        file_path = os.path.join(save_path, f"cam-{int(time.time())}.webp")
        
        with open(file_path, 'wb') as f:
            f.write(buffer)
        
        return base64.b64encode(buffer).decode('utf-8')

    def capture_image(self):
        frame = self._get_frame()
        if frame is None: return None
        
        _, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, self.webp_quality])
        return base64.b64encode(buffer).decode('utf-8')

    def release(self):
        if self.mode == "PICAMERA2":
            self.picam2.stop()
        elif self.mode == "PICAMERA_LEGACY":
            self.legacy_cam.close()
        elif hasattr(self, 'capture') and self.capture.isOpened():
            self.capture.release()