import os, io, json , base64, cv2, time
from PIL import Image


class CamManager:
    def __init__(self, camera_index=0, width=640, height=480, fps=30, webp_quality=50):
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.fps = fps
        self.webp_quality = webp_quality    
        
        self.capture = cv2.VideoCapture(self.camera_index)

        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.capture.set(cv2.CAP_PROP_FPS, self.fps)

    def capture_image(self):
        try:
            if not self.capture.isOpened():
                print(f"Error: Camera with index {self.camera_index} could not be opened.")
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