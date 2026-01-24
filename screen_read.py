import mss
import numpy as np
import colorsys
import traceback


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
    color1, color2, hue_threshold=0.1, lightness_threshold=0.2, saturation_threshold=0.3
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
    sample_rate=5,
    hue_threshold=0.1,
    lightness_threshold=0.2,
    saturation_threshold=0.3,
):
    """
    Find the most common color in the image by grouping similar colors together.

    Args:
        image: numpy array (H,W,3) or (H,W,4) uint8 in BGR or BGRA format
        sample_rate: Only check every Nth pixel for performance (default 5)
        hue_threshold: Maximum hue difference for grouping similar colors
        lightness_threshold: Maximum lightness difference for grouping
        saturation_threshold: Maximum saturation difference for grouping

    Returns:
        (B, G, R) tuple of the most common color
    """
    # If BGRA or RGBA, drop alpha
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]

    H, W = image.shape[:2]

    # Sample pixels for performance
    sampled_pixels = []
    for y in range(0, H, sample_rate):
        for x in range(0, W, sample_rate):
            pixel = tuple(image[y, x])  # BGR format
            sampled_pixels.append(pixel)

    if not sampled_pixels:
        return (0, 0, 0)

    # Group similar colors together
    color_groups = []  # List of (representative_color, count)

    for pixel in sampled_pixels:
        # Convert BGR to RGB for comparison
        pixel_rgb = (pixel[2], pixel[1], pixel[0])

        # Find existing group that this pixel matches
        found_group = False
        for i, (group_color, count) in enumerate(color_groups):
            group_rgb = (group_color[2], group_color[1], group_color[0])
            if colors_are_similar(
                pixel_rgb,
                group_rgb,
                hue_threshold,
                lightness_threshold,
                saturation_threshold,
            ):
                color_groups[i] = (group_color, count + 1)
                found_group = True
                break

        # If no matching group, create a new one
        if not found_group:
            color_groups.append((pixel, 1))

    # Find the group with the most pixels
    if not color_groups:
        return (0, 0, 0)

    most_common = max(color_groups, key=lambda x: x[1])
    return most_common[0]  # Return BGR tuple


def image_to_bool_mask(
    image,
    target_color=(0, 0, 0),
    always_background_colors=[(255, 72, 0)],  # color of the stickman
    hue_threshold=0.1,
    lightness_threshold=0.2,
    saturation_threshold=0.3,
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
        target_color = get_most_common_color(
            image,
            sample_rate=5,
            hue_threshold=hue_threshold,
            lightness_threshold=lightness_threshold,
            saturation_threshold=saturation_threshold,
        )

    # If BGRA or RGBA, drop alpha
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]

    H, W = image.shape[:2]

    # Initialize mask as all collision (True)
    mask = np.ones((H, W), dtype=bool)

    # Convert image from BGR to RGB for processing
    image_rgb = image[:, :, ::-1].copy()

    # Convert target color from BGR to RGB
    target_rgb = (target_color[2], target_color[1], target_color[0])

    # Check each pixel against target color
    for y in range(H):
        for x in range(W):
            pixel = tuple(image_rgb[y, x])

            # Check if similar to target color
            if colors_are_similar(
                pixel,
                target_rgb,
                hue_threshold,
                lightness_threshold,
                saturation_threshold,
            ):
                mask[y, x] = False
                continue

            # Check if matches any always-background colors
            for bg_color in always_background_colors:
                bg_rgb = (bg_color[2], bg_color[1], bg_color[0])
                if colors_are_similar(
                    pixel,
                    bg_rgb,
                    hue_threshold,
                    lightness_threshold,
                    saturation_threshold,
                ):
                    mask[y, x] = False
                    break

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
    stickman_right = min(width, stickman_local_x + stickman.width)
    stickman_bottom = min(height, stickman_local_y + stickman.height)

    if 0 <= stickman_local_x < width and 0 <= stickman_local_y < height:
        collision_mask[
            stickman_local_y:stickman_bottom, stickman_local_x:stickman_right
        ] = False

    return collision_mask
