import time
from pygame import mixer
import config


def play_sound(filepath: str, wait=True):
    """Play a sound from the given filepath

    Args:
        filepath: Path to the sound file
        wait: If True, wait for the sound to finish playing before returning
    """
    try:
        # Get the correct path for assets (works in exe and dev)
        full_path = config.get_asset_path(filepath)

        # Initialize mixer if not already initialized
        if not mixer.get_init():
            mixer.init()

        # Load and play the sound
        sound = mixer.Sound(full_path)
        channel = sound.play()

        # Wait for the sound to finish if requested
        if wait and channel:
            while channel.get_busy():
                time.sleep(0.01)
    except Exception as e:
        print(f"Error playing sound {filepath}: {e}")


if __name__ == "__main__":
    play_sound("assets/sounds/punch.wav")
