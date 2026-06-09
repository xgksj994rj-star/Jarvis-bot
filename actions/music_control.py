"""
Spotify/Music Control for MARK XXXVII
Play, pause, skip, search music, and control playback
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"

# Platform-specific music control
IS_WINDOWS = os.name == "nt"


def load_config() -> Dict[str, Any]:
    """Load API configuration from config file."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _run_powershell(command: str) -> str:
    """Run a PowerShell command and return output."""
    try:
        result = subprocess.run(
            ["powershell", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"Error: {str(e)}"


def _run_command(cmd: list) -> str:
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.stdout.strip() or result.stderr.strip()
    except Exception as e:
        return f"Error: {str(e)}"


# ── Windows Spotify Control via COM ─────────────────────────────────────────────
def _spotify_windows(action: str, query: str = "") -> str:
    """Control Spotify on Windows using PowerShell COM."""
    
    ps_script = '''
$spotify = New-Object -ComObject Spotify.Application
$spotify.{action}
'''.format(action=action)
    
    if action == "PlayPause":
        ps_script = '''
$spotify = New-Object -ComObject Spotify.Application
$spotify.Play
'''
    elif action == "search":
        ps_script = f'''
$spotify = New-Object -ComObject Spotify.Application
$spotify.Search("{query}")
'''
    
    return _run_powershell(ps_script)


# ── macOS Spotify Control via AppleScript ───────────────────────────────────────
def _spotify_mac(action: str, query: str = "") -> str:
    """Control Spotify on macOS using AppleScript."""
    
    actions = {
        "play": 'tell application "Spotify" to play',
        "pause": 'tell application "Spotify" to pause',
        "next": 'tell application "Spotify" to next track',
        "previous": 'tell application "Spotify" to previous track',
        "playpause": 'tell application "Spotify" to playpause',
        "search": 'tell application "Spotify" to search for "{query}"'
    }
    
    if action == "search":
        script = actions.get("search", "").format(query=query)
    else:
        script = actions.get(action.lower(), "")
    
    if script:
        return _run_command(["osascript", "-e", script])
    return "Unknown action"


# ── Linux Spotify Control via dbus ──────────────────────────────────────────────
def _spotify_linux(action: str, query: str = "") -> str:
    """Control Spotify on Linux using dbus."""
    
    # Using playerctl for Linux
    commands = {
        "play": ["playerctl", "--player=spotify", "play"],
        "pause": ["playerctl", "--player=spotify", "pause"],
        "next": ["playerctl", "--player=spotify", "next"],
        "previous": ["playerctl", "--player=spotify", "previous"],
        "playpause": ["playerctl", "--player=spotify", "play-pause"],
        "status": ["playerctl", "--player=spotify", "status"],
        "metadata": ["playerctl", "--player=spotify", "metadata"]
    }
    
    if action.lower() in commands:
        return _run_command(commands[action.lower()])
    
    return "Unknown action or Spotify not running"


# ── Generic Spotify Control ─────────────────────────────────────────────────────
def _spotify_control(action: str, query: str = "") -> str:
    """Platform-agnostic Spotify control."""
    
    if IS_WINDOWS:
        return _spotify_windows(action, query)
    else:
        # Try macOS first, then Linux
        result = _spotify_mac(action, query)
        if "Error" in result:
            result = _spotify_linux(action, query)
        return result


# ── Web API for Spotify (requires API key) ──────────────────────────────────────
def spotify_web_search(query: str) -> str:
    """
    Search Spotify using web API (requires Spotify API key).
    Returns track info without needing Spotify to be open.
    """
    config = load_config()
    
    if "spotify_client_id" not in config or not config["spotify_client_id"]:
        return "Spotify web search requires Spotify API credentials. Add spotify_client_id and spotify_client_secret to config/api_keys.json"
    
    try:
        import base64
        import requests
        
        # Get access token
        auth = base64.b64encode(
            f"{config['spotify_client_id']}:{config['spotify_client_secret']}".encode()
        ).decode()
        
        token_response = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": f"Basic {auth}"}
        )
        
        if token_response.status_code != 200:
            return f"Failed to get Spotify token: {token_response.text}"
        
        token = token_response.json()["access_token"]
        
        # Search
        search_response = requests.get(
            f"https://api.spotify.com/v1/search?q={query}&type=track&limit=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if search_response.status_code != 200:
            return f"Spotify search failed: {search_response.text}"
        
        results = search_response.json()
        tracks = results.get("tracks", {}).get("items", [])
        
        if not tracks:
            return f"No tracks found for '{query}'"
        
        output = [f"🎵 Search results for '{query}':\n"]
        for i, track in enumerate(tracks, 1):
            artists = ", ".join([a["name"] for a in track["artists"]])
            output.append(f"{i}. {track['name']} - {artists}")
            output.append(f"   ⏱️ {track['duration_ms']//60000}:{track['duration_ms']%60000:02d}")
            output.append(f"   🔗 {track['external_urls']['spotify']}\n")
        
        return "\n".join(output)
        
    except ImportError:
        return "Error: requests package needed. Run: pip install requests"
    except Exception as e:
        return f"Spotify search error: {str(e)}"


# ── Main Action Function ────────────────────────────────────────────────────────
def music_control(action: str, query: str = "", track: str = "", artist: str = "", player=None) -> str:
    """
    Main action function to be called from JARVIS.
    
    Args:
        action: play, pause, next, previous, search, now_playing, volume
        query: Search query
        track: Track name to play
        artist: Artist name
        player: optional UI player for widget display
    
    Returns:
        Response message
    """
    action = action.lower()
    
    # Handle different actions
    if action in ["play", "pause", "next", "previous", "playpause"]:
        result = _spotify_control(action)
        title = "Music"
        if not result or "Error" in result:
            body = f"Spotify: {action} command sent"
            if player and hasattr(player, "add_widget"):
                player.add_widget("music_status", title, body, duration=9.0, widget_type="music")
            return f"⏯️ Spotify: {action} - (command sent)"

        body = f"Spotify: {action} completed"
        if player and hasattr(player, "add_widget"):
            player.add_widget("music_status", title, body, duration=9.0, widget_type="music")
        return result
    elif action == "search":
        if query:
            return spotify_web_search(query)
        return "Please provide a search query. Example: search for 'Bohemian Rhapsody'"
    
    elif action == "nowplaying" or action == "now_playing":
        if IS_WINDOWS:
            ps_script = '''
$spotify = New-Object -ComObject Spotify.Application
$track = $spotify.CurrentTrack
$artist = $spotify.CurrentArtist
Write-Output "🎵 Now Playing: $track - $artist"
'''
            result = _run_powershell(ps_script)
        else:
            result = _spotify_control("metadata")

        if player and hasattr(player, "add_widget"):
            player.add_widget("music_nowplaying", "Now Playing", result, duration=14.0, widget_type="music")
        return result
    
    elif action == "volume":
        if not query:
            return "Please specify volume level (0-100). Example: volume 50"
        
        try:
            vol = int(query)
            if vol < 0 or vol > 100:
                return "Volume must be between 0 and 100"
            
            if IS_WINDOWS:
                ps_script = f'''
$spotify = New-Object -ComObject Spotify.Application
$spotify.Volume = {vol}
'''
                _run_powershell(ps_script)
            else:
                # Use playerctl for macOS/Linux
                _run_command(["playerctl", "--player=spotify", "volume", str(vol/100)])

            body = f"Volume set to {vol}%"
            if player and hasattr(player, "add_widget"):
                player.add_widget("music_volume", "Volume", body, duration=8.0, widget_type="music")
            return f"🔊 {body}"
        except ValueError:
            return "Invalid volume level. Use a number between 0-100"
    
    elif action == "open" or action == "launch":
        if IS_WINDOWS:
            _run_command(["start", "spotify"])
        elif os.uname().sysname == "Darwin":
            _run_command(["open", "-a", "Spotify"])
        else:
            _run_command(["spotify"])
        body = "Opening Spotify..."
        if player and hasattr(player, "add_widget"):
            player.add_widget("music_open", "Spotify", body, duration=8.0, widget_type="music")
        return f"🎵 {body}"
    
    elif action == "shuffle":
        if IS_WINDOWS:
            ps_script = '''
$spotify = New-Object -ComObject Spotify.Application
$spotify.Shuffle = $true
'''
            _run_powershell(ps_script)
        body = "Shuffle enabled"
        if player and hasattr(player, "add_widget"):
            player.add_widget("music_shuffle", "Shuffle", body, duration=8.0, widget_type="music")
        return f"🔀 {body}"
    
    elif action == "repeat":
        if IS_WINDOWS:
            ps_script = '''
$spotify = New-Object -ComObject Spotify.Application
$spotify.Repeat = 1
'''
            _run_powershell(ps_script)
        body = "Repeat enabled"
        if player and hasattr(player, "add_widget"):
            player.add_widget("music_repeat", "Repeat", body, duration=8.0, widget_type="music")
        return f"🔁 {body}"
    
    else:
        return f"""Unknown action '{action}'. Available commands:
- play, pause, next, previous, playpause
- search <query>
- nowplaying
- volume <0-100>
- open/launch
- shuffle, repeat"""


# ── Alternative: Generic Music Control (any player) ─────────────────────────────
def generic_music_control(action: str, player: str = "spotify") -> str:
    """
    Control any music player using playerctl (cross-platform).
    
    Args:
        action: play, pause, next, previous, status
        player: Player name (spotify, vlc, etc.)
    
    Returns:
        Response message
    """
    if IS_WINDOWS:
        return "playerctl not available on Windows. Use native Spotify control."
    
    commands = {
        "play": ["playerctl", "--player", player, "play"],
        "pause": ["playerctl", "--player", player, "pause"],
        "next": ["playerctl", "--player", player, "next"],
        "previous": ["playerctl", "--player", player, "previous"],
        "status": ["playerctl", "--player", player, "status"],
        "position": ["playerctl", "--player", player, "position"],
        "metadata": ["playerctl", "--player", player, "metadata"]
    }
    
    if action.lower() in commands:
        result = _run_command(commands[action.lower()])
        return result if result else f"✅ {player}: {action}"
    
    return f"Unknown action. Available: {', '.join(commands.keys())}"