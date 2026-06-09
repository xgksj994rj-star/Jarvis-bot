# Quick Start: Live Transcription & Context-Aware Listening

## 🚀 Getting Started in 30 Seconds

### Step 1: Enable the Overlay
Simply say:
```
"Show transcription overlay"
```

A floating window will appear showing **real-time transcription** of what Jarvis is hearing.

### Step 2: Check What's Being Heard
Look at the overlay window:
- **👤 You (Blue)**: What you just said
- **🤖 Jarvis (Green)**: What Jarvis is saying
- **Confidence**: How sure the recognition is

### Step 3: Debug Commands Not Working
If a command isn't recognized:
1. Say: `"Enable debug mode"`
2. Look at the overlay - you'll see exactly what's being transcribed
3. Try the command again and watch in real-time
4. Adjust volume or clarity based on what you see

---

## 📝 Voice Commands Reference

### Transcription Overlay Control
| Command | Does |
|---------|------|
| "Show transcription overlay" | Displays the transcription window |
| "Hide transcription" | Hides the transcription window |
| "Toggle transcription" | Shows/hides it |
| "Enable debug mode" | Shows detailed transcription info |
| "Disable debug mode" | Hides debug info |
| "Show listening status" | Reports current context and status |
| "Clear transcription history" | Erases the buffer |

### Context Awareness (Automatic)
The system **automatically adapts** listening based on what you're doing:

- **Gaming** 🎮 → Reduces sensitivity (doesn't pick up game sounds)
- **Watching videos** 🎬 → Very quiet listening
- **In a video call** 📞 → Pauses listening (respects your meeting)
- **Focus mode** 🎯 → Minimal listening (respects your deep work)
- **Normal use** 💼 → Full listening

No commands needed - it **just works**.

---

## 🎯 Debugging Workflow

### "Commands aren't being recognized"

1. **Enable the overlay:**
   ```
   "Show transcription overlay"
   ```

2. **Say your command slowly** and watch the overlay

3. **Check what appeared:**
   - If it shows your words correctly → Problem might be with command recognition
   - If it shows gibberish → Audio input issue (check microphone)
   - If it shows nothing → Check if you're in meeting/focus mode

4. **Enable debug to see details:**
   ```
   "Enable debug mode"
   ```

5. **Try again and look for:**
   - Confidence scores (should be 80%+)
   - Current context (should be "General" for normal use)
   - Sensitivity level (should be 1.0 for general use)

### "False commands triggering during gaming"

The system automatically reduces sensitivity during gaming.
- This is **intentional** for a better gaming experience
- Commands still work, just speak more clearly
- Sensitivity returns to normal when you exit the game

### "Transcription shows but doesn't work"

1. Check the current context:
   ```
   "Show listening status"
   ```

2. If it says "Context: Video Call" or "Focus Mode":
   - You're in a protected context
   - Return to normal mode to give commands
   - Or adjust settings if needed

---

## 💡 Pro Tips

### Tip 1: Keep it Hidden Until Needed
- Overlay can stay hidden during normal use
- Only show it when troubleshooting
- Shows/hides with: `"Toggle transcription"`

### Tip 2: Use Debug Mode for Training
- Enable debug mode while Jarvis learns your voice patterns
- Shows confidence scores for each word
- Helps identify which words are misheard

### Tip 3: Monitor Context Changes
- Say: `"Show listening status"` to see current context
- Useful if commands suddenly stop working
- Tells you if you're in a protected mode

### Tip 4: Clear History When Done
- Say: `"Clear transcription history"` to reset the buffer
- Useful for testing fresh without old transcriptions

---

## ⚙️ What's Happening Behind the Scenes

### Context Detection
```
Window Focus → App Recognition → Context Type → Listening Optimization
```

The system:
1. Detects which window/app is focused
2. Recognizes what type of app it is (game, video, etc.)
3. Sets listening sensitivity accordingly
4. Shows everything on the overlay for debugging

### Transcription Flow
```
Audio Input → Context Check → Audio Processing → Real-time Display
```

You see:
1. Raw input (what your mic picks up)
2. Context info (what app you're in)
3. Transcription (what Jarvis hears)
4. Confidence (how sure it is)

---

## 🔧 Customization

### Change Overlay Position
The overlay appears at coordinates (100, 100) by default.
To move it: Just drag the window with your mouse.

### Resize Overlay
The default size is 400×200 pixels. You can resize it by dragging edges.

### Disable for Certain Apps
Edit `actions/audio_context.py` and add your app to:
- `GAMING_PATTERNS` - for game sensitivity
- `VIDEO_PATTERNS` - for movie/stream sensitivity
- `MEETING_PATTERNS` - to pause listening

---

## 🆘 Troubleshooting

### "Overlay doesn't appear"
- Check: Is Jarvis running? (Check terminal window)
- Try: `"Enable debug mode"` first
- Check: PyQt6 installed? `pip install pyqt6`

### "Transcription is blank"
- Check: Microphone is unmuted
- Try: `"Show listening status"` to see context
- Possible: You're in a context that pauses listening (meeting/focus mode)

### "Sensitivity is too high during gaming"
- This is automatic and intentional
- Edit `audio_context.py` line with `AppContext.GAMING: (0.3, True)`
- Change `0.3` to `0.5` for higher sensitivity

### "Commands not working but transcription shows them"
- Problem is with command recognition, not hearing
- Try rephrasing the command
- Use more specific language

---

## 📊 What You Can Learn

By watching the transcription overlay, you can:

1. **Verify your mic works** - See if audio is being captured
2. **Understand command failures** - See what was actually heard
3. **Optimize your speech** - Learn which commands work best
4. **Debug audio issues** - Identify if problem is hearing or understanding
5. **Monitor context** - See what apps are being detected

---

## ✨ Example Workflows

### Debugging a Command
```
User: "Show transcription overlay"
[Overlay appears]

User: "Open Discord"
[Overlay shows: "👤 You: Opan Discordd"]
[No action taken - misrecognized]

User: [Speaking more clearly] "Open Discord"
[Overlay shows: "👤 You: Open Discord"]
[Discord opens successfully]
```

### Verifying Context Switching
```
User: "Show listening status"
Jarvis: "Context: General | Sensitivity: 100%"

[User launches Fortnite]
[Game window becomes focused]

User: "Show listening status"
Jarvis: "Context: Gaming | Sensitivity: 30%"

[Sensitivity reduced - good for gaming]
```

### Debug Mode Inspection
```
User: "Enable debug mode"

User: "What's the weather in New York"
[Overlay shows detailed breakdown of each word and confidence]
[You can see if any words were misheard]

User: "Disable debug mode"
```

---

## 📚 Learn More

For detailed information, see:
- **TRANSCRIPTION_AND_CONTEXT_GUIDE.md** - Complete documentation
- **actions/audio_context.py** - How context detection works
- **actions/transcription_overlay.py** - Overlay implementation

Happy debugging! 🎙️✨
