import mss
import numpy as np


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


# takes an image as a numpy array and returns a boolean collision mask
# True  = collision
# False = background (dark)
def image_to_bool_mask(image, threshold=100):
    """
    Args:
        image: numpy array (H,W,3) or (H,W,4) uint8
        threshold: brightness cutoff (0–255). Higher = fewer collisions.

    Returns:
        mask: np.ndarray (H,W) dtype=bool
    """

    # If BGRA or RGBA, drop alpha
    if image.ndim == 3 and image.shape[2] == 4:
        image = image[:, :, :3]

    # Convert to grayscale (perceptual luminance)
    if image.ndim == 3:
        # Assume RGB or BGR; weights work fine either way for thresholding
        gray = (
            0.2126 * image[:, :, 0] + 0.7152 * image[:, :, 1] + 0.0722 * image[:, :, 2]
        )
    else:
        gray = image  # already grayscale

    # Boolean collision map
    mask = gray > threshold
    return mask


import numpy as np


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

    return image_to_bool_mask(screenshot)
