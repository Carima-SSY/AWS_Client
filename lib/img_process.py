import cv2
import numpy as np
from collections import Counter

def analyze_dlp_slice_image(image_path):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
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