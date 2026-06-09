# Live Transcription Overlay & Context-Aware Listening

Two powerful new debugging and productivity features for Jarvis MK3.

---

## 🎤 Live Transcription Overlay

### What It Does
Shows **real-time transcription** of what Jarvis is hearing and understanding on a floating overlay window. Perfect for debugging why voice commands aren't being recognized.

### Features
- **Real-time transcription display** - See exactly what's being transcribed as it happens
- **Input vs Output differentiation** - User input in blue, Jarvis responses in green  
- **Confidence scores** - Shows how confident the recognition is
- **Event history** - Keeps a buffer of recent transcriptions
- **Always-on-top** - Overlay stays visible over other windows
- **Debug mode** - Enhanced display with detailed information

### Voice Commands

#### Enable Overlay
```
"Show transcription overlay"
"Enable transcription display"
"Show what you're hearing"
```

#### Disable Overlay
```
"Hide transcription"
"Disable transcription overlay"
```

#### Toggle Overlay
```
"Toggle transcription"
```

#### Enable Debug Mode
```
"Enable debug mode"
"Start debug transcription"
```

#### Disable Debug Mode
```
"Disable debug mode"
"Stop debug mode"
```

#### Check Status
```
"Show listening status"
"What's the transcription status"
```

#### Clear History
```
"Clear transcription history"
```

### Programmatic Usage

```python
from actions.transcription_control import (
    enable_transcription_overlay,
    disable_transcription_overlay,
    enable_debug_mode,
    show_listening_status
)

# Enable the overlay
enable_transcription_overlay()

# Enable debug mode
enable_debug_mode()

# Show current status
show_listening_status()
```

---

## 📍 Context-Aware Listening Optimization

### What It Does
Automatically detects which application is focused and **optimizes listening behavior** accordingly. 

- **During gaming**: Reduces sensitivity to filter out game sounds
- **During video playback**: Minimizes audio pickup from movies/streams
- **During video calls**: Pauses listening to avoid interrupting meetings
- **During focus mode**: Significantly reduces listening to respect your flow
- **During coding**: Normal listening mode
- **General use**: Optimized for command recognition

### How It Works

The context manager monitors:
1. **Focused window/application**
2. **Process name and title**
3. **Application type detection** using pattern matching

### Supported Contexts

| Context | Listening | Sensitivity | Background Filter | When Detected |
|---------|-----------|-------------|-------------------|---------------|
| **General** | ✅ Full | 100% | No | Default |
| **Gaming** | ⚠️ Reduced | 30% | Yes | Game/Steam window |
| **Movie/Video** | ⚠️ Very Low | 20% | Yes | YouTube, Netflix, Twitch |
| **Video Call** | ❌ Paused | 0% | Yes | Zoom, Teams, Discord |
| **Music Player** | ⚠️ Reduced | 40% | Yes | Spotify, Apple Music |
| **IDE/Code Editor** | ✅ Normal | 100% | No | VS Code, PyCharm |
| **Focus Mode** | ❌ Paused | 20% | Yes | Focus app detected |
| **Web Browser** | ✅ Slightly Reduced | 90% | No | Chrome, Firefox, Edge |

### Detected Applications

The system automatically recognizes:

**Games:**
- Steam, Epic Games, Unreal, Unity, Godot
- Specific titles: Call of Duty, Elden Ring, Baldur's Gate, Minecraft, Valorant, Fortnite, Cyberpunk, Starfield, Palworld

**Video Streaming:**
- YouTube, Netflix, Twitch, TikTok, Plex, VLC, Kodi

**IDEs/Editors:**
- VS Code, PyCharm, IntelliJ, Sublime, Vim

**Communication:**
- Zoom, Microsoft Teams, Discord, Skype, Google Meet, Webex, OBS Studio

**Music Players:**
- Spotify, Apple Music, YouTube Music, Tidal, SoundCloud

**Focus/Productivity Apps:**
- Focus, Pomodoro timers, DeepWork, Freedom, Cold Turkey, LeechBlock

### Viewing Context Information

Check the current listening context through:

```python
from actions.audio_context import AudioContextManager

mgr = AudioContextManager()
context_info = mgr.get_current_context()

print(f"Context: {context_info.context}")
print(f"Window: {context_info.window_title}")
print(f"Should Listen: {context_info.should_listen}")
print(f"Sensitivity: {context_info.sensitivity_multiplier}")
```

