import mss
import numpy as np


def screenshot_to_numpy(monitor=1):
    """
    Takes a screenshot of the specified monitor and returns it as a NumPy array.

    Args:
        monitor (int): Monitor index (1 = primary monitor)

    Returns:
        np.ndarray: Screenshot image in BGRA format (H, W, 4)
    """
    with mss.mss() as sct:
        # Get the monitor info
        mon = sct.monitors[monitor]
        # Force exact dimensions: 1920x1200
        capture_region = {"top": 0, "left": 0, "width": 1920, "height": 1200}
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


def get_collision_map():
    return image_to_bool_mask(screenshot_to_numpy())
