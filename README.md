# Animator-vs-Animation-IRL

A 24 hour hackathon project where a stickman is put on a transparent window on top of the screen and can collide with objects that are on your screen like apps and windows. This is done by converting the pixels on the screen to a collision map: pixels similar to the most common background color are background while other pixels are objects that can be collided with. The stickman can punch things which causes the mouse to move there, click it and move back very fast. Every once in a while, the Google Gemini API makes a snarky comment about a screenshot of the screen. This comment is read aloud by ElevenLabs. The collision map refreshes at 20fps.

## Features
- Stickman walks, jumps, flies, and interacts with screen elements
- Voice-controlled Kamehameha attack ("Hame" detection)
- AI-powered snarky comments via Google Gemini
- Text-to-speech via ElevenLabs
- Real-time collision detection with screen pixels

## Installation

### For Users (Running the .exe)
1. Download the `.exe` file from the releases
2. Run `AnimatorVsAnimationIRL.exe`
3. That's it! Everything is bundled inside.

### For Developers
1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your API keys:
   ```
   ELEVENLABS_API_KEY=your_key_here
   GOOGLE_API_KEY=your_key_here
   ```
4. Run the application:
   ```bash
   python App.py
   ```

## Building the Executable
See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) for detailed instructions on creating a standalone .exe file.

Quick build:
```bash
python build_exe.py
```

## Controls
- `J` - Move left
- `L` - Move right
- `I` - Jump / Move up (when flying)
- `K` - Move down (when flying)
- `S` - Punch
- `E` - Toggle flying mode
- `D` - Turn off flying
- `R` - Kamehameha attack
- `A` - Teleport to mouse cursor
- `G` - Re-detect background color
- Say "Hame" - Trigger Kamehameha
- Loud sound - Toggle flying

## Credits
Stickman animation based off of the one by Angelina at https://www.pngitem.com/middle/ThbJJm_stickman-fight-sprite-sheet-hd-png-download/

Walking sound effect by freesound_community at https://pixabay.com/users/freesound_community-46691455/ on Pixabay

Fire Crackling Sounds sound effect by DRAGON-STUDIO at https://pixabay.com/sound-effects/nature-fire-crackling-sounds-427410/ on Pixabay
