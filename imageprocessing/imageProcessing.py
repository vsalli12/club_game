import pygame

import numpy as np
from PIL import Image
from rembg import remove
import io
import random

import pygame
import colorsys


def get_apex_pixel_mean(surface: pygame.Surface, threshold=1, min_pixels=3, max_spread=20):
    arr = pygame.surfarray.array_alpha(surface)

    for y in range(arr.shape[0]):
        row = arr[y]
        visible = row >= threshold
        count = np.count_nonzero(visible)
        
        if count >= min_pixels:
            xs = np.where(visible)[0]
            
            # Check if pixels are reasonably clustered (not too spread out)
            if True:
                x_mean = int(xs.mean())
                print(f"Row {y}: {count} visible pixels, x_mean={x_mean}")
                return x_mean - arr.shape[1]/2, y - arr.shape[0]/2

    print("No valid apex found.")
    return None

def set_image_hue_rgba(surface, hue_degrees):
    hue = hue_degrees / 360.0
    rgb_array = pygame.surfarray.pixels3d(surface).copy()
    alpha_array = pygame.surfarray.pixels_alpha(surface).copy()

    arr_float = rgb_array.astype(np.float32) / 255.0
    h, w = rgb_array.shape[:2]
    reshaped = arr_float.reshape(-1, 3)

    new_rgb = np.empty_like(reshaped)
    for i, (r, g, b) in enumerate(reshaped):
        h0, l, s = colorsys.rgb_to_hls(r, g, b)
        r1, g1, b1 = colorsys.hls_to_rgb(hue, l, s)
        new_rgb[i] = [r1, g1, b1]

    result_rgb = (new_rgb.reshape(h, w, 3) * 255).astype(np.uint8)

    # Create output surface and blit RGB
    surface_out = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(surface_out, result_rgb)

    # Apply alpha channel
    surface_out.lock()
    pygame.surfarray.pixels_alpha(surface_out)[:, :] = alpha_array
    surface_out.unlock()

    return surface_out



