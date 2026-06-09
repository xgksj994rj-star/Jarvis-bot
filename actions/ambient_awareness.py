"""
Ambient Awareness & Scene Classification
Detects context and application without asking, offers relevant help
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import psutil
from PIL import Image
import io

class AmbientAwareness:
    """Monitors screen context and offers proactive assistance"""
    
    def __init__(self):
        self.current_scene = None
        self.scene_history = []
        self.active_app = None
        self.last_screenshot = None
        self.context_confidence = 0.0
        
        # Scene definitions
        self.scene_definitions = {
            "coding": {
                "keywords": ["vscode", "code", "intellij", "visual studio", "editor", ".py", ".js", ".ts"],
                "apps": ["code", "Visual Studio Code", "PyCharm", "IntelliJ"],
                "suggestions": [
                    "Need help with code? I can debug, refactor, or explain it.",
                    "Want to search StackOverflow or documentation?",
                    "Need to run tests or deploy?"
                ]
            },
            "browsing": {
                "keywords": ["chrome", "firefox", "edge", "safari", "browser", "http", "search"],
                "apps": ["chrome", "firefox", "msedge", "Safari"],
                "suggestions": [
                    "Want me to search for something?",
                    "Should I read this page aloud?",
                    "Need to download or extract data?"
                ]
            },
            "writing": {
                "keywords": ["word", "doc", "document", "writer", "sheets", "spreadsheet", ".docx", ".xlsx"],
                "apps": ["WINWORD", "excel", "docs", "sheets"],
                "suggestions": [
                    "Want me to format this document?",
                    "Should I help with grammar or structure?",
                    "Need to create a table or chart?"
                ]
            },
            "video_call": {
                "keywords": ["zoom", "teams", "meet", "skype", "video", "call", "conference"],
                "apps": ["Zoom", "Teams", "skype"],
                "suggestions": [
                    "Need help managing the meeting?",
                    "Should I record or transcribe?",
                    "Want to share your screen?"
                ]
            },
            "gaming": {
                "keywords": ["game", "steam", "epic", "blender", "unity", "unreal"],
                "apps": ["steam", "Game", "Epic", "blender", "unity"],
                "suggestions": [
                    "Need game help or guides?",
                    "Want to optimize performance?",
                    "Should I record gameplay?"
                ]
            },
            "media": {
                "keywords": ["spotify", "youtube", "netflix", "vlc", "media", "music", "video"],
                "apps": ["Spotify", "youtube", "netflix", "vlc"],
                "suggestions": [
                    "Want to find similar music?",
                    "Should I create a playlist?",
                    "Need lyrics or music info?"
                ]
            },
            "email": {
                "keywords": ["outlook", "gmail", "email", "mail"],
                "apps": ["outlook", "gmail"],
                "suggestions": [
                    "Need to organize emails?",
                    "Want to schedule follow-ups?",
                    "Should I help draft a reply?"
                ]
            },
            "presentation": {
                "keywords": ["powerpoint", "presentation", "slides", "ppt"],
                "apps": ["POWERPNT", "slides"],
                "suggestions": [
                    "Need design suggestions?",
                    "Want me to generate content?",
                    "Should I check for typos?"
                ]
            },
            "discord": {
                "keywords": ["discord", "chat", "server", "channel"],
                "apps": ["Discord"],
                "suggestions": [
                    "Want to send a message?",
                    "Need to find something in chat history?",
                    "Should I moderate or manage roles?"
                ]
            },
            "system_settings": {
                "keywords": ["settings", "control panel", "windows settings", "preferences"],
                "apps": ["Settings", "Control Panel"],
                "suggestions": [
                    "What setting do you want to change?",
                    "Need help configuring something?",
                    "Want to troubleshoot an issue?"
                ]
            }
        }
    
    async def detect_scene(self, screenshot: Optional[Image.Image] = None, 
                          app_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect the current scene/context
        
        Args:
            screenshot: Optional screenshot to analyze
            app_name: Optional active application name
        
        Returns:
            Scene detection result with confidence and suggestions
        """
        result = {
            "scene": None,
            "confidence": 0.0,
            "active_app": app_name,
            "suggestions": [],
            "context_data": {}
        }
        
        try:
            # Get active application
            if not app_name:
                app_name = self._get_active_app()
            
            result["active_app"] = app_name
            
            # Classify scene based on app and keywords
            best_match = None
            best_score = 0
            
            for scene_name, scene_config in self.scene_definitions.items():
                score = 0
                
                # Check if app matches
                for app in scene_config["apps"]:
                    if app_name and app.lower() in app_name.lower():
                        score += 40
                
                # Check keywords (would analyze screenshot content here)
                if app_name:
                    for keyword in scene_config["keywords"]:
                        if keyword.lower() in app_name.lower():
                            score += 20
                
                if score > best_score:
                    best_score = score
                    best_match = scene_name
            
            if best_match:
                result["scene"] = best_match
                result["confidence"] = min(100, best_score)
                result["suggestions"] = self.scene_definitions[best_match]["suggestions"]
                result["context_data"] = await self._get_context_data(best_match)
            else:
                result["confidence"] = 0
                result["suggestions"] = ["What are you working on? I can help if you tell me the context."]
            
            self.current_scene = best_match
            self.last_screenshot = screenshot
            
            # Add to history
            self.scene_history.append({
                "timestamp": datetime.now().isoformat(),
                "scene": best_match,
                "app": app_name,
                "confidence": result["confidence"]
            })
            
            # Keep history manageable
            if len(self.scene_history) > 1000:
                self.scene_history = self.scene_history[-1000:]
        
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    def _get_active_app(self) -> Optional[str]:
        """Get the currently active application"""
        try:
            import win32gui
            import win32process
            
            hwnd = win32gui.GetForegroundWindow()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            
            try:
                proc = psutil.Process(pid)
                return proc.name()
            except:
                return None
        except:
            # Fallback
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] not in ['System', 'systemd']:
                        return proc.info['name']
                except:
                    pass
            return None
    
    async def _get_context_data(self, scene: str) -> Dict[str, Any]:
        """Get additional context data for a scene"""
        context = {}
        
        try:
            # Get system info
            context["cpu_usage"] = psutil.cpu_percent()
            context["memory_usage"] = psutil.virtual_memory().percent
            
            # Get time-based context
            hour = datetime.now().hour
            if hour < 12:
                context["time_of_day"] = "morning"
            elif hour < 17:
                context["time_of_day"] = "afternoon"
            else:
                context["time_of_day"] = "evening"
            
            # Scene-specific context
            if scene == "gaming":
                context["is_performance_intensive"] = True
            elif scene == "video_call":
                context["bandwidth_sensitive"] = True
            elif scene == "coding":
                context["file_tracking"] = "active"
        
        except:
            pass
        
        return context
    
    async def offer_help(self) -> str:
        """Generate contextual help offer"""
        if not self.current_scene:
            return "What are you working on? I'm here to help."
        
        scene_info = self.scene_definitions.get(self.current_scene)
        if not scene_info:
            return "I'm ready to assist. What do you need?"
        
        # Randomly pick a suggestion
        import random
        suggestion = random.choice(scene_info["suggestions"])
        
        return suggestion
    
    async def get_scene_history(self, minutes: int = 60) -> List[Dict]:
        """Get scene history for the last N minutes"""
        cutoff = datetime.now().timestamp() - (minutes * 60)
        
        history = []
        for entry in self.scene_history:
            try:
                timestamp = datetime.fromisoformat(entry["timestamp"]).timestamp()
                if timestamp > cutoff:
                    history.append(entry)
            except:
                pass
        
        return history
    
    async def detect_inactivity(self, seconds: int = 300) -> bool:
        """Detect if user has been inactive"""
        if not self.scene_history:
            return False
        
        last_entry = self.scene_history[-1]
        last_time = datetime.fromisoformat(last_entry["timestamp"])
        
        time_since = (datetime.now() - last_time).total_seconds()
        
        return time_since > seconds
    
    async def suggest_action(self) -> Optional[str]:
        """Suggest next action based on context"""
        if not self.current_scene:
            return None
        
        suggestions = {
            "coding": "You've been coding for a while. Time for a break? Or need help with debugging?",
            "browsing": "Finding what you need? Want me to search for something specific?",
            "gaming": "Playing for a while. Need performance tips or break reminder?",
            "video_call": "In a call. Need to share screen, record, or manage audio?",
            "writing": "Writing a document. Need help with structure, grammar, or formatting?",
        }
        
        return suggestions.get(self.current_scene)
    
    async def get_ambient_status(self) -> Dict[str, Any]:
        """Get full ambient awareness status"""
        return {
            "current_scene": self.current_scene,
            "confidence": self.context_confidence,
            "active_app": self._get_active_app(),
            "help_offer": await self.offer_help(),
            "action_suggestion": await self.suggest_action(),
            "scene_history_count": len(self.scene_history)
        }
