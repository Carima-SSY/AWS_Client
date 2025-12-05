import os, io, json , base64, cv2, time
from PIL import Image


class CamManager:
    def __init__(self, camera_index=0, width=640, height=480, fps=30, webp_quality=50, cam_folder=""):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.webp_quality = webp_quality
        self.cam_folder = cam_folder
        
        self.capture = cv2.VideoCapture(self.camera_index)

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.fps)
        
    def exists_cam_folder(self, sub_folder):
        return os.path.exists(f"{self.cam_folder}/{sub_folder}")

    def create_sub_folder(self, sub_folder):
        try:
            os.makedirs(f"{self.cam_folder}/{sub_folder}")
            return True
        except Exception as e:
            print(f"Exception in create_sub_folder -> {sub_folder}: {e}")
            return False
    
    def save_image(self, sub_folder):
        try:
            if self.capture.isOpened():
                print(f"Camera with index {self.camera_index} could not be opened.")
                return None
            
            ret, frame = self.capture.read()
            if not ret:
                print("Failed to capture frame from camera.")
                return None
            _, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, self.webp_quality])

            byte_io = io.BytesIO()
            byte_io.write(buffer.tobytes())
            byte_io.seek(0)
            with open(f"{self.cam_folder}/{sub_folder}/cam-{int(time.time())}.webp", 'wb') as f:
                f.write(byte_io.read())
            
            img_bytes = io.BytesIO(buffer).getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')

            return img_base64
        except Exception as e:
            print(f"Camera capture error: {e}")
            
            return None
        
    def capture_image(self):
        try:
            if not self.capture.isOpened():
                print(f"Camera with index {self.camera_index} could not be opened.")
                return None
            
            ret, frame = self.capture.read()
            if not ret:
                print("Failed to capture frame from camera.")
                return None
            _, buffer = cv2.imencode('.webp', frame, [cv2.IMWRITE_WEBP_QUALITY, self.webp_quality])
            img_bytes = io.BytesIO(buffer).getvalue()
            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            #print(img_base64)
            return img_base64
        except Exception as e:
            print(f"Camera capture error: {e}")
            
            return None
        
    def release(self):
        if self.capture.isOpened():
            self.capture.release()