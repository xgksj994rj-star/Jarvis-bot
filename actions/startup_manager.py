"""
Startup Manager for MARK XXXVII
Add or remove Jarvis from Windows startup
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

# Base directory
BASE_DIR = Path(__file__).resolve().parent.parent
MAIN_SCRIPT = BASE_DIR / "main.py"


def _get_python_executable() -> str:
    """Get the Python executable path."""
    # Use current Python executable
    return sys.executable


def _get_startup_folder() -> Path:
    """Get the Windows startup folder path."""
    startup = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
    return Path(startup)


def _get_registry_path() -> str:
    """Get the registry path for startup apps."""
    return r"Software\Microsoft\Windows\CurrentVersion\Run"


def add_to_startup(method: str = "registry") -> str:
    """
    Add Jarvis to Windows startup.
    
    Args:
        method: "registry" (default) or "folder"
    
    Returns:
        Status message
    """
    if os.name != "nt":
        return "Startup configuration is only supported on Windows."
    
    python_exe = _get_python_executable()
    script_path = str(MAIN_SCRIPT)
    
    if method == "folder":
        # Add shortcut to startup folder
        startup_folder = _get_startup_folder()
        shortcut_path = startup_folder / "Jarvis-MK37.lnk"
        
        try:
            # Create a simple batch file as workaround (no COM needed)
            bat_path = startup_folder / "Jarvis-MK37.bat"
            with open(bat_path, "w") as f:
                f.write(f'@echo off\ncd /d "{BASE_DIR}"\nstart "" "{python_exe}" "{script_path}"\n')
            
            return f"✅ Added to startup folder: {bat_path}"
            
        except Exception as e:
            return f"❌ Failed to add to startup: {e}"
    
    else:
        # Add to registry (default method)
        try:
            import winreg
            
            key_path = _get_registry_path()
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            
            # Value: start python with the script minimized
            value = f'"{python_exe}" "{script_path}"'
            winreg.SetValueEx(key, "Jarvis-MK37", 0, winreg.REG_SZ, value)
            winreg.CloseKey(key)
            
            return "✅ Added to Windows startup (Registry)"
            
        except ImportError:
            return "❌ winreg not available. Try method='folder'"
        except Exception as e:
            return f"❌ Failed to add to registry: {e}"


def remove_from_startup(method: str = "registry") -> str:
    """
    Remove Jarvis from Windows startup.
    
    Args:
        method: "registry" (default) or "folder"
    
    Returns:
        Status message
    """
    if os.name != "nt":
        return "Startup configuration is only supported on Windows."
    
    if method == "folder":
        # Remove from startup folder
        startup_folder = _get_startup_folder()
        
        removed = []
        for file in ["Jarvis-MK37.bat", "Jarvis-MK37.lnk"]:
            path = startup_folder / file
            if path.exists():
                path.unlink()
                removed.append(file)
        
        if removed:
            return f"✅ Removed from startup folder: {', '.join(removed)}"
        return "ℹ️ No startup files found"
    
    else:
        # Remove from registry
        try:
            import winreg
            
            key_path = _get_registry_path()
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, "Jarvis-MK37")
            winreg.CloseKey(key)
            
            return "✅ Removed from Windows startup (Registry)"
            
        except FileNotFoundError:
            return "ℹ️ Not in startup registry"
        except Exception as e:
            return f"❌ Failed to remove: {e}"


def is_in_startup(method: str = "registry") -> bool:
    """
    Check if Jarvis is in startup.
    
    Args:
        method: "registry" or "folder"
    
    Returns:
        True if in startup
    """
    if os.name != "nt":
        return False
    
    if method == "folder":
        startup_folder = _get_startup_folder()
        return (startup_folder / "Jarvis-MK37.bat").exists() or (startup_folder / "Jarvis-MK37.lnk").exists()
    
    else:
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _get_registry_path(), 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, "Jarvis-MK37")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False


def get_startup_status() -> str:
    """Get current startup configuration status."""
    if os.name != "nt":
        return "Startup is only supported on Windows."
    
    in_registry = is_in_startup("registry")
    in_folder = is_in_startup("folder")
    
    status = ["📋 Startup Status:"]
    
    if in_registry:
        status.append("  ✅ Registry: Enabled")
    else:
        status.append("  ❌ Registry: Disabled")
    
    if in_folder:
        status.append("  ✅ Startup Folder: Enabled")
    else:
        status.append("  ❌ Startup Folder: Disabled")
    
    if not in_registry and not in_folder:
        status.append("\n💡 Run 'startup add' to enable auto-start")
    
    return "\n".join(status)


# ── Main Action Function ────────────────────────────────────────────────────────
def startup_action(action: str = "status", method: str = "registry") -> str:
    """
    Main action function to be called from JARVIS.
    
    Args:
        action: add, remove, status, enable, disable
        method: registry (default) or folder
    
    Returns:
        Response message
    """
    action = action.lower()
    
    if action in ["add", "enable", "on"]:
        return add_to_startup(method)
    
    elif action in ["remove", "disable", "off"]:
        return remove_from_startup(method)
    
    elif action in ["status", "check", "info"]:
        return get_startup_status()
    
    else:
        return """Unknown action. Available:
- add / enable: Add to startup
- remove / disable: Remove from startup
- status: Check current status

Use method='folder' if registry doesn't work."""


# ── Run directly for testing ───────────────────────────────────────────────────
if __name__ == "__main__":
    print(get_startup_status())
    print("\nAdding to startup...")
    print(add_to_startup())