Or use the voice command:
```
"Show listening status"
```

---

## 🔧 Technical Details

### New Files Created

1. **`actions/audio_context.py`** - Context detection and optimization
   - `AudioContextManager` - Main context detection class
   - `AppContext` - Enum for context types
   - `AudioContextInfo` - Data class for context information

2. **`actions/transcription_overlay.py`** - Overlay UI and display
   - `TranscriptionOverlay` - PyQt6 floating window
   - `TranscriptionBuffer` - Event history management
   - `TranscriptionManager` - Global manager
   - `TranscriptionEvent` - Event data structure

3. **`actions/transcription_control.py`** - Voice control functions
   - `toggle_transcription_display()`
   - `enable_transcription_overlay()`
   - `disable_transcription_overlay()`
   - `enable_debug_mode()`
   - `disable_debug_mode()`
   - `show_listening_status()`
   - `clear_transcription_history()`

### Integration Points in main.py

- **Initialization**: `JarvisLive.__init__()` creates context manager and overlay
- **Audio listening**: `_listen_audio()` respects context sensitivity settings
- **Transcription updates**: `_receive_audio()` sends transcriptions to overlay
- **Tool handling**: `_execute_tool()` processes transcription control commands

### Architecture

```
Audio Input
    ↓
[Audio Context Manager] ← Monitors focused app/game
    ↓
[Sensitivity Filter] ← Adjusts listening based on context
    ↓
[Gemini Real-time Model] ← Transcription
    ↓
[Transcription Overlay] ← Displays in real-time
    ↓
[UI Log & Processing]
```

---

## 🎯 Use Cases

### Debugging Command Recognition Issues

1. **Enable the transcription overlay:**
   ```
   "Show transcription overlay"
   ```

2. **Look at the real-time transcription** to see what Jarvis is actually hearing

3. **Check context sensitivity** with:
   ```
   "Show listening status"
   ```

4. **Enable debug mode** for detailed info:
   ```
   "Enable debug mode"
   ```

### Improving Gaming Experience

The system automatically reduces listening sensitivity during gaming, so:
- Game sounds don't trigger false commands
- Voice commands still work when needed
- Return to normal listening when you exit the game

### Respecting Focus Time

During focus mode apps, listening is paused:
- Deep work is uninterrupted
- Accidental commands won't interrupt flow
- Full listening resumes when focus ends

---

## 🛠️ Customization

### Adjust Sensitivity Thresholds

Edit `actions/audio_context.py` to modify sensitivity multipliers:

```python
optimizations = {
    AppContext.GAMING: (0.3, True),    # Change from 0.3 to 0.5 for higher sensitivity
    AppContext.MOVIE: (0.2, True),     # etc.
}
```

### Add New App Contexts

Add patterns to `AudioContextManager`:

```python
CUSTOM_PATTERNS = [
    r"(?i)(my app name|specific pattern)",
]
```

### Modify Overlay Appearance

Customize styling in `TranscriptionOverlay.setup_ui()`:
- Colors in the `setStyleSheet()` calls
- Window size: `self.setGeometry(100, 100, 400, 200)`
- Font sizes and families

---

## 📊 Performance

- **Minimal CPU impact**: Context detection runs once per second
- **Efficient overlay**: Uses Qt's event loop, doesn't block audio
- **Low memory**: Circular buffer limits history size
- **Thread-safe**: All components use proper locking

---

## 🐛 Troubleshooting

### Overlay doesn't appear
- Check that PyQt6 is installed: `pip install pyqt6`
- Verify the overlay thread started in console logs
- Try enabling debug mode: `"Enable debug mode"`

### Commands not recognized during gaming
- This is intentional - sensitivity is reduced to filter game sounds
- You can still give commands; they might need to be louder/clearer
- Adjust sensitivity multiplier in `audio_context.py` if needed

### Transcription delay
- Normal 1-2 second delay due to buffering
- Increase overlay update frequency if needed (modify `update_display()`)

### Context not detecting your app
- Add the app name/pattern to the appropriate pattern list
- Use `"Show listening status"` to verify current context

---

## 🚀 Future Enhancements

Potential improvements:
- Machine learning to learn your listening preferences per app
- Custom user-defined contexts
- Transcription history export (CSV, TXT)
- Voice pattern recognition for command confidence
- Integration with focus time tracking apps
- Network-based transcription logging

