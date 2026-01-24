from overlay import Overlay
import screen_read
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRect, Qt
import os
import signal
from pynput import keyboard


class SignalHandler(QObject):
    """Thread-safe signal handler for shutdown requests"""

    shutdown_requested = pyqtSignal()


class App:
    def __init__(self):
        self.running = True
        self.overlay = None
        self.keyboard_listener = None
        self.signal_handler = SignalHandler()
        self.qt_app = None

    def on_press(self, key):
        """Global keyboard listener - stops everything when Z is pressed"""
        try:
            if hasattr(key, "char") and key.char and key.char.lower() == "z":
                print("\nZ key pressed - shutting down...")
                # Emit signal to trigger shutdown in main Qt thread
                self.signal_handler.shutdown_requested.emit()
        except AttributeError:
            pass

    def shutdown(self):
        """Thread-safe shutdown - must be called from Qt main thread"""
        self.running = False
        print("Shutting down...")

        # Stop the keyboard listener
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
            except:
                pass

        # Close overlay if it exists (we're in Qt thread now, so this is safe)
        if self.overlay:
            try:
                self.overlay.stop()  # Stop the timer
                self.overlay.close()  # Close the window
            except Exception as e:
                print(f"Error closing overlay: {e}")

        # Quit the QApplication
        if self.qt_app:
            self.qt_app.quit()

        print("Program terminated.")

    def start(self):
        """Start the application with global hotkey listener"""
        # Set up global keyboard listener (works regardless of focus)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.keyboard_listener.start()

        print("App started. Press 'Z' anywhere to exit (or Ctrl+C).")

        # Disable high DPI scaling to ensure exact pixel dimensions
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        # Create QApplication
        self.qt_app = QApplication(sys.argv)

        # Connect the signal to shutdown slot (thread-safe)
        self.signal_handler.shutdown_requested.connect(self.shutdown)

        # Set up Ctrl+C handler that works with Qt event loop
        signal.signal(signal.SIGINT, self._handle_sigint)
        # Use a timer to allow Python to process signals during Qt event loop
        timer = QTimer()
        timer.start(100)  # Check every 100ms
        timer.timeout.connect(lambda: None)  # Just allows Python to process signals

        # Hardcoded screen size: 1920x1200
        screen_geometry = QRect(0, 0, 1920, 1200)

        # Create and show overlay with explicit screen dimensions
        self.overlay = Overlay(screen_rect=screen_geometry)
        self.overlay.show()

        # Get collision map and print dimensions for debugging
        collision_map = screen_read.get_collision_map()
        rgba_image = screen_read.bool_mask_to_rgba(collision_map)
        print(f"Overlay size: {screen_geometry.width()}x{screen_geometry.height()}")
        print(f"Image size: {rgba_image.shape[1]}x{rgba_image.shape[0]}")

        color_image = screen_read.screenshot_to_numpy()
        self.overlay.set_images([(color_image, 0, 0)])

        # Start event loop
        exit_code = self.qt_app.exec()

        # Cleanup after event loop exits
        if self.keyboard_listener:
            self.keyboard_listener.stop()

        sys.exit(exit_code)

    def _handle_sigint(self, signum, frame):
        """Handle Ctrl+C signal"""
        print("\nCtrl+C detected - shutting down...")
        self.signal_handler.shutdown_requested.emit()


def main():
    app = App()
    app.start()


if __name__ == "__main__":
    main()
