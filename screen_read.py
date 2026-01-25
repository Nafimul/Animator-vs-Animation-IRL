import mss
import numpy as np
import colorsys
import traceback

# Cached background color (detected once and reused)
_cached_background_color = None


def detect_and_cache_background_color():
    """Detect the most common color and cache it for future use."""
    global _cached_background_color
    screenshot = screenshot_to_numpy()
    _cached_background_color = get_most_common_color(screenshot)
    print(f"🎨 Background color detected and cached: BGR{_cached_background_color}")
    return _cached_background_color


def get_cached_background_color():
    """Get the cached background color, detecting it if not yet cached."""
    global _cached_background_color
    if _cached_background_color is None:
        return detect_and_cache_background_color()
    return _cached_background_color


def screenshot_to_numpy(monitor=1, region=None):
    """
    Takes a screenshot of the specified monitor and returns it as a NumPy array.

    Args:
        monitor (int): Monitor index (1 = primary monitor)
        region (dict): Optional region dict with 'left', 'top', 'width', 'height'

    Returns:
        np.ndarray: Screenshot image in BGRA format (H, W, 4)
    """
    with mss.mss() as sct:
        # Use custom region or default to full screen
        if region is None:
            capture_region = {"top": 0, "left": 0, "width": 1920, "height": 1200}
        else:
            capture_region = region
        screenshot = sct.grab(capture_region)
        img = np.array(screenshot)
        return img


def colors_are_similar(
    color1, color2, hue_threshold, lightness_threshold, saturation_threshold
):
    """
        Check if two colors are similar using HLS color space.
    z
        Args:
            color1: (R, G, B) tuple with values 0-255
            color2: (R, G, B) tuple with values 0-255
            hue_threshold: Maximum difference in hue (0-1)
            lightness_threshold: Maximum difference in lightness (0-1)
            saturation_threshold: Maximum difference in saturation (0-1)

        Returns:
            bool: True if colors are similar
    """
    # Convert to 0-1 range
    r1, g1, b1 = color1[0] / 255.0, color1[1] / 255.0, color1[2] / 255.0
    r2, g2, b2 = color2[0] / 255.0, color2[1] / 255.0, color2[2] / 255.0

    # Convert to HLS
    h1, l1, s1 = colorsys.rgb_to_hls(r1, g1, b1)
    h2, l2, s2 = colorsys.rgb_to_hls(r2, g2, b2)

    # Special handling for low saturation colors (grey, black, white)
    # For these, hue is meaningless, so just check lightness
    if s1 < 0.1 or s2 < 0.1:
        # Both are unsaturated (grey/black/white), just check lightness
        return abs(l1 - l2) < lightness_threshold

    # For saturated colors, check hue, lightness, and saturation
    # Hue wraps around (0 and 1 are both red)
    hue_diff = abs(h1 - h2)
    if hue_diff > 0.5:
        hue_diff = 1.0 - hue_diff

    return (
        hue_diff < hue_threshold
        and abs(l1 - l2) < lightness_threshold
        and abs(s1 - s2) < saturation_threshold
    )


