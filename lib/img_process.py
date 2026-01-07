import cv2, os, shutil, zipfile
import numpy as np
from collections import Counter

def analyze_dlp_slice_image(image_path):
    #print(f"analyze_dlp_slice_image: {image_path}")
    # img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    with open(image_path, 'rb') as f:
        bytes_data = f.read()
    np_array = np.frombuffer(bytes_data, np.uint8)
    img = cv2.imdecode(np_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"Error: No such file in directory / Path: {image_path}")
        return False

    _, binary_img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    
    total_white_pixels = int(np.sum(binary_img == 255))
    
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        binary_img, 
        connectivity=8,  # 8방향 연결성 (대각선 포함)
        ltype=cv2.CV_32S
    )
    
    blob_sizes = list()

    for i in range(1, num_labels): 
        area = stats[i, cv2.CC_STAT_AREA] 
        blob_sizes.append(int(area))
        
    blob_sizes.sort()
    
    return {"total": total_white_pixels, "blob": {"count": len(blob_sizes), "sizes": blob_sizes}}

def create_preview_zip(src_folder, output_file):
    if os.path.exists(os.path.join(src_folder, "preview_temp")): shutil.rmtree(os.path.join(src_folder, "preview_temp"))
    os.makedirs(os.path.join(src_folder, "preview_temp"))
    
    images = [img for img in os.listdir(src_folder) if img.endswith((".jpg", ".png", ".jpeg", ".webp"))]
    images.sort()
    
    files_to_zip = images[-30:]
    
    for filename in files_to_zip:
        src_path = os.path.join(src_folder, filename)
        dst_path = os.path.join(src_folder, "preview_temp", filename)
        shutil.copy2(src_path, dst_path) # 파일 복사 (메타데이터 포함)
        
    with zipfile.ZipFile(f"{output_file}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(os.path.join(src_folder, "preview_temp")):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, os.path.join(src_folder, "preview_temp")))
                
    shutil.rmtree(os.path.join(src_folder, "preview_temp"))
    
def create_timelapse(src_folder, output_file, fps):
    
    images = [img for img in os.listdir(src_folder) if img.endswith((".jpg", ".png", ".jpeg", ".webp"))]
    images.sort()
    
    if not images:
        print(f"Error: No images found in {src_folder}")
        return

    first_image_path = os.path.join(src_folder, images[0])
    frame = cv2.imread(first_image_path)
    height, width, layers = frame.shape

    fourcc = cv2.VideoWriter_fourcc(*'mp4v') # XVID, MJPG ...
    video = cv2.VideoWriter(output_file, fourcc, fps, (width, height))
    
    for image_name in images:
        image_path = os.path.join(src_folder, image_name)
        image = cv2.imread(image_path)
        video.write(image)

    video.release()
    cv2.destroyAllWindows()