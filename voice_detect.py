import numpy as np
import sounddevice as sd
import speech_recognition as sr
from difflib import SequenceMatcher


def detect_loud_sound(threshold=0.001, duration=0.5, sample_rate=44100):
    """
    Detect if sound from microphone exceeds a threshold.

    Args:
        threshold: Volume threshold (0.0 to 1.0), default 0.1
        duration: How long to listen in seconds, default 0.5
        sample_rate: Audio sample rate, default 44100 Hz

    Returns:
        True if sound exceeds threshold, False otherwise
    """
    try:
        # Record audio from microphone
        audio = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
        )
        sd.wait()  # Wait for recording to finish

        # Calculate RMS (root mean square) amplitude
        rms = np.sqrt(np.mean(audio**2))

        return rms > threshold
    except Exception as e:
        print(f"Error detecting loud sound: {e}")
        return False


def detect_word_hame(duration=2.0, similarity_threshold=0.6):
    """
    Detect if the word 'hame' (or similar) is spoken into the microphone.

    Args:
        duration: How long to listen in seconds, default 2.0
        similarity_threshold: How similar the word needs to be (0.0 to 1.0), default 0.6

    Returns:
        True if 'hame' or similar word is detected, False otherwise
    """
    try:
        recognizer = sr.Recognizer()

        # Use microphone as audio source
        with sr.Microphone() as source:
            # Adjust for ambient noise
            recognizer.adjust_for_ambient_noise(source, duration=0.5)

            # Listen for audio
            audio = recognizer.listen(
                source, timeout=duration, phrase_time_limit=duration
            )

        # Try to recognize speech
        try:
            text = recognizer.recognize_google(audio).lower()
            print(f"Recognized: {text}")

            # Check if any word in the recognized text is similar to "hame"
            words = text.split()
            target = "hame"

            for word in words:
                similarity = SequenceMatcher(None, word, target).ratio()
                if similarity >= similarity_threshold:
                    print(f"Match found: '{word}' (similarity: {similarity:.2f})")
                    return True

            return False

        except sr.UnknownValueError:
            # Speech not recognized
            return False
        except sr.RequestError as e:
            print(f"Speech recognition error: {e}")
            return False

    except Exception as e:
        print(f"Error detecting word: {e}")
        return False


if __name__ == "__main__":
    print("Testing loud sound detection...")
    if detect_loud_sound(threshold=0.001, duration=1.0):
        print("Loud sound detected!")
    else:
        print("No loud sound detected.")

    print("\nTesting 'hame' word detection...")
    print("Say something with 'hame' in it (like 'kame hame ha')...")
    if detect_word_hame(duration=3.0):
        print("'Hame' detected!")
    else:
        print("'Hame' not detected.")
