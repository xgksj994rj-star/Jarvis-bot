import os
import subprocess
import platform
import time
import psutil
from pathlib import Path

_SYSTEM = platform.system()

def _widget_notify(player, widget_id: str, title: str, message: str, widget_type: str = "system"):
    if not player or not hasattr(player, "add_widget"):
        return
    snippet = "\n".join(message.splitlines()[:4])
    player.add_widget(widget_id, title, snippet, duration=12.0, widget_type=widget_type)


def system_control(action: str, player=None) -> str:
    """
    Controls system-level operations like shutdown, restart, sleep, lock, hibernate
    Actions: shutdown, restart, sleep, lock, hibernate
    """
    action = action.lower().strip()
    result = None

    if _SYSTEM == "Windows":
        if action == "shutdown":
            subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
            result = "System shutting down..."
        elif action == "restart":
            subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
            result = "System restarting..."
        elif action == "sleep":
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=True)
            result = "System going to sleep..."
        elif action == "lock":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
            result = "Screen locked..."
        elif action == "hibernate":
            subprocess.run(["shutdown", "/h"], check=True)
            result = "System hibernating..."

    elif _SYSTEM == "Darwin":  # macOS
        if action == "shutdown":
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
            result = "System shutting down..."
        elif action == "restart":
            subprocess.run(["sudo", "shutdown", "-r", "now"], check=True)
            result = "System restarting..."
        elif action == "sleep":
            subprocess.run(["pmset", "sleepnow"], check=True)
            result = "System going to sleep..."
        elif action == "lock":
            subprocess.run(["pmset", "displaysleepnow"], check=True)
            result = "Screen locked..."

    elif _SYSTEM == "Linux":
        if action == "shutdown":
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
            result = "System shutting down..."
        elif action == "restart":
            subprocess.run(["sudo", "shutdown", "-r", "now"], check=True)
            result = "System restarting..."
        elif action == "sleep":
            subprocess.run(["systemctl", "suspend"], check=True)
            result = "System going to sleep..."

    if result is None:
        result = f"Unsupported action '{action}' on {_SYSTEM}"

    _widget_notify(player, "system_control", "System Control", result, widget_type="system")
    return result

def volume_control(action: str, level: int = None, player=None) -> str:
    """
    Controls system volume.
    Actions: up, down, mute, unmute, set
    Level: 0-100 for set action
    """
    action = action.lower().strip()
    result = f"Unsupported volume action '{action}' on {_SYSTEM}"

    if _SYSTEM == "Windows":
        if action == "up":
            subprocess.run(["nircmd.exe", "changesysvolume", "2000"], check=True)
            result = "Volume increased"
        elif action == "down":
            subprocess.run(["nircmd.exe", "changesysvolume", "-2000"], check=True)
            result = "Volume decreased"
        elif action == "mute":
            subprocess.run(["nircmd.exe", "mutesysvolume", "1"], check=True)
            result = "Volume muted"
        elif action == "unmute":
            subprocess.run(["nircmd.exe", "mutesysvolume", "0"], check=True)
            result = "Volume unmuted"
        elif action == "set" and level is not None:
            vol = int((level / 100) * 65535)
            subprocess.run(["nircmd.exe", "setsysvolume", str(vol)], check=True)
            result = f"Volume set to {level}%"

    elif _SYSTEM == "Darwin":
        if action == "up":
            subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) + 10)"], check=True)
            result = "Volume increased"
        elif action == "down":
            subprocess.run(["osascript", "-e", "set volume output volume (output volume of (get volume settings) - 10)"], check=True)
            result = "Volume decreased"
        elif action == "mute":
            subprocess.run(["osascript", "-e", "set volume output muted true"], check=True)
            result = "Volume muted"
        elif action == "unmute":
            subprocess.run(["osascript", "-e", "set volume output muted false"], check=True)
            result = "Volume unmuted"
        elif action == "set" and level is not None:
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"], check=True)
            result = f"Volume set to {level}%"

    elif _SYSTEM == "Linux":
        if action in ["up", "down", "mute", "unmute"]:
            cmd = {
                "up": ["amixer", "set", "Master", "5%+"],
                "down": ["amixer", "set", "Master", "5%-"],
                "mute": ["amixer", "set", "Master", "mute"],
                "unmute": ["amixer", "set", "Master", "unmute"]
            }[action]
            subprocess.run(cmd, check=True)
            result = f"Volume {action}"
        elif action == "set" and level is not None:
            subprocess.run(["amixer", "set", "Master", f"{level}%"], check=True)
            result = f"Volume set to {level}%"

    _widget_notify(player, "volume_control", "Volume", result, widget_type="status")
    return result

def process_manager(action: str, process_name: str = None, pid: int = None, player=None) -> str:
    """
    Manages system processes.
    Actions: list, kill, start, monitor
    """
    action = action.lower().strip()
    result = None

    if action == "list":
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(f"{proc.info['pid']}: {proc.info['name']} (CPU: {proc.info['cpu_percent']}%, MEM: {proc.info['memory_percent']}%)")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        result = "\n".join(processes[:20])  # Limit to 20 processes

    elif action == "kill":
        if pid:
            try:
                psutil.Process(pid).terminate()
                result = f"Terminated process {pid}"
            except psutil.NoSuchProcess:
                result = f"Process {pid} not found"
        elif process_name:
            killed = []
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if process_name.lower() in proc.info['name'].lower():
                        proc.terminate()
                        killed.append(f"{proc.info['pid']}: {proc.info['name']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            result = f"Killed processes: {', '.join(killed)}" if killed else f"No processes found matching '{process_name}'"

    elif action == "start" and process_name:
        try:
            subprocess.Popen(process_name)
            result = f"Started {process_name}"
        except Exception as e:
            result = f"Failed to start {process_name}: {e}"

    if result is None:
        result = f"Unsupported process action '{action}'"

    if player and hasattr(player, "add_widget"):
        snippet = "\n".join(result.splitlines()[:4])
        player.add_widget("process_manager", "Process Manager", snippet, duration=12.0, widget_type="status")

    return result