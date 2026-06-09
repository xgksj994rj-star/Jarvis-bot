"""
Transcription Control - Voice-controllable transcription overlay and debug features.
"""

from actions.transcription_overlay import get_transcription_manager


def toggle_transcription_display(display: str = "overlay") -> str:
    """
    Toggle the transcription display on/off.
    
    Args:
        display: "overlay" | "debug" | "both"
    
    Returns:
        Status message
    """
    try:
        mgr = get_transcription_manager()
        
        if not mgr.overlay:
            # Initialize if not already done
            mgr.initialize()
            # Wait a moment for initialization
            import time
            time.sleep(0.5)
        
        if display.lower() in ("overlay", "both"):
            if mgr.overlay:
                mgr.toggle_overlay()
        
        if display.lower() in ("debug", "both"):
            if mgr.overlay:
                mgr.set_debug_mode(True)  # Enable debug mode
        
        return f"Transcription {display} toggled."
    except Exception as e:
        return f"Error toggling transcription: {str(e)}"


def enable_transcription_overlay() -> str:
    """Enable the transcription overlay display."""
    try:
        mgr = get_transcription_manager()
        
        # Initialize if not already done (lazy initialization)
        if not mgr._initialized:
            mgr.initialize()
            import time
            time.sleep(0.5)
        
        # Make sure overlay is visible
        if mgr.overlay and not mgr.overlay.isVisible():
            mgr.overlay.show()
        
        return "Transcription overlay enabled. You can see what I'm hearing in real-time on your screen."
    except Exception as e:
        return f"Error enabling overlay: {str(e)}"


def disable_transcription_overlay() -> str:
    """Disable the transcription overlay display."""
    try:
        mgr = get_transcription_manager()
        
        if mgr.overlay:
            mgr.overlay.hide()
        
        return "Transcription overlay disabled."
    except Exception as e:
        return f"Error disabling overlay: {str(e)}"


def enable_debug_mode() -> str:
    """Enable debug mode for detailed transcription information."""
    try:
        mgr = get_transcription_manager()
        
        if not mgr.overlay:
            mgr.initialize()
            import time
            time.sleep(0.5)
        
        if mgr.overlay:
            mgr.set_debug_mode(True)
        
        return "Debug mode enabled. Detailed transcription information will be displayed."
    except Exception as e:
        return f"Error enabling debug mode: {str(e)}"


def disable_debug_mode() -> str:
    """Disable debug mode."""
    try:
        mgr = get_transcription_manager()
        
        if not mgr.overlay:
            return "Transcription system not initialized."
        
        mgr.set_debug_mode(False)
        return "Debug mode disabled."
    except Exception as e:
        return f"Error disabling debug mode: {str(e)}"


def show_listening_status() -> str:
    """Show current listening status and context."""
    try:
        mgr = get_transcription_manager()
        
        if not mgr.overlay:
            mgr.initialize()
            import time
            time.sleep(0.5)
        
        if mgr.overlay:
            visible = "visible" if mgr.overlay.isVisible() else "hidden"
            debug = "enabled" if mgr.overlay.debug_mode else "disabled"
            context = mgr.overlay.current_context
            events = len(mgr.overlay.buffer.events)
            return (f"Transcription overlay is {visible}. Debug mode: {debug}. "
                    f"Current context: {context}. Transcription events: {events}.")
        return "Transcription system not initialized."
    except Exception as e:
        return f"Error getting status: {str(e)}"


def clear_transcription_history() -> str:
    """Clear the transcription history buffer."""
    try:
        mgr = get_transcription_manager()
        
        if not mgr.overlay:
            return "Transcription system not initialized."
        
        if mgr.overlay:
            mgr.overlay.clear_history()
            return "Transcription history cleared."
        return "Transcription system not initialized."
    except Exception as e:
        return f"Error clearing history: {str(e)}"


# These can be called from main.py's tool execution system
__all__ = [
    "toggle_transcription_display",
    "enable_transcription_overlay",
    "disable_transcription_overlay",
    "enable_debug_mode",
    "disable_debug_mode",
    "show_listening_status",
    "clear_transcription_history",
]