def get_most_common_color(
    image,
    sample_rate=15,  # Increased from 5 to 15 for better performance
    color_distance_threshold=100,  # RGB distance threshold (0-255 scale)
):
    """
    Find the most common color in the image by grouping similar colors together.
    Optimized version using simple RGB distance instead of HLS conversion.

    Args:
        image: numpy array (H,W,3) or (H,W,4) uint8 in BGR or BGRA format
        sample_rate: Only check every Nth pixel for performance (default 15)
        color_distance_threshold: Maximum RGB distance for grouping colors (default 50)

    Returns:
        (B, G, R) tuple of the most common color
    """
    # If BGRA or RGBA, drop alpha
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]

    H, W = image.shape[:2]

    # Sample pixels for performance (much more aggressive sampling)
    sampled_pixels = []
    for y in range(0, H, sample_rate):
        for x in range(0, W, sample_rate):
            pixel = tuple(image[y, x])  # BGR format
            sampled_pixels.append(pixel)

    if not sampled_pixels:
        return (0, 0, 0)

    # Fast color grouping using RGB distance instead of HLS
    # Store (sum_b, sum_g, sum_r, count) for each group to calculate average
    color_groups = []
    threshold_sq = color_distance_threshold**2  # Use squared distance to avoid sqrt

    for pixel in sampled_pixels:
        found_group = False
        for i, (sum_b, sum_g, sum_r, count) in enumerate(color_groups):
            # Calculate average color of this group
            avg_b = sum_b // count
            avg_g = sum_g // count
            avg_r = sum_r // count

            # Calculate squared RGB distance (faster than HLS conversion)
            dist_sq = (
                (int(pixel[0]) - avg_b) ** 2
                + (int(pixel[1]) - avg_g) ** 2
                + (int(pixel[2]) - avg_r) ** 2
            )
            if dist_sq <= threshold_sq:
                # Add to this group (convert to int to avoid overflow)
                color_groups[i] = (
                    sum_b + int(pixel[0]),
                    sum_g + int(pixel[1]),
                    sum_r + int(pixel[2]),
                    count + 1,
                )
                found_group = True
                break

        if not found_group:
            color_groups.append((int(pixel[0]), int(pixel[1]), int(pixel[2]), 1))

    if not color_groups:
        return (0, 0, 0)

    # Find group with highest count and return its average color
    most_common_group = max(color_groups, key=lambda x: x[3])
    sum_b, sum_g, sum_r, count = most_common_group
    avg_color = (sum_b // count, sum_g // count, sum_r // count)

    print(
        f"🔍 Sampled {len(sampled_pixels)} pixels, found {len(color_groups)} color groups"
    )
    print(f"🏆 Most common group: {count} pixels, average color: BGR{avg_color}")

    return avg_color


def image_to_bool_mask(
    image,
    target_color=None,
    always_background_colors=[
        (255, 72, 0),
        (0, 141, 255),
        (186, 224, 255),
    ],  # color of the stickman
    hue_threshold=0.1,
    lightness_threshold=0.1,
    saturation_threshold=0.1,
):
    """
    Creates a collision mask where colors similar to target_color are background (False),
    and everything else is collision (True).

    Args:
        image: numpy array (H,W,3) or (H,W,4) uint8 in BGR or BGRA format
        target_color: (B, G, R) tuple with values 0-255 - colors similar to this are background.
                     If None, automatically detects the most common color as background.
        always_background_colors: List of (B, G, R) tuples that are always considered background
        hue_threshold: Maximum hue difference for similarity (0-1)
        lightness_threshold: Maximum lightness difference for similarity (0-1)
        saturation_threshold: Maximum saturation difference for similarity (0-1)

    Returns:
        mask: np.ndarray (H,W) dtype=bool where True = collision, False = background
    """
    if always_background_colors is None:
        always_background_colors = []

    # Auto-detect target color if not provided
    if target_color is None:
        target_color = get_cached_background_color()

    # If BGRA or RGBA, drop alpha
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]

    H, W = image.shape[:2]

    # Initialize mask as all collision (True)
    mask = np.ones((H, W), dtype=bool)

    # Convert image from BGR to RGB
    image_rgb = image[:, :, ::-1].astype(np.float32) / 255.0

    # Vectorized color similarity check
    def check_color_similarity_vectorized(target_bgr):
        target_rgb = (
            np.array([target_bgr[2], target_bgr[1], target_bgr[0]], dtype=np.float32)
            / 255.0
        )

        # Convert entire image to HLS
        r, g, b = image_rgb[:, :, 0], image_rgb[:, :, 1], image_rgb[:, :, 2]

        # Compute HLS for entire image (vectorized)
        maxc = np.maximum(np.maximum(r, g), b)
        minc = np.minimum(np.minimum(r, g), b)
        l = (maxc + minc) / 2.0

        delta = maxc - minc
        s = np.zeros_like(l)
        mask_delta = delta > 0
        s[mask_delta] = np.where(
            l[mask_delta] <= 0.5,
            delta[mask_delta] / (maxc[mask_delta] + minc[mask_delta]),
            delta[mask_delta] / (2.0 - maxc[mask_delta] - minc[mask_delta]),
        )

        # Compute hue
        h = np.zeros_like(l)
        rc = np.where(mask_delta, (maxc - r) / delta, 0)
        gc = np.where(mask_delta, (maxc - g) / delta, 0)
        bc = np.where(mask_delta, (maxc - b) / delta, 0)

        h = np.where(r == maxc, bc - gc, h)
        h = np.where(g == maxc, 2.0 + rc - bc, h)
        h = np.where(b == maxc, 4.0 + gc - rc, h)
        h = (h / 6.0) % 1.0

        # Convert target to HLS
        t_h, t_l, t_s = colorsys.rgb_to_hls(target_rgb[0], target_rgb[1], target_rgb[2])

        # Check similarity
        if t_s < 0.1 or np.mean(s) < 0.1:
            # Low saturation - only check lightness
            return np.abs(l - t_l) < lightness_threshold
        else:
            # Check hue, lightness, saturation
            hue_diff = np.abs(h - t_h)
            hue_diff = np.minimum(hue_diff, 1.0 - hue_diff)  # Wrap around

            return (
                (hue_diff < hue_threshold)
                & (np.abs(l - t_l) < lightness_threshold)
                & (np.abs(s - t_s) < saturation_threshold)
            )

    # Mark target color as background
    is_background = check_color_similarity_vectorized(target_color)
    mask[is_background] = False

    # Mark always-background colors
    for bg_color in always_background_colors:
        is_background = check_color_similarity_vectorized(bg_color)
        mask[is_background] = False

    return mask


