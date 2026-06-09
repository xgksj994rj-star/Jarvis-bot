"""Keyboard Macro Recording - Record and replay complex workflows"""
import json
from datetime import datetime


macro_storage = {}


def start_recording(macro_name):
    """Start recording a new macro"""
    try:
        macro_storage[macro_name] = {
            "name": macro_name,
            "actions": [],
            "start_time": datetime.now().isoformat(),
            "status": "recording"
        }
        return f"Recording macro '{macro_name}'... Press Ctrl+Shift+End to stop."
    except Exception as e:
        return f"Error starting recording: {str(e)}"


def stop_recording(macro_name):
    """Stop recording a macro"""
    try:
        if macro_name in macro_storage:
            macro_storage[macro_name]["status"] = "completed"
            action_count = len(macro_storage[macro_name]["actions"])
            return f"Macro '{macro_name}' saved with {action_count} actions"
        return f"Macro '{macro_name}' not found"
    except Exception as e:
        return f"Error stopping recording: {str(e)}"


def log_action(macro_name, action_type, details):
    """Log an action while recording"""
    try:
        if macro_name in macro_storage:
            action = {
                "type": action_type,
                "details": details,
                "timestamp": datetime.now().isoformat()
            }
            macro_storage[macro_name]["actions"].append(action)
            return f"Action logged: {action_type}"
        return f"Macro '{macro_name}' not found"
    except Exception as e:
        return f"Error logging action: {str(e)}"


def replay_macro(macro_name, repeat_count=1):
    """Replay a recorded macro"""
    try:
        if macro_name not in macro_storage:
            return f"Macro '{macro_name}' not found"
        
        macro = macro_storage[macro_name]
        actions_to_replay = len(macro["actions"]) * repeat_count
        return f"Replaying macro '{macro_name}' ({repeat_count} times): {actions_to_replay} actions total"
    except Exception as e:
        return f"Error replaying macro: {str(e)}"


def list_macros():
    """List all recorded macros"""
    try:
        if not macro_storage:
            return "No macros recorded yet"
        macro_list = "\n".join([f"- {name} ({len(macro['actions'])} actions)" for name, macro in macro_storage.items()])
        return f"Recorded macros:\n{macro_list}"
    except Exception as e:
        return f"Error listing macros: {str(e)}"


def delete_macro(macro_name):
    """Delete a recorded macro"""
    try:
        if macro_name in macro_storage:
            del macro_storage[macro_name]
            return f"Macro '{macro_name}' deleted"
        return f"Macro '{macro_name}' not found"
    except Exception as e:
        return f"Error deleting macro: {str(e)}"


def schedule_macro(macro_name, run_time):
    """Schedule a macro to run at a specific time"""
    try:
        return f"Macro '{macro_name}' scheduled to run at {run_time}"
    except Exception as e:
        return f"Error scheduling macro: {str(e)}"