def roughen_surface(surface, roughness=0.3, scale=4):
    w, h = surface.get_size()
    mask_w, mask_h = w // scale, h // scale

    # Generate low-res noise and upscale it
    noise = np.random.rand(mask_w, mask_h) < roughness
    noise = noise.astype(np.uint8) * 255
    noise_surface = pygame.surfarray.make_surface(np.repeat(np.repeat(noise[:, :, None], scale, axis=0), scale, axis=1).squeeze())

    # Ensure size match
    noise_surface = pygame.transform.scale(noise_surface, (w, h))
    noise_surface.set_colorkey((0, 0, 0))  # Black = masked out

    # Mask original with noise
    masked = surface.copy()
    masked.blit(noise_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    return masked

def generate_corpse_sprite(surface):
    #bloodied = colorize_to_blood(surface)
    corpse = split_displace_blood_sprite(surface, parts = random.randint(3,5), max_offset=50, max_angle=30)
    #corpse = pad_surface(corpse)
    #blurred = fast_gaussian_blur(corpse, sigma=2.5)
    return corpse

def pad_surface(surface, pad_x=10, pad_y=10):
    w, h = surface.get_size()
    padded = pygame.Surface((w + 2 * pad_x, h + 2 * pad_y), pygame.SRCALPHA)
    padded.blit(surface, (pad_x, pad_y))
    return padded

def collapse_to_floor(surface, twist_angle=40, flatten=0.4):
    # Flatten Y
    w, h = surface.get_size()
    flattened = pygame.transform.smoothscale(surface, (w, int(h * flatten)))
    # Rotate to appear "collapsed"
    twisted = pygame.transform.rotate(flattened, twist_angle)
    return twisted

def brighten_surface(surface, gain=2.5, offset=40):
    arr = pygame.surfarray.pixels3d(surface).copy()
    alpha = pygame.surfarray.pixels_alpha(surface).copy()

    arr = arr.astype(np.float32)
    arr = arr * gain + offset
    np.clip(arr, 0, 255, out=arr)

    arr = arr.astype(np.uint8)

    result = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(result, arr)
    pygame.surfarray.pixels_alpha(result)[:, :] = alpha
    return result



def outline_surface(src: pygame.Surface, width: int) -> pygame.Surface:
    w, h = src.get_size()
    src = src.convert_alpha()

    mask = pygame.mask.from_surface(src)

    out_w = w + 2 * width
    out_h = h + 2 * width
    result = pygame.Surface((out_w, out_h), pygame.SRCALPHA)

    # Draw expanded mask (outline)
    outline_mask = mask.copy()
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx*dx + dy*dy > width*width:
                continue
            result.blit(
                outline_mask.to_surface(setcolor=(0, 0, 0, 255), unsetcolor=(0, 0, 0, 0)),
                (dx + width, dy + width),
                special_flags=pygame.BLEND_PREMULTIPLIED
            )

    # Subtract original alpha region so outline stays outside
    result.blit(src, (width, width), special_flags=pygame.BLEND_RGBA_SUB)

    # Draw original on top
    result.blit(src, (width, width))

    return result



def colorize_to_blood(surface):
    arr = pygame.surfarray.pixels3d(surface).copy()
    alpha = pygame.surfarray.pixels_alpha(surface).copy()

    # Convert to grayscale
    gray = (0.3 * arr[:, :, 0] + 0.59 * arr[:, :, 1] + 0.11 * arr[:, :, 2])
    
    # Scale gray to dark red
    arr[:, :, 0] = np.clip(gray * 0.9 + 60, 0, 255)   # R
    arr[:, :, 1] = np.clip(gray * 0.1, 0, 50)         # G
    arr[:, :, 2] = np.clip(gray * 0.1, 0, 50)         # B

    result = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(result, arr)
    pygame.surfarray.pixels_alpha(result)[:, :] = alpha
    return result
    
import math
def create_irregular_mask(width, height, jaggedness=0.3, num_points=8):
    """Create an irregular mask with jagged edges"""
    # Create points around the perimeter for a rough shape
    points = []
    center_x, center_y = width // 2, height // 2
    
    for i in range(num_points):
        angle = (2 * math.pi * i) / num_points
        # Base radius with random variation
        base_radius = min(width, height) * 0.4
        radius = base_radius * (1 + random.uniform(-jaggedness, jaggedness))
        
        x = center_x + radius * math.cos(angle)
        y = center_y + radius * math.sin(angle)
        
        # Add some random noise to make it more jagged
        x += random.randint(-int(width * 0.1), int(width * 0.1))
        y += random.randint(-int(height * 0.1), int(height * 0.1))
        
        points.append((max(0, min(width-1, x)), max(0, min(height-1, y))))
    
    # Create mask surface
    mask_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    if len(points) >= 3:
        pygame.draw.polygon(mask_surface, (255, 255, 255, 255), points)
    
    return mask_surface

def create_torn_edge_mask(width, height, edge_roughness=0.2):
    """Create a mask with torn/ripped edges"""
    mask = pygame.Surface((width, height), pygame.SRCALPHA)
    
    # Start with a basic shape
    base_points = []
    num_edges = random.randint(6, 12)
    
    for i in range(num_edges):
        angle = (2 * math.pi * i) / num_edges
        # Vary the radius more dramatically for torn effect
        radius_var = random.uniform(0.3, 0.8)
        x = width/2 + (width/2 * radius_var * math.cos(angle))
        y = height/2 + (height/2 * radius_var * math.sin(angle))
        
        # Add jagged sub-points between main points
        if i > 0:
            prev_x, prev_y = base_points[-1]
            # Add 1-3 intermediate jagged points
            for j in range(random.randint(1, 3)):
                t = (j + 1) / (random.randint(1, 3) + 1)
                mid_x = prev_x + t * (x - prev_x)
                mid_y = prev_y + t * (y - prev_y)
                
                # Offset perpendicular to create jagged edge
                perp_x = -(y - prev_y)
                perp_y = (x - prev_x)
                length = math.sqrt(perp_x**2 + perp_y**2)
                if length > 0:
                    perp_x /= length
                    perp_y /= length
                
                offset = random.uniform(-edge_roughness * min(width, height), 
                                      edge_roughness * min(width, height))
                mid_x += perp_x * offset
                mid_y += perp_y * offset
                
                base_points.append((max(0, min(width-1, mid_x)), 
                                  max(0, min(height-1, mid_y))))
        
        base_points.append((max(0, min(width-1, x)), max(0, min(height-1, y))))
    
    if len(base_points) >= 3:
        pygame.draw.polygon(mask, (255, 255, 255, 255), base_points)
    
    return mask

def apply_mask_to_surface(surface, mask):
    """Apply an irregular mask to a surface"""
    result = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    
    # Convert to pixel arrays for faster processing
    surf_array = pygame.surfarray.array3d(surface)
    alpha_array = pygame.surfarray.array_alpha(surface)
    mask_array = pygame.surfarray.array_alpha(mask)
    
    # Apply mask to alpha channel
    new_alpha = np.minimum(alpha_array, mask_array)
    
    # Create new surface
    pygame.surfarray.blit_array(result, surf_array)
    pygame.surfarray.pixels_alpha(result)[:] = new_alpha
    
    return result

def split_displace_blood_sprite(surface, parts=4, max_offset=12, max_angle=30, 
                               jaggedness=0.4, edge_roughness=0.3):
    """
    Create corpse sprite with irregular, jagged parts instead of rectangular slices
    
    Args:
        surface: Original sprite surface
        parts: Number of parts to split into
        max_offset: Maximum random offset for positioning
        max_angle: Maximum rotation angle
        jaggedness: How irregular the part shapes are (0.0-1.0)
        edge_roughness: How rough/torn the edges look (0.0-1.0)
    """
    w, h = surface.get_size()
    
    # Estimate required output surface size
    out_h = h + max_offset * 4  # Extra space for irregular shapes
    out_w = w + max_offset * 4
    final = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
    
    # Define regions for parts (still use this as a guide)
    part_height = h // parts
    
    for i in range(parts):
        # Define the region this part should roughly come from
        region_y = i * part_height
        region_height = part_height if i < parts - 1 else h - region_y
        
        # Create a larger working area around this region
        work_margin = max(20, int(min(w, h) * 0.2))
        work_y = max(0, region_y - work_margin)
        work_height = min(h - work_y, region_height + work_margin * 2)
        work_surface = pygame.Surface((w, work_height), pygame.SRCALPHA)
        
        # Extract the working region
        work_surface.blit(surface, (0, 0), 
                         area=pygame.Rect(0, work_y, w, work_height))
        
        # Create irregular mask - choose between torn edge or irregular blob
        if random.random() < 0.6:  # 60% chance for torn edge
            mask = create_torn_edge_mask(w, work_height, edge_roughness)
        else:  # 40% chance for irregular blob
            mask = create_irregular_mask(w, work_height, jaggedness)
        
        # Apply mask to create irregular part
        irregular_part = apply_mask_to_surface(work_surface, mask)
        
        # Apply blood effects
        irregular_part = colorize_to_blood(irregular_part)
        #irregular_part = roughen_surface(irregular_part, roughness=0.4)
        irregular_part = pad_surface(irregular_part)
        irregular_part = fast_gaussian_blur(irregular_part, sigma=1.5)
        
        # Rotate and position
        angle = random.uniform(-max_angle, max_angle)
        offset_x = random.randint(-max_offset, max_offset)
        # Position relative to original region center
        offset_y = region_y + region_height // 2 + random.randint(-max_offset, max_offset)
        
        rotated = pygame.transform.rotate(irregular_part, angle)
        rect = rotated.get_rect(center=(out_w // 2 + offset_x, 
                                       offset_y + max_offset * 2))
        
        # Blit to final surface
        final.blit(rotated, rect.topleft)
    
    return final

# Alternative simpler version using built-in pygame drawing
def split_displace_blood_sprite_simple(surface, parts=4, max_offset=12, max_angle=30):
    """Simpler version using pygame's built-in polygon drawing"""
    w, h = surface.get_size()
    out_h = h + max_offset * 4
    out_w = w + max_offset * 4
    final = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
    
    part_height = h // parts
    
    for i in range(parts):
        region_y = i * part_height
        region_height = part_height if i < parts - 1 else h - region_y
        
        # Create irregular shape points
        points = []
        num_points = random.randint(8, 15)
        
        for j in range(num_points):
            # Distribute points around the region
            if j < num_points // 4:  # Top edge
                x = random.randint(0, w)
                y = region_y + random.randint(-10, 10)
            elif j < num_points // 2:  # Right edge  
                x = w + random.randint(-10, 10)
                y = random.randint(region_y, region_y + region_height)
            elif j < 3 * num_points // 4:  # Bottom edge
                x = random.randint(0, w)
                y = region_y + region_height + random.randint(-10, 10)
            else:  # Left edge
                x = random.randint(-10, 10)
                y = random.randint(region_y, region_y + region_height)
            
            points.append((max(0, min(w-1, x)), max(0, min(h-1, y))))
        
        # Create mask with irregular shape
        mask = pygame.Surface((w, h), pygame.SRCALPHA)
        if len(points) >= 3:
            pygame.draw.polygon(mask, (255, 255, 255, 255), points)
        
        # Apply mask
        part = pygame.Surface((w, h), pygame.SRCALPHA)
        for x in range(w):
            for y in range(h):
                if mask.get_at((x, y))[3] > 0:  # If mask is not transparent
                    part.set_at((x, y), surface.get_at((x, y)))
        
        # Apply effects and position
        part = colorize_to_blood(part)
        part = roughen_surface(part, roughness=0.4)
        part = pad_surface(part)
        part = fast_gaussian_blur(part, sigma=1.5)
        
        angle = random.uniform(-max_angle, max_angle)
        offset_x = random.randint(-max_offset, max_offset)
        offset_y = region_y + random.randint(-max_offset, max_offset)
        
        rotated = pygame.transform.rotate(part, angle)
        rect = rotated.get_rect(center=(out_w // 2 + offset_x, 
                                       offset_y + max_offset * 2))
        
        final.blit(rotated, rect.topleft)
    
    return final



def gaussian_blur(surface, sigma=5):
    """
    Apply a Gaussian blur to a Pygame surface.

    Args:
        surface (pygame.Surface): The surface to blur.
        sigma (float): The standard deviation for the Gaussian kernel.

    Returns:
        pygame.Surface: A new surface with the Gaussian blur applied.
    """
    # Convert surface to an array
    width, height = surface.get_size()
    
    # Get the RGB and alpha channels
    rgb_array = pygame.surfarray.array3d(surface)
    alpha_array = pygame.surfarray.array_alpha(surface)

    # Create a Gaussian kernel
    kernel_size = int(2 * (sigma + 0.5)) + 1
    kernel = np.fromfunction(
        lambda x, y: (1 / (2 * np.pi * sigma ** 2)) * 
                      np.exp(-((x - (kernel_size - 1) / 2) ** 2 + (y - (kernel_size - 1) / 2) ** 2) / (2 * sigma ** 2)),
        (kernel_size, kernel_size)
    )
    kernel /= np.sum(kernel)  # Normalize the kernel

    # Pad the RGB and alpha arrays
    pad_width = kernel_size // 2
    padded_rgb = np.pad(rgb_array, ((pad_width, pad_width), (pad_width, pad_width), (0, 0)), mode='reflect')
    padded_alpha = np.pad(alpha_array, ((pad_width, pad_width), (pad_width, pad_width)), mode='reflect')

    # Create an output array for RGB and alpha
    output_rgb = np.zeros_like(rgb_array)
    output_alpha = np.zeros_like(alpha_array)

    # Apply the Gaussian blur for each color channel
    for i in range(width):
        for j in range(height):
            # Extract the region of interest for the current pixel
            region_rgb = padded_rgb[i:i + kernel_size, j:j + kernel_size]
            region_alpha = padded_alpha[i:i + kernel_size, j:j + kernel_size]
            # Apply the kernel to each color channel
            for channel in range(3):  # Loop over the RGB channels
                output_rgb[i, j, channel] = np.sum(kernel * region_rgb[:, :, channel])
            # Average the alpha value
            output_alpha[i, j] = np.sum(kernel * region_alpha)

    # Create a new RGBA surface
    blurred_surface = pygame.Surface((width, height), pygame.SRCALPHA)

    # Set the RGB values
    pygame.surfarray.blit_array(blurred_surface, output_rgb)

    # Set the alpha values manually
    for i in range(width):
        for j in range(height):
            blurred_surface.set_at((i, j), (*output_rgb[i, j], output_alpha[i, j]))

    return blurred_surface


from scipy.ndimage import gaussian_filter

def fast_gaussian_blur(surface, sigma=5):
    rgb = pygame.surfarray.array3d(surface).astype(np.float32)
    alpha = pygame.surfarray.array_alpha(surface).astype(np.float32)

    for c in range(3):
        rgb[:, :, c] = gaussian_filter(rgb[:, :, c], sigma=sigma)
    alpha = gaussian_filter(alpha, sigma=sigma)

    rgb = np.clip(rgb, 0, 255).astype(np.uint8)
    alpha = np.clip(alpha, 0, 255).astype(np.uint8)

    blurred = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.surfarray.blit_array(blurred, rgb)
    pygame.surfarray.pixels_alpha(blurred)[:, :] = alpha

    return blurred

def remove_background_bytes(input_bytes):
    # Remove the background
    output_bytes = remove(input_bytes)

    # Return output bytes (PNG format)
    return output_bytes

import base64
import hashlib
import json
import os
import traceback

def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def load_bg_cache(app, cache_path="background_cache.json"):
    with app.cacheLock:
        if os.path.isfile(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

def save_bg_cache(app, data, cache_path="background_cache.json"):
    with app.cacheLock:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

def get_or_remove_background(app, input_bytes, cache_path="background_cache.json"):
    key = bytes_hash(input_bytes)
    initial_cache = load_bg_cache(app, cache_path)

    if key in initial_cache:
        return base64.b64decode(initial_cache[key]) if initial_cache[key] is not None else None

    try:
        output_bytes = remove(input_bytes)
        new_data = base64.b64encode(output_bytes).decode("utf-8")
    except:
        traceback.print_exc()
        output_bytes = None
        new_data = None

    if new_data:
        latest_cache = load_bg_cache(app, cache_path)
        latest_cache[key] = new_data
        save_bg_cache(app, latest_cache, cache_path)

    return output_bytes



def remove_background(input_path, output_path):
    print("Removing:", input_path)
    # Open the input image file
    with open(input_path, 'rb') as input_file:
        input_image = input_file.read()

    # Remove the background
    output_image = remove(input_image)

    # Convert the output bytes to an image and save it
    img = Image.open(io.BytesIO(output_image))
    img.save(output_path)

    print(f"Background removed and saved to {output_path}")

def trim_surface(surface):
    # Get the surface size
    width, height = surface.get_size()

    # Lock the surface to directly access the pixel array
    surface.lock()

    # Create a mask based on alpha transparency (non-zero alpha means non-transparent)
    mask = pygame.mask.from_surface(surface)

    # Get the bounding box of the non-transparent area
    rects = mask.get_bounding_rects()


    
    if rects:
        rects.sort(key=lambda r: r.width * r.height, reverse=True)
        # If a bounding box is found, crop the surface to that bounding box
        trimmed_surface = surface.subsurface(rects[0]).copy()
    else:
        # If no bounding box is found (fully transparent image), return the original surface
        trimmed_surface = surface.copy()

    # Unlock the surface after accessing the pixels
    surface.unlock()

    return trimmed_surface
