"""
Voice-Controlled System Actions
Control system operations through voice commands
"""

import os
import subprocess
import asyncio
import psutil
import sys
from typing import Dict, List, Optional, Any
import json

class VoiceSystemControl:
    """Handles voice-based system control operations"""
    
    def __init__(self):
        self.system_info = self._get_system_info()
        self.running_apps = {}
        self.update_running_apps()
    
    def _get_system_info(self) -> Dict:
        """Get current system information"""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "battery": psutil.sensors_battery().percent if psutil.sensors_battery() else None
        }
    
    def update_running_apps(self):
        """Update list of running applications"""
        self.running_apps = {}
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                self.running_apps[proc.info['name']] = proc.info['pid']
            except:
                pass
    
    async def restart_application(self, app_name: str) -> Dict[str, Any]:
        """
        Restart an application
        
        Args:
            app_name: Name of the application to restart
        
        Returns:
            Result dictionary
        """
        result = {
            "app": app_name,
            "action": "restart",
            "success": False,
            "message": ""
        }
        
        try:
            # Find and kill the process
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if app_name.lower() in proc.info['name'].lower():
                        pid = proc.info['pid']
                        proc_obj = psutil.Process(pid)
                        proc_obj.terminate()
                        
                        # Wait for process to terminate
                        await asyncio.sleep(1)
                        
                        if proc_obj.is_running():
                            proc_obj.kill()
                        
                        result["message"] = f"Terminated {app_name}"
                        result["success"] = True
                        break
                except:
                    pass
            
            if not result["success"]:
                result["message"] = f"Application {app_name} not found"
        
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def close_window(self, app_name: str) -> Dict[str, Any]:
        """
        Close a running application window
        
        Args:
            app_name: Name of the application to close
        
        Returns:
            Result dictionary
        """
        result = {
            "app": app_name,
            "action": "close",
            "success": False,
            "message": ""
        }
        
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if app_name.lower() in proc.info['name'].lower():
                        proc_obj = psutil.Process(proc.info['pid'])
                        proc_obj.terminate()
                        result["message"] = f"Closed {app_name}"
                        result["success"] = True
                        break
                except:
                    pass
            
            if not result["success"]:
                result["message"] = f"Application {app_name} not found"
        
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def open_application(self, app_name: str) -> Dict[str, Any]:
        """
        Open an application
        
        Args:
            app_name: Name or path of the application to open
        
        Returns:
            Result dictionary
        """
        result = {
            "app": app_name,
            "action": "open",
            "success": False,
            "message": ""
        }
        
        try:
            # Common applications
            app_paths = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "edge": "msedge.exe",
                "vscode": "code.exe",
                "discord": "Discord.exe",
                "spotify": "Spotify.exe",
                "steam": "steam.exe",
                "explorer": "explorer.exe",
                "cmd": "cmd.exe",
                "powershell": "powershell.exe",
            }
            
            path = app_paths.get(app_name.lower(), app_name)
            
            subprocess.Popen(path)
            result["message"] = f"Opened {app_name}"
            result["success"] = True
        
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def change_system_setting(self, setting: str, value: Any) -> Dict[str, Any]:
        """
        Change a system setting
        
        Args:
            setting: Setting name (brightness, volume, theme, etc)
            value: New value
        
        Returns:
            Result dictionary
        """
        result = {
            "setting": setting,
            "value": value,
            "success": False,
            "message": ""
        }
        
        try:
            if setting.lower() == "brightness":
                # Windows brightness control
                value = max(0, min(100, int(value)))
                os.system(f"powershell -Command \"(Get-WmiObject -Namespace root/cimv2 -Class WmiMonitorBrightnessSetting -ComputerName . | Where-Object {{$_.InstanceName -match '^.*DISPLAY' }}).WmiSetBrightness(1, {value})\"")
                result["message"] = f"Set brightness to {value}%"
                result["success"] = True
            
            elif setting.lower() == "volume":
                # Volume control using nircmd
                value = max(0, min(100, int(value)))
                os.system(f"nircmd.exe setsysvolume {int(value * 655)}")
                result["message"] = f"Set volume to {value}%"
                result["success"] = True
            
            elif setting.lower() == "theme":
                # Dark/Light theme toggle
                if value.lower() in ["dark", "light"]:
                    # This would require registry changes on Windows
                    result["message"] = f"Would set theme to {value}"
                    result["success"] = True
            
            else:
                result["message"] = f"Unknown setting: {setting}"
        
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def restart_system(self, delay_seconds: int = 60) -> Dict[str, Any]:
        """
        Schedule system restart
        
        Args:
            delay_seconds: Seconds to wait before restart
        
        Returns:
            Result dictionary
        """
        result = {
            "action": "restart",
            "delay": delay_seconds,
            "success": False,
            "message": ""
        }
        
        try:
            os.system(f"shutdown /r /t {delay_seconds} /c \"System restart scheduled\"")
            result["message"] = f"System restart scheduled in {delay_seconds} seconds"
            result["success"] = True
        
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def shutdown_system(self, delay_seconds: int = 60) -> Dict[str, Any]:
        """
        Schedule system shutdown
        
        Args:
            delay_seconds: Seconds to wait before shutdown
        
        Returns:
            Result dictionary
        """
        result = {
            "action": "shutdown",
            "delay": delay_seconds,
            "success": False,
            "message": ""
        }
        
        try:
            os.system(f"shutdown /s /t {delay_seconds} /c \"System shutdown scheduled\"")
            result["message"] = f"System shutdown scheduled in {delay_seconds} seconds"
            result["success"] = True
        
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        self.system_info = self._get_system_info()
        
        return {
            "cpu_percent": self.system_info["cpu_percent"],
            "memory_percent": self.system_info["memory_percent"],
            "disk_percent": self.system_info["disk_percent"],
            "battery_percent": self.system_info["battery"],
            "running_apps_count": len(self.running_apps)
        }
    
    async def list_running_apps(self) -> List[str]:
        """Get list of running applications"""
        self.update_running_apps()
        return list(self.running_apps.keys())
    
    async def lock_system(self) -> Dict[str, Any]:
        """Lock the system"""
        result = {
            "action": "lock",
            "success": False,
            "message": ""
        }
        
        try:
            os.system("rundll32.exe user32.dll,LockWorkStation")
            result["message"] = "System locked"
            result["success"] = True
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def sleep_system(self) -> Dict[str, Any]:
        """Put system to sleep"""
        result = {
            "action": "sleep",
            "success": False,
            "message": ""
        }
        
        try:
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            result["message"] = "System going to sleep"
            result["success"] = True
        except Exception as e:
            result["message"] = str(e)
        
        return result
    
    async def toggle_wifi(self, enabled: bool) -> Dict[str, Any]:
        """Toggle WiFi on/off"""
        result = {
            "action": "toggle_wifi",
            "enabled": enabled,
            "success": False,
            "message": ""
        }
        
        try:
            state = "on" if enabled else "off"
            os.system(f"netsh interface set interface WiFi {state}")
            result["message"] = f"WiFi turned {state}"
            result["success"] = True
        except Exception as e:
            result["message"] = str(e)
        
        return result
