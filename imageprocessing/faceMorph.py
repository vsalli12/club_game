import face_alignment
import cv2
import numpy as np
from scipy.spatial import Delaunay
from scipy import ndimage

import os, json

import os
import json
import hashlib
import numpy as np

def rgb_hash(rgb: np.ndarray) -> str:
    """Compute a SHA-256 hash of the RGB image array."""
    return hashlib.sha256(rgb.tobytes()).hexdigest()

def load_landmarks_cache(app, cache_path="landmarks_cache.json"):
    with app.cacheLock:
        if os.path.isfile(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

def save_landmarks_cache(app, data, cache_path="landmarks_cache.json"):
    with app.cacheLock:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

def get_or_load_landmarks(app, rgb, cache_path="landmarks_cache.json"):
    key = rgb_hash(rgb)
    initial_cache = load_landmarks_cache(app, cache_path)

    if key in initial_cache:
        return np.array(initial_cache[key]) if initial_cache[key] is not None else np.array(None)

    try:
        landmarks = getFaceLandMarks(rgb)
        new_data = landmarks.tolist()
    except:
        landmarks = np.array(None)
        new_data = None

    latest_cache = load_landmarks_cache(app, cache_path)
    latest_cache[key] = new_data
    save_landmarks_cache(app, latest_cache, cache_path)

    return landmarks



def create_triangular_mesh(landmarks, img_shape):
    """Create a triangular mesh from facial landmarks"""
    h, w = img_shape[:2]
    
    # Add boundary points to ensure the entire face is covered
    boundary_points = [
        [0, 0], [w//2, 0], [w-1, 0],
        [0, h//2], [w-1, h//2],
        [0, h-1], [w//2, h-1], [w-1, h-1]
    ]
    
    all_points = np.vstack([landmarks, boundary_points])
    tri = Delaunay(all_points)
    return tri.simplices, all_points

def apply_triangular_warp(src_img, src_landmarks, dst_landmarks):
    """Apply triangular warping between source and destination landmarks"""
    triangles, src_points = create_triangular_mesh(src_landmarks, src_img.shape)
    
    # Create destination points with same boundary
    h, w = src_img.shape[:2]
    boundary_points = [
        [0, 0], [w//2, 0], [w-1, 0],
        [0, h//2], [w-1, h//2],
        [0, h-1], [w//2, h-1], [w-1, h-1]
    ]
    dst_points = np.vstack([dst_landmarks, boundary_points])
    
    result = np.zeros_like(src_img)
    
    for triangle in triangles:
        src_tri = src_points[triangle].astype(np.float32)
        dst_tri = dst_points[triangle].astype(np.float32)
        
        # Get bounding rectangles
        src_rect = cv2.boundingRect(src_tri)
        dst_rect = cv2.boundingRect(dst_tri)
        
        # Offset triangles to rect
        src_tri_offset = src_tri - [src_rect[0], src_rect[1]]
        dst_tri_offset = dst_tri - [dst_rect[0], dst_rect[1]]
        
        # Check if triangles are valid (not degenerate) using cross product
        def triangle_area(tri):
            p1, p2, p3 = tri
            return abs((p1[0]*(p2[1]-p3[1]) + p2[0]*(p3[1]-p1[1]) + p3[0]*(p1[1]-p2[1])) / 2.0)
        
        if triangle_area(src_tri_offset) < 1 or triangle_area(dst_tri_offset) < 1:
            continue
            
        # Ensure we have exactly 3 points and correct data type
        if src_tri_offset.shape[0] != 3 or dst_tri_offset.shape[0] != 3:
            continue
            
        src_tri_offset = np.array(src_tri_offset, dtype=np.float32)
        dst_tri_offset = np.array(dst_tri_offset, dtype=np.float32)
        
        # Get affine transform
        try:
            M = cv2.getAffineTransform(src_tri_offset, dst_tri_offset)
        except cv2.error:
            continue  # Skip degenerate triangles
        
        # Apply transformation
        # Apply transformation
        src_crop = src_img[src_rect[1]:src_rect[1]+src_rect[3], 
                          src_rect[0]:src_rect[0]+src_rect[2]]
        
        if src_crop.size > 0 and dst_rect[2] > 0 and dst_rect[3] > 0:
            try:
                warped = cv2.warpAffine(src_crop, M, (dst_rect[2], dst_rect[3]))
            except cv2.error:
                continue  # Skip if warp fails
            
            # Create mask for triangle
            mask = np.zeros((dst_rect[3], dst_rect[2]), dtype=np.uint8)
            cv2.fillConvexPoly(mask, np.int32(dst_tri_offset), 255)
            
            # Apply mask and copy to result
            mask_3ch = cv2.merge([mask, mask, mask])
            warped_masked = cv2.bitwise_and(warped, mask_3ch)
            
            dst_y1, dst_y2 = dst_rect[1], dst_rect[1] + dst_rect[3]
            dst_x1, dst_x2 = dst_rect[0], dst_rect[0] + dst_rect[2]
            
            # Ensure we don't go out of bounds
            dst_y1 = max(0, dst_y1)
            dst_x1 = max(0, dst_x1)
            dst_y2 = min(result.shape[0], dst_y2)
            dst_x2 = min(result.shape[1], dst_x2)
            
            if dst_y2 > dst_y1 and dst_x2 > dst_x1:
                mask_region = mask[:dst_y2-dst_y1, :dst_x2-dst_x1]
                warped_region = warped_masked[:dst_y2-dst_y1, :dst_x2-dst_x1]
                
                # Blend with existing pixels
                for c in range(3):
                    result[dst_y1:dst_y2, dst_x1:dst_x2, c] = np.where(
                        mask_region > 0,
                        warped_region[:, :, c],
                        result[dst_y1:dst_y2, dst_x1:dst_x2, c]
                    )
    
    return result

def enlarge_eyes_advanced(landmarks, scale_factor=1.2, eye_vert=1.0):
    """Create enlarged eye effect by moving eye contour landmarks outward"""
    landmarks_mod = landmarks.copy()
    
    # Left eye (landmarks 36-41)
    left_eye_points = landmarks[36:42]
    left_eye_center = left_eye_points.mean(axis=0)
    
    # Right eye (landmarks 42-47)  
    right_eye_points = landmarks[42:48]
    right_eye_center = right_eye_points.mean(axis=0)
    
    # Scale eye contours outward from center (more conservative)
    for i in range(36, 42):  # Left eye
        direction = landmarks[i] - left_eye_center
        landmarks_mod[i] = left_eye_center + direction * [scale_factor, eye_vert * scale_factor]
    
    for i in range(42, 48):  # Right eye
        direction = landmarks[i] - right_eye_center
        landmarks_mod[i] = right_eye_center + direction * [scale_factor, eye_vert * scale_factor]
    
    return landmarks_mod

def create_smile(landmarks, intensity=0.5):
    """Create a smile by modifying mouth landmarks"""
    landmarks_mod = landmarks.copy()
    
    # Get mouth corners
    left_corner = landmarks[48]   # Left corner
    right_corner = landmarks[54]  # Right corner
    
    # Move corners slightly outward and up (more conservative)
    landmarks_mod[48] += [-2 * intensity, -2 * intensity]  # Left corner
    landmarks_mod[54] += [2 * intensity, -2 * intensity]   # Right corner
    
    # Upper lip - slight upward curve
    landmarks_mod[51] += [0, -1 * intensity]  # Top center
    landmarks_mod[49] += [0, -0.5 * intensity]  # Left of center
    landmarks_mod[53] += [0, -0.5 * intensity]  # Right of center
    
    return landmarks_mod

def smooth_landmarks(landmarks, sigma=0.5):
    """Apply slight smoothing to landmarks to avoid harsh transitions"""
    smoothed = landmarks.copy()
    for i in range(len(landmarks)):
        if i > 0 and i < len(landmarks) - 1:
            smoothed[i] = (landmarks[i-1] + landmarks[i] * 2 + landmarks[i+1]) / 4
    return smoothed

def getFaceLandMarks(rgb):
    print("Beginning NN detection...")
    # Initialize face-alignment with 2D landmarks
    fa = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D, device='cpu')
    landmarks = fa.get_landmarks(rgb)

    if landmarks is None:
        raise RuntimeError("No face detected.")

    landmarks = landmarks[0]  # Assume first face

    print(f"Detected {len(landmarks)} facial landmarks")
    return landmarks



def processFaceMorph(img, landmarks, eyeScale = 2, smileIntensity=20, eye_vert = 1):
    # Apply transformations with more conservative settings
    landmarks_big_eyes = enlarge_eyes_advanced(landmarks, scale_factor=eyeScale, eye_vert=eye_vert)

    landmarks_smile = create_smile(landmarks_big_eyes, intensity=smileIntensity)


    # Skip smoothing for now to avoid over-processing
    landmarks_final = landmarks_smile

    # Apply the warp
    result = apply_triangular_warp(img, landmarks, landmarks_final)

    # Post-processing: slight blur to smooth any artifacts
    result = cv2.bilateralFilter(result, 5, 50, 50)
    return result

def draw_landmarks(img, landmarks, color=(0, 255, 0), radius=2, connect=True):
    img_vis = img.copy()
    landmarks = landmarks.astype(int)

    # Draw points
    for idx, (x, y) in enumerate(landmarks):
        cv2.circle(img_vis, (x, y), radius, color, -1)
        cv2.putText(img_vis, str(idx), (x + 3, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

    if not connect:
        return img_vis

    # Connect landmark groups (68-point landmarks standard)
    # Jawline
    for i in range(1, 17):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    # Left eyebrow
    for i in range(18, 22):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    # Right eyebrow
    for i in range(23, 27):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    # Nose bridge
    for i in range(28, 31):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    # Lower nose
    for i in range(32, 36):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    cv2.line(img_vis, tuple(landmarks[35]), tuple(landmarks[31]), color, 1)
    # Left eye
    for i in range(37, 42):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    cv2.line(img_vis, tuple(landmarks[41]), tuple(landmarks[36]), color, 1)
    # Right eye
    for i in range(43, 48):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    cv2.line(img_vis, tuple(landmarks[47]), tuple(landmarks[42]), color, 1)
    # Outer lip
    for i in range(49, 60):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    cv2.line(img_vis, tuple(landmarks[59]), tuple(landmarks[48]), color, 1)
    # Inner lip
    for i in range(61, 68):
        cv2.line(img_vis, tuple(landmarks[i-1]), tuple(landmarks[i]), color, 1)
    cv2.line(img_vis, tuple(landmarks[67]), tuple(landmarks[60]), color, 1)

    return img_vis

def make_sigma_face(landmarks, eye_closure=0.5, brow_raise=1.5, smile_intensity=0.5):
    landmarks_mod = landmarks.copy()

    # --- Eye squint: lower upper eyelid, raise lower eyelid ---
    # Left eye: 37-42, Right eye: 43-48
    eye_pairs = [
        (37, 41), (38, 40),  # Left eye verticals
        (43, 47), (44, 46)   # Right eye verticals
    ]
    for i_top, i_bottom in eye_pairs:
        center = (landmarks[i_top] + landmarks[i_bottom]) / 2
        direction = landmarks[i_bottom] - landmarks[i_top]
        landmarks_mod[i_top] += direction * eye_closure * 0.5
        landmarks_mod[i_bottom] -= direction * eye_closure * 0.5

    # --- Raise inner eyebrows (serious/stern look) ---

    # --- Optional: Lower outer eyebrows slightly ---
    for i in range(17, 27):  # Outer eyebrows
        landmarks_mod[i] += [0, -brow_raise]

    # --- Subtle smile ---
    landmarks_mod = create_smile(landmarks_mod, intensity=smile_intensity)

    return landmarks_mod


class debugClass:
    def __init__(self):
        import threading

        self.cacheLock = threading.Lock()


if __name__ == "__main__":

    # Load image
    img = cv2.imread("Aapodebug.jpg")
    if img is None:
        raise FileNotFoundError("Could not load image. Please check the path.")

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    #target_height = 400
    #h, w = rgb.shape[:2]
    #aspect_ratio = w / h
    #new_width = int(target_height * aspect_ratio)
#
    #resized_rgb = cv2.resize(rgb, (new_width, target_height), interpolation=cv2.INTER_AREA)

    # Initialize face-alignment with 2D landmarks

    debug = debugClass()

    landmarks = get_or_load_landmarks(app=debug, name="Aapodebug", rgb=rgb)
    landmarks = enlarge_eyes_advanced(landmarks, scale_factor=2)
    landmarks_sigma = make_sigma_face(landmarks, eye_closure=0.6, brow_raise=50, smile_intensity=5)
    result = apply_triangular_warp(img, landmarks, landmarks_sigma)

    #

    # Visualize original landmarks on the original image
    result = draw_landmarks(result, landmarks_sigma, color=(0,255,0), radius=3)

    cv2.imwrite("original_landmarks.png", result)
    #cv2.imwrite("morphed_landmarks.png", img_with_morphed)
