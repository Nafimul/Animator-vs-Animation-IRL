from gemini import get_snarky_comment
from speech import text_to_speech_stream
import time

if __name__ == "__main__":
    print("⏳ Starting comment generation and speech...")
    start_time = time.time()

    # Get the comment from Gemini
    comment = get_snarky_comment()
    gemini_time = time.time() - start_time
    print(f"\n🤖 Gemini says: {comment}")
    print(f"⏱️  Gemini took: {gemini_time:.2f}s")

    # Generate speech immediately with the comment
    speech_start = time.time()
    audio_stream = text_to_speech_stream(comment)
    speech_time = time.time() - speech_start
    print(f"🎤 Speech generated in: {speech_time:.2f}s")

    total_time = time.time() - start_time
    print(f"✅ Total time: {total_time:.2f}s")

    # Play the audio
    try:
        import pygame

        pygame.mixer.init()
        pygame.mixer.music.load(audio_stream)
        pygame.mixer.music.play()

        # Wait for audio to finish
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
    except ImportError:
        print(
            "⚠️  pygame not installed - audio not played. Install with: pip install pygame"
        )
    except Exception as e:
        print(f"Error playing audio: {e}")
