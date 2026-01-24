from overlay import Overlay
import screen_read
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRect, Qt
import os
import signal
from pynput import keyboard

from stickman import Stickman


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
        self.stickman = None

    def stuff_i_understand(self):
        screen_geometry = QRect(0, 0, 1920, 1200)

        # Create and show overlay with explicit screen dimensions
        self.overlay = Overlay(screen_rect=screen_geometry)
        self.overlay.show()

        self.stickman = Stickman()
        # Set up collision map provider so stickman can update it at 20fps
        self.stickman.collision_map_provider = screen_read.get_collision_map

        # Set up 60 FPS update timer for stickman
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_game)
        self.update_timer.start(16)  # ~60 FPS (1000ms / 60 = 16.67ms)

    def update_game(self):
        """Called at 60 FPS to update game state and refresh display"""
        if self.stickman:
            # Update stickman physics (collision map updated at 20fps internally)
            self.stickman.update()

            images = []

            # if (self.stickman.collision_map is not None):
            #     images.append(
            #         (screen_read.bool_mask_to_rgba(self.stickman.collision_map),
            #         int(self.stickman.collision_map_x),
            #         int(self.stickman.collision_map_y))
            #     )

            # Tuple format: (image, x, y, flip_horizontal)
            images.append(
                (
                    self.stickman.sprite_url,
                    int(self.stickman.pos[0]),
                    int(self.stickman.pos[1]),
                    not self.stickman.facing_right,  # Flip when facing left
                )
            )

            # Update overlay with new stickman position
            self.overlay.set_images(images)

    def start(self):
        """Start the application with global hotkey listener"""
        # Set up global keyboard listener (works regardless of focus)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_press)
        self.keyboard_listener.start()

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

        self.stuff_i_understand()

        # Start event loop
        exit_code = self.qt_app.exec()

        # Cleanup after event loop exits
        if self.keyboard_listener:
            self.keyboard_listener.stop()

        sys.exit(exit_code)

    def on_press(self, key):
        """Global keyboard listener - handles exit only"""
        try:
            if hasattr(key, "char") and key.char:
                char = key.char.lower()

                if char == "z":
                    print("\nZ key pressed - shutting down...")
                    self.signal_handler.shutdown_requested.emit()
        except AttributeError:
            pass

    def shutdown(self):
        """Thread-safe shutdown - must be called from Qt main thread"""
        self.running = False
        print("Shutting down...")

        # Stop stickman keyboard listener
        if self.stickman:
            try:
                self.stickman.stop_keyboard_listener()
            except:
                pass

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

        # Stop update timer
        if hasattr(self, "update_timer") and self.update_timer:
            try:
                self.update_timer.stop()
            except:
                pass

        # Quit the QApplication
        if self.qt_app:
            self.qt_app.quit()

        print("Program terminated.")

    def _handle_sigint(self, signum, frame):
        """Handle Ctrl+C signal"""
        print("\nCtrl+C detected - shutting down...")
        self.signal_handler.shutdown_requested.emit()


def main():
    app = App()
    app.start()


if __name__ == "__main__":
    main()
