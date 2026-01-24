# overlay.py
# Transparent always-on-top overlay window that repaints at a configurable FPS
# Draws a set of images at given screen coordinates.
#
# Dependencies:
#   pip install PyQt6 numpy
# (PyQt5 also supported via fallback)

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Union
import urllib.request

import numpy as np

# ----------------------------
# Configurable performance knob
# ----------------------------
TARGET_FPS: int = 60  # <<< change this instead of hardcoding "60fps"
FRAME_INTERVAL_MS: int = max(1, int(1000 / TARGET_FPS))


# --------
# Qt setup
# --------
try:
    # PyQt6
    from PyQt6.QtCore import Qt, QTimer, QRect
    from PyQt6.QtGui import QPainter, QPixmap, QImage
    from PyQt6.QtWidgets import QWidget

    QT6 = True
except ImportError:
    # PyQt5 fallback
    from PyQt5.QtCore import Qt, QTimer, QRect
    from PyQt5.QtGui import QPainter, QPixmap, QImage
    from PyQt5.QtWidgets import QWidget

    QT6 = False


ImageSource = Union[str, np.ndarray, QPixmap]


@dataclass
class OverlayImage:
    pixmap: QPixmap
    x: int
    y: int
    flip_horizontal: bool = False


class Overlay(QWidget):
    """
    Transparent overlay window that stays on top and repaints at TARGET_FPS.

    Use set_images(...) to provide images + coordinates.
      - image can be a URL (str), a NumPy array (H,W,3 or H,W,4), or a QPixmap.
      - coordinates are screen pixels (x,y) relative to top-left of the overlay.
    """

    def __init__(
        self,
        screen_rect: Optional[QRect] = None,
        click_through: bool = True,
        parent=None,
    ):
        super().__init__(parent)

        # Window flags for always-on-top, frameless overlay
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setWindowFlags(flags)

        # Transparent background + no system background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        # Optional: allow mouse/keyboard events to pass through to underlying windows
        if click_through:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # Fullscreen over a chosen screen rect
        if screen_rect is None:
            screen_rect = self._primary_screen_rect()

        # Set fixed size and position
        self.setGeometry(screen_rect)
        self.setFixedSize(screen_rect.width(), screen_rect.height())
        self.move(screen_rect.x(), screen_rect.y())

        # Stored images to draw
        self.images: List[OverlayImage] = []

        # 60fps-ish repaint timer (configurable via TARGET_FPS)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.update)
        self._timer.start(FRAME_INTERVAL_MS)

        self.show()

    # -------------------
    # Public API methods
    # -------------------
    def set_images(
        self,
        items: Iterable[Tuple[ImageSource, int, int, ...]],
        *,
        assume_numpy_format: str = "BGRA",
    ) -> None:
        """
        Replace the current image list.

        Args:
            items: iterable of (image_source, x, y) or (image_source, x, y, flip_horizontal)
                image_source can be:
                  - URL string (http/https/file)
                  - numpy array shape (H,W,3) or (H,W,4), dtype uint8
                  - QPixmap
                flip_horizontal: optional bool, whether to flip the image horizontally
            assume_numpy_format:
                When numpy has 4 channels, interpret it as "BGRA" (common from mss)
                or "RGBA". For 3 channels, assumes "RGB".
        """
        converted: List[OverlayImage] = []
        for item in items:
            if len(item) == 3:
                src, x, y = item
                flip = False
            else:
                src, x, y, flip = item

            pm = self._to_pixmap(src, assume_numpy_format=assume_numpy_format)
            if not pm.isNull():
                converted.append(OverlayImage(pm, int(x), int(y), flip))

        self.images = converted
        self.update()

    def start(self) -> None:
        """Start refreshing."""
        if not self._timer.isActive():
            self._timer.start(FRAME_INTERVAL_MS)

    def stop(self) -> None:
        """Stop refreshing."""
        if self._timer.isActive():
            self._timer.stop()

    # ---------------
    # QWidget overrides
    # ---------------
    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        # Disable smooth transform for exact 1:1 pixel rendering
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        # Draw each pixmap at its coordinates
        for it in self.images:
            if it.flip_horizontal:
                # Flip horizontally by transforming the painter
                painter.save()
                painter.translate(it.x + it.pixmap.width(), it.y)
                painter.scale(-1, 1)
                painter.drawPixmap(0, 0, it.pixmap)
                painter.restore()
            else:
                painter.drawPixmap(it.x, it.y, it.pixmap)

        painter.end()

    # ----------------
    # Internal helpers
    # ----------------
    def _primary_screen_rect(self) -> QRect:
        # Works without needing QApplication reference here; caller should have one running.
        # QWidget has screen() in Qt6, but may be None before show; this is robust enough.
        if QT6:
            scr = (
                self.screen() or self.windowHandle().screen()
                if self.windowHandle()
                else None
            )
            if scr is None:
                # fallback: use current geometry as last resort
                return (
                    self.geometry()
                    if not self.geometry().isNull()
                    else QRect(0, 0, 1920, 1080)
                )
            g = scr.geometry()
            return QRect(g.x(), g.y(), g.width(), g.height())
        else:
            # PyQt5: QWidget.screen() exists on newer versions; otherwise use desktop geometry fallback
            try:
                scr = self.screen()
                g = scr.geometry()
                return QRect(g.x(), g.y(), g.width(), g.height())
            except Exception:
                return QRect(0, 0, 1920, 1080)

    def _to_pixmap(self, src: ImageSource, *, assume_numpy_format: str) -> QPixmap:
        if isinstance(src, QPixmap):
            return src

        if isinstance(src, str):
            return self._pixmap_from_url(src)

        if isinstance(src, np.ndarray):
            return self._pixmap_from_numpy(src, assume_numpy_format=assume_numpy_format)

        raise TypeError(f"Unsupported image source type: {type(src)}")

    def _pixmap_from_url(self, url: str) -> QPixmap:
        pm = QPixmap()
        try:
            # Check if it's a local file path
            if not url.startswith(("http://", "https://", "file://")):
                # It's a local file path - load directly
                pm = QPixmap(url)
                if pm.isNull():
                    print(f"Warning: Failed to load image from: {url}")
                return pm

            # It's a URL - download and load
            with urllib.request.urlopen(url) as resp:
                data = resp.read()
            pm.loadFromData(data)
        except Exception as e:
            # Keep null pixmap if download/load fails
            print(f"Error loading image from {url}: {e}")
            return QPixmap()
        return pm

    def _pixmap_from_numpy(
        self, arr: np.ndarray, *, assume_numpy_format: str
    ) -> QPixmap:
        if not isinstance(arr, np.ndarray):
            return QPixmap()

        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)

        if arr.ndim != 3 or arr.shape[2] not in (3, 4):
            raise ValueError("NumPy image must have shape (H, W, 3) or (H, W, 4).")

        h, w, c = arr.shape
        arr_c = np.ascontiguousarray(arr)

        if c == 3:
            # Assume RGB
            fmt = QImage.Format.Format_RGB888 if QT6 else QImage.Format_RGB888
            qimg = QImage(arr_c.data, w, h, 3 * w, fmt)
            return QPixmap.fromImage(qimg)

        # c == 4
        # Common sources:
        #  - mss -> BGRA
        #  - some libs -> RGBA
        assume = assume_numpy_format.upper().strip()
        if assume == "BGRA":
            # Convert BGRA -> RGBA for QImage if needed; QImage has Format_RGBA8888
            rgba = arr_c[:, :, [2, 1, 0, 3]]
        elif assume == "RGBA":
            rgba = arr_c
        else:
            raise ValueError(
                "assume_numpy_format must be 'BGRA' or 'RGBA' for 4-channel arrays."
            )

        rgba_c = np.ascontiguousarray(rgba)
        fmt = QImage.Format.Format_RGBA8888 if QT6 else QImage.Format_RGBA8888
        qimg = QImage(rgba_c.data, w, h, 4 * w, fmt)
        return QPixmap.fromImage(qimg)
