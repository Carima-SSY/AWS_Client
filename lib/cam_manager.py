import os, io, base64, cv2, time
import numpy as np

# 라즈베리파이 전용 라이브러리 체크
try:
    from picamera2 import Picamera2
    IS_RPI_LIBCAMERA = True
except (ImportError, RuntimeError):
    IS_RPI_LIBCAMERA = False

class CamManager:
    def __init__(self, camera_index=0, width=640, height=480, fps=30, webp_quality=50, cam_folder=""):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.webp_quality = webp_quality
        self.cam_folder = cam_folder
        self.mode = "OPENCV"  
        
        if IS_RPI_LIBCAMERA:
            try:
                self.picam2 = Picamera2()
                config = self.picam2.create_still_configuration(main={"size": (self.width, self.height)})
                self.picam2.configure(config)
                self.picam2.start()
                self.mode = "PICAMERA2"
                print("Mode: Raspberry Pi CSI (Picamera2)")
            except Exception as e:
                print(f"Picamera2 fail, switching to OpenCV: {e}")
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
        elif hasattr(self, 'capture') and self.capture.isOpened():
            self.capture.release()