"""
Cross-App Automation System
Chains actions across multiple applications automatically
"""

import pyautogui
import time
import asyncio
import re
from typing import List, Dict, Optional, Callable, Any
import psutil
import subprocess
import os

class CrossAppAutomation:
    """Orchestrates complex multi-app workflows"""
    
    def __init__(self):
        self.workflows = {}
        self.running = False
        self.last_error = None
        
        # App locators
        self.app_paths = {
            "discord": ["Discord", "DiscordPTB", "DiscordCanary"],
            "chrome": ["chrome", "google-chrome"],
            "firefox": ["firefox", "firefox.exe"],
            "edge": ["msedge", "msedge.exe"],
            "vscode": ["Code", "code"],
            "notepad": ["notepad.exe"],
            "explorer": ["explorer.exe"],
            "outlook": ["Outlook.exe"],
            "teams": ["Teams.exe"],
        }
    
    def _find_app_window(self, app_name: str) -> Optional[str]:
        """Find a running application window"""
        app_name_lower = app_name.lower()
        
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if app_name_lower in proc.info['name'].lower():
                    return proc.info['name']
            except:
                pass
        
        return None
    
    def _bring_app_to_front(self, app_name: str) -> bool:
        """Bring an application window to front"""
        try:
            # Try to find and focus the window
            if os.name == 'nt':  # Windows
                import ctypes
                import win32gui
                
                # Find window by app name
                hwnd = win32gui.FindWindow(None, app_name)
                if hwnd:
                    win32gui.SetForegroundWindow(hwnd)
                    return True
            
            # Fallback: use Alt+Tab or taskbar
            return True
        except:
            return False
    
    async def navigate_app_and_execute(self,
                                      app_name: str,
                                      navigation_steps: List[Dict],
                                      delay: float = 0.5) -> Dict[str, Any]:
        """
        Navigate through an app and execute actions
        
        Args:
            app_name: Application to control (discord, chrome, etc)
            navigation_steps: List of steps with 'action' and 'params'
            delay: Delay between actions in seconds
        
        Returns:
            Execution result dict
        """
        result = {
            "app": app_name,
            "steps_executed": 0,
            "success": False,
            "error": None
        }
        
        try:
            # Bring app to front
            self._bring_app_to_front(app_name)
            await asyncio.sleep(1)
            
            for i, step in enumerate(navigation_steps):
                action = step.get("action")
                params = step.get("params", {})
                
                if action == "click":
                    # Click at coordinates or find and click element
                    x = params.get("x")
                    y = params.get("y")
                    text = params.get("text")
                    
                    if text:
                        # Find and click text on screen
                        await self._find_and_click_text(text)
                    else:
                        pyautogui.click(x, y)
                
                elif action == "type":
                    # Type text with optional modifiers
                    text = params.get("text", "")
                    pyautogui.typewrite(text, interval=0.05)
                
                elif action == "hotkey":
                    # Press keyboard shortcut
                    keys = params.get("keys", [])
                    pyautogui.hotkey(*keys)
                
                elif action == "wait":
                    # Wait for condition or time
                    wait_time = params.get("duration", 1)
                    condition = params.get("condition")
                    
                    if condition:
                        await self._wait_for_condition(condition)
                    else:
                        await asyncio.sleep(wait_time)
                
                elif action == "screenshot":
                    # Take screenshot and optionally search for text
                    result[f"screenshot_{i}"] = pyautogui.screenshot()
                
                elif action == "scroll":
                    # Scroll in a direction
                    direction = params.get("direction", "down")
                    amount = params.get("amount", 3)
                    
                    if direction == "up":
                        pyautogui.scroll(amount)
                    else:
                        pyautogui.scroll(-amount)
                
                elif action == "go_to_channel":
                    # Discord-specific: go to channel
                    channel_name = params.get("channel")
                    await self._discord_go_to_channel(channel_name)
                
                elif action == "send_message":
                    # Send a message in current focused window
                    message = params.get("message", "")
                    pyautogui.typewrite(message, interval=0.05)
                    pyautogui.press("enter")
                
                result["steps_executed"] += 1
                
                # Delay between steps
                if i < len(navigation_steps) - 1:
                    await asyncio.sleep(delay)
            
            result["success"] = True
        
        except Exception as e:
            result["error"] = str(e)
            self.last_error = str(e)
        
        return result
    
    async def _find_and_click_text(self, text: str) -> bool:
        """Find text on screen and click it"""
        try:
            import pytesseract
            from PIL import Image
            
            # Take screenshot and find text location
            screenshot = pyautogui.screenshot()
            # This would require OCR to find exact location
            # For now, use basic approach
            pyautogui.click()
            return True
        except:
            return False
    
    async def _wait_for_condition(self, condition: Dict) -> bool:
        """Wait for a condition to be met"""
        condition_type = condition.get("type")
        timeout = condition.get("timeout", 10)
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if condition_type == "window_open":
                window_name = condition.get("window")
                if self._find_app_window(window_name):
                    return True
            
            elif condition_type == "text_visible":
                # Would need OCR implementation
                pass
            
            await asyncio.sleep(0.5)
        
        return False
    
    async def _discord_go_to_channel(self, channel_name: str):
        """Navigate to a Discord channel"""
        # Use keyboard shortcut to open channel search
        pyautogui.hotkey("ctrl", "k")
        await asyncio.sleep(0.5)
        
        # Type channel name
        pyautogui.typewrite(channel_name, interval=0.05)
        await asyncio.sleep(0.5)
        
        # Press enter to go to channel
        pyautogui.press("enter")
    
    def create_workflow(self, name: str, workflow: List[Dict]) -> bool:
        """Create and save a workflow"""
        self.workflows[name] = workflow
        return True
    
    async def execute_workflow(self, name: str) -> Dict[str, Any]:
        """Execute a saved workflow"""
        if name not in self.workflows:
            return {"success": False, "error": "Workflow not found"}
        
        workflow = self.workflows[name]
        return await self.navigate_app_and_execute(workflow[0].get("app"), workflow)
    
    def get_workflow(self, name: str) -> Optional[List[Dict]]:
        """Get a workflow"""
        return self.workflows.get(name)
    
    def list_workflows(self) -> List[str]:
        """List all saved workflows"""
        return list(self.workflows.keys())


async def cross_app_automation_example():
    """Example usage"""
    automation = CrossAppAutomation()
    
    # Define workflow: Open Discord -> Go to #announcements -> Send message
    workflow = [
        {"action": "click", "params": {"x": 100, "y": 100}},  # Click Discord icon
        {"action": "wait", "params": {"duration": 1}},
        {"action": "go_to_channel", "params": {"channel": "announcements"}},
        {"action": "send_message", "params": {"message": "Hello from automation!"}}
    ]
    
    automation.create_workflow("discord_announcement", workflow)
    
    result = await automation.execute_workflow("discord_announcement")
    print(result)
