# BUILD_INSTRUCTIONS.md

## Building the Executable

Follow these steps to create a standalone .exe file that includes all dependencies and API keys:

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
Make sure your `.env` file exists with your API keys:
```
ELEVENLABS_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here
```

### 3. Build the Executable
Run the build script:
```bash
python build_exe.py
```

This will create a `dist` folder containing `AnimatorVsAnimationIRL.exe`.

### 4. Distribution
The `.exe` file in the `dist` folder includes:
- All Python dependencies
- All assets (sprites, sounds)
- API keys from your `.env` file
- Everything needed to run on any Windows PC

**Note**: The `.env` file is bundled inside the .exe, so anyone who has the .exe will have access to your API keys. For public distribution, consider implementing a different API key management strategy (e.g., requiring users to input their own keys).

### Alternative: Manual PyInstaller Build
If you prefer to customize the build, you can run PyInstaller directly:
```bash
pyinstaller App.py --name=AnimatorVsAnimationIRL --onefile --windowed --add-data="assets;assets" --add-data=".env;."
```

### Troubleshooting
- If the build fails, check that all dependencies are installed
- Make sure the `assets` folder exists and contains all sprites and sounds
- Verify your `.env` file is in the project root directory
- On first run, Windows Defender may scan the .exe (this is normal)