# True  -> white (255,255,255,255)
# False -> black (0,0,0,255)
def bool_mask_to_rgba(mask):
    """
    Args:
        mask: np.ndarray (H, W) dtype=bool

    Returns:
        rgba: np.ndarray (H, W, 4) dtype=uint8
    """
    h, w = mask.shape

    rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # Set RGB channels
    rgba[mask] = [255, 255, 255, 255]  # True = collision
    rgba[~mask] = [0, 0, 0, 255]  # False = background

    return rgba


def get_collision_map(stickman):
    """
    Get collision map for a region around the stickman.

    Args:
        stickman: Stickman object with pos, width, height attributes

    Returns:
        np.ndarray: Boolean collision map (H, W) for the region
    """
    # Define capture region: 100 pixels padding around stickman
    padding = 100
    x, y = stickman.pos

    # Calculate region bounds with padding
    left = int(max(0, x - padding))
    top = int(max(0, y - padding))
    right = int(min(1920, x + stickman.width + padding))
    bottom = int(min(1200, y + stickman.height + padding))

    width = right - left
    height = bottom - top

    # Store the collision map origin in the stickman
    stickman.collision_map_x = left
    stickman.collision_map_y = top

    # Capture only the region around the stickman
    region = {"left": left, "top": top, "width": width, "height": height}
    screenshot = screenshot_to_numpy(region=region)

    collision_mask = image_to_bool_mask(screenshot)

    # Exclude the stickman's own position from the collision map
    # Convert stickman screen position to local collision map coordinates
    stickman_local_x = int(x - left)
    stickman_local_y = int(y - top)

    # Clear collision in the stickman's area (make it background)
    # Clamp to valid bounds within the collision map
    stickman_left = max(0, stickman_local_x)
    stickman_top = max(0, stickman_local_y)
    stickman_right = min(width, stickman_local_x + stickman.width)
    stickman_bottom = min(height, stickman_local_y + stickman.height)

    if stickman_right > stickman_left and stickman_bottom > stickman_top:
        collision_mask[stickman_top:stickman_bottom, stickman_left:stickman_right] = (
            False
        )

    return collision_mask
