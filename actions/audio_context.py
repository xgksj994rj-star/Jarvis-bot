"""
Audio Context Manager - Detects focused app/game and optimizes listening behavior.
Provides context awareness for audio processing.
"""

import json
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable
from enum import Enum

try:
    import pygetwindow as gw
    import win32gui
    import win32process
except ImportError:
    gw = None
    win32gui = None
    win32process = None


class AppContext(Enum):
    """Application context types for audio optimization."""
    GENERAL = "general"           # Normal listening
    GAMING = "gaming"              # Game focused - reduce sensitivity
    MOVIE = "movie"                # Video playback - reduce audio pickup
    CODING = "coding"              # IDE/editor - normal listening
    MUSIC = "music"                # Music app - filter background
    BROWSER = "browser"            # Web browser - normal listening
    MEETING = "meeting"            # Video call - don't interrupt
    FOCUS_APP = "focus"            # Focus mode app - reduced listening


@dataclass
class AudioContextInfo:
    """Information about current audio context."""
    context: AppContext
    window_title: str
    process_name: str
    should_listen: bool
    sensitivity_multiplier: float  # 0.0-1.0, 1.0 = normal
    filter_background_noise: bool
    description: str


class AudioContextManager:
    """
    Detects and manages audio context based on focused application.
    Provides optimization hints for audio processing.
    """

    # Game window patterns (regex)
    GAME_PATTERNS = [
        r"(?i)(game|steam|epic|unreal|unity|godot)",
        r"(?i)(call of duty|elden ring|baldur's gate|minecraft|valorant|fortnite|cyberpunk|starfield|palworld)",
    ]

    # Video/Movie patterns
    VIDEO_PATTERNS = [
        r"(?i)(youtube|netflix|twitch|tiktok|plex|vlc|media player|kodi)",
        r"(?i)(movie|film|video player|streaming)",
    ]

    # IDE/Coding patterns
    IDE_PATTERNS = [
        r"(?i)(visual studio code|vscode|pycharm|intellij|rider|sublime|notepad\+\+|vim)",
        r"(?i)(code|editor|ide|programming)",
    ]

    # Music app patterns
    MUSIC_PATTERNS = [
        r"(?i)(spotify|apple music|youtube music|tidal|soundcloud|winamp|aimp)",
        r"(?i)(music player|audio player)",
    ]

    # Video call patterns
    MEETING_PATTERNS = [
        r"(?i)(zoom|teams|discord|skype|google meet|webex|hangouts|obs studio)",
        r"(?i)(meeting|conference|call|stream)",
    ]

    # Focus mode patterns
    FOCUS_PATTERNS = [
        r"(?i)(focus|pomodoro|deepwork|freedom|cold turkey|leechblock)",
    ]

    # Browser patterns
    BROWSER_PATTERNS = [
        r"(?i)(chrome|firefox|edge|safari|opera|brave|vivaldi)",
        r"(?i)(browser)",
    ]

    def __init__(self, update_callback: Optional[Callable[[AudioContextInfo], None]] = None):
        self.update_callback = update_callback
        self._last_context = None
        self._lock = threading.Lock()
        self._monitoring = False
        self._override_file = Path(__file__).resolve().parent.parent / "config" / "audio_context_overrides.json"
        self._overrides = self._load_overrides()

    def get_focused_window(self) -> tuple[Optional[str], Optional[str]]:
        """
        Returns (window_title, process_name) of focused window.
        Returns (None, None) if unable to get.
        """
        if not gw or not win32gui:
            return None, None

        try:
            # Get focused window
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None, None

            # Get window title
            window_title = win32gui.GetWindowText(hwnd)

            # Get process name
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                import psutil
                process_name = psutil.Process(pid).name()
            except Exception:
                process_name = "unknown"

            return window_title, process_name
        except Exception as e:
            print(f"[AudioContext] ❌ Error getting window: {e}")
            return None, None

    def _load_overrides(self) -> list[dict]:
        self._override_file.parent.mkdir(parents=True, exist_ok=True)
        if not self._override_file.exists():
            self._override_file.write_text(json.dumps({"overrides": []}, indent=2), encoding="utf-8")

        try:
            data = json.loads(self._override_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            overrides = data.get("overrides", [])
            if isinstance(overrides, list):
                return overrides
        except Exception as e:
            print(f"[AudioContext] ❌ Failed loading overrides: {e}")
        return []

    def save_overrides(self, overrides: list[dict]) -> None:
        try:
            data = {"overrides": overrides}
            self._override_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self._overrides = overrides
        except Exception as e:
            print(f"[AudioContext] ❌ Failed saving overrides: {e}")

    def get_overrides(self) -> list[dict]:
        return list(self._overrides)

    def _find_override(self, combined: str) -> Optional[dict]:
        for override in self._overrides:
            pattern = override.get("pattern", "")
            if not pattern:
                continue
            try:
                if re.search(pattern, combined, re.IGNORECASE):
                    return override
            except re.error:
                continue
        return None

    def _classify_context(self, window_title: str, process_name: str) -> tuple[AppContext, str]:

        """
        Classify audio context based on window title and process name.
        Returns (AppContext, description).
        """
        combined = f"{window_title} {process_name}".lower()

        # Check patterns in order of priority
        checks = [
            (self.GAME_PATTERNS, AppContext.GAMING, "Gaming detected"),
            (self.VIDEO_PATTERNS, AppContext.MOVIE, "Video playback detected"),
            (self.MEETING_PATTERNS, AppContext.MEETING, "Video call/meeting detected"),
            (self.MUSIC_PATTERNS, AppContext.MUSIC, "Music player detected"),
            (self.IDE_PATTERNS, AppContext.CODING, "IDE/Code editor detected"),
            (self.FOCUS_PATTERNS, AppContext.FOCUS_APP, "Focus mode detected"),
            (self.BROWSER_PATTERNS, AppContext.BROWSER, "Web browser detected"),
        ]

        for patterns, context, desc in checks:
            for pattern in patterns:
                if re.search(pattern, combined):
                    return context, desc

        return AppContext.GENERAL, "General context"

    def _get_optimization_params(self, context: AppContext) -> tuple[float, bool]:
        """
        Get audio optimization parameters for context.
        Returns (sensitivity_multiplier, filter_background_noise).
        """
        optimizations = {
            AppContext.GENERAL: (1.0, False),
            AppContext.GAMING: (0.3, True),          # Reduce sensitivity, filter noise
            AppContext.MOVIE: (0.2, True),           # Very quiet, filter heavily
            AppContext.CODING: (1.0, False),         # Normal
            AppContext.MUSIC: (0.4, True),           # Reduced, filter noise
            AppContext.BROWSER: (0.9, False),        # Slightly reduced
            AppContext.MEETING: (0.0, True),         # Don't listen during calls
            AppContext.FOCUS_APP: (0.2, True),       # Very quiet, focus uninterrupted
        }
        return optimizations.get(context, (1.0, False))

    def get_current_context(self) -> AudioContextInfo:
        """Get current audio context information."""
        with self._lock:
            window_title, process_name = self.get_focused_window()

            if not window_title or not process_name:
                window_title = window_title or "Unknown"
                process_name = process_name or "unknown"

            combined = f"{window_title} {process_name}".lower()
            override = self._find_override(combined)
            if override:
                context = AppContext.GENERAL
                desc = override.get("description", "Override context detected")
                override_context = override.get("context")
                if override_context:
                    try:
                        context = AppContext(override_context)
                    except ValueError:
                        pass
            else:
                context, desc = self._classify_context(window_title, process_name)

            sensitivity, filter_noise = self._get_optimization_params(context)
            if override:
                sensitivity = override.get("sensitivity_multiplier", sensitivity)
                filter_noise = override.get("filter_background_noise", filter_noise)

            # Determine if we should listen
            should_listen = context not in [
                AppContext.MEETING,   # Don't interrupt meetings
                AppContext.GAMING,    # Don't interrupt games unless Jarvis is explicitly invoked
                AppContext.FOCUS_APP, # Don't interrupt focus mode (can be overridden)
            ]
            if override:
                action = str(override.get("action", "")).strip().lower()
                if action == "blacklist":
                    should_listen = False
                elif action == "whitelist":
                    should_listen = True
                else:
                    should_listen = override.get("should_listen", should_listen)

            info = AudioContextInfo(
                context=context,
                window_title=window_title,
                process_name=process_name,
                should_listen=should_listen,
                sensitivity_multiplier=sensitivity,
                filter_background_noise=filter_noise,
                description=desc,
            )

            # Trigger callback if context changed
            if (
                self._last_context is None or
                self._last_context.context != info.context or
                self._last_context.window_title != info.window_title
            ):
                self._last_context = info
                if self.update_callback:
                    self.update_callback(info)

            return info

    def start_monitoring(self, interval: float = 1.0):
        """Start background monitoring of audio context."""
        if self._monitoring:
            return

        self._monitoring = True

        def monitor_loop():
            while self._monitoring:
                try:
                    self.get_current_context()
                except Exception as e:
                    print(f"[AudioContext] ❌ Monitor error: {e}")
                time.sleep(interval)

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()

    def stop_monitoring(self):
        """Stop background monitoring."""
        self._monitoring = False

    def is_game_mode(self) -> bool:
        """Quick check if in game mode."""
        return self.get_current_context().context == AppContext.GAMING

    def is_meeting_mode(self) -> bool:
        """Quick check if in meeting/call mode."""
        return self.get_current_context().context == AppContext.MEETING

    def should_listen(self) -> bool:
        """Check if we should be listening based on context."""
        return self.get_current_context().should_listen

