"""
Live Transcription Overlay - Displays real-time audio transcription on screen.
Shows what Jarvis is hearing and understanding for debugging purposes.
"""

import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable
from collections import deque

from PyQt6.QtCore import (
    Qt, QTimer, QSize, pyqtSignal, QObject, QRect, QPoint,
)
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QBrush, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QMainWindow,
    QApplication, QFrame,
)


@dataclass
class TranscriptionEvent:
    """Represents a transcription event."""
    text: str
    is_input: bool  # True = user input (blue), False = Jarvis output (green)
    confidence: float = 1.0  # 0.0-1.0
    timestamp: float = None  # Unix timestamp

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class TranscriptionBuffer:
    """Manages buffered transcription history."""

    def __init__(self, max_events: int = 50):
        self.events = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def add_event(self, event: TranscriptionEvent):
        """Add transcription event to buffer."""
        with self._lock:
            self.events.append(event)

    def add_input(self, text: str, confidence: float = 1.0):
        """Add user input transcription."""
        self.add_event(TranscriptionEvent(text, True, confidence))

    def add_output(self, text: str, confidence: float = 1.0):
        """Add Jarvis output transcription."""
        self.add_event(TranscriptionEvent(text, False, confidence))

    def get_recent(self, count: int = 10) -> list[TranscriptionEvent]:
        """Get recent events."""
        with self._lock:
            return list(self.events)[-count:]

    def clear(self):
        """Clear buffer."""
        with self._lock:
            self.events.clear()

    def get_current_line(self) -> Optional[TranscriptionEvent]:
        """Get the most recent (current) transcription."""
        with self._lock:
            return self.events[-1] if self.events else None


class TranscriptionOverlay(QWidget):
    """
    Floating overlay window showing real-time transcription.
    Displays user input (blue) and Jarvis responses (green).
    """

    # Signals for thread-safe updates
    new_transcription = pyqtSignal(TranscriptionEvent)
    context_changed = pyqtSignal(str)  # Context description

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buffer = TranscriptionBuffer()
        self.current_input = ""  # Current partial input being transcribed
        self.current_context = "Idle"
        self._alpha = 0.95  # Window transparency
        self.debug_mode = False  # Debug mode flag

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self):
        """Setup UI components."""
        self.setWindowTitle("🎤 Jarvis Transcription")
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create background frame
        self.frame = QFrame()
        self.frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(1, 13, 20, 240);
                border: 2px solid #0d3347;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )

        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(8, 8, 8, 8)
        frame_layout.setSpacing(4)

        # Title/status bar
        self.title_label = QLabel("🎤 Listening...")
        self.title_label.setStyleSheet(
            "color: #00d4ff; font-weight: bold; font-size: 11px;"
        )
        frame_layout.addWidget(self.title_label)

        # Transcription display
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        self.text_display.setMaximumHeight(140)
        self.text_display.setStyleSheet(
            """
            QTextEdit {
                background-color: rgba(1, 15, 24, 180);
                border: 1px solid #1a5c7a;
                border-radius: 4px;
                color: #8ffcff;
                font-size: 12px;
                padding: 6px;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            """
        )
        frame_layout.addWidget(self.text_display)

        # Context/info bar
        self.info_label = QLabel("Context: General | Confidence: ---%")
        self.info_label.setStyleSheet(
            "color: #3a8a9a; font-size: 10px; padding-top: 2px;"
        )
        frame_layout.addWidget(self.info_label)

        self.frame.setLayout(frame_layout)
        layout.addWidget(self.frame)

        self.setLayout(layout)
        self.setGeometry(100, 100, 400, 200)

    def setup_signals(self):
        """Setup Qt signals."""
        self.new_transcription.connect(self._on_transcription_update)
        self.context_changed.connect(self._on_context_update)

    def add_input_text(self, text: str, confidence: float = 1.0):
        """Add user input transcription (partial or complete)."""
        self.current_input = text
        event = TranscriptionEvent(text, True, confidence)
        self.buffer.add_event(event)
        self.new_transcription.emit(event)

    def add_output_text(self, text: str, confidence: float = 1.0):
        """Add Jarvis output transcription."""
        if text.strip():
            event = TranscriptionEvent(text, False, confidence)
            self.buffer.add_event(event)
            self.new_transcription.emit(event)
            self.current_input = ""  # Clear current input

    def update_context(self, context_desc: str):
        """Update context display."""
        self.current_context = context_desc
        self.context_changed.emit(context_desc)

    def _on_transcription_update(self, event: TranscriptionEvent):
        """Handle transcription update (slot)."""
        self.update_display()

    def _on_context_update(self, context: str):
        """Handle context update (slot)."""
        self.update_display()

    def update_display(self):
        """Update the display with current transcription."""
        lines = []

        # Get recent events
        recent = self.buffer.get_recent(5)

        for event in recent:
            if event.is_input:
                # User input - blue
                prefix = "👤 You:"
                color = "#00ccff"
            else:
                # Jarvis output - green
                prefix = "🤖 Jarvis:"
                color = "#00ff88"

            conf_str = f"[{event.confidence*100:.0f}%]" if event.confidence < 1.0 else ""
            line = f'<span style="color: {color}"><b>{prefix}</b> {event.text} {conf_str}</span>'
            lines.append(line)

        # Add current input if present
        if self.current_input and self.current_input != recent[-1].text if recent else True:
            lines.append(f'<span style="color: #ffcc00; font-style: italic;">✎ Input: {self.current_input}...</span>')

        html = "<br>".join(lines)
        self.text_display.setHtml(html)

        # Update info label
        conf = 100 if not recent else recent[-1].confidence * 100
        self.info_label.setText(
            f"Context: {self.current_context} | Confidence: {conf:.0f}% | "
            f"Events: {len(self.buffer.events)}"
        )

        # Update title
        if self.current_input:
            self.title_label.setText(f"🎤 Listening... ({len(self.current_input)} chars)")
        else:
            self.title_label.setText("🎤 Listening...")

    def set_debug_mode(self, enabled: bool):
        """Enable/disable debug mode (shows more details)."""
        self.debug_mode = enabled
        if enabled:
            self.frame.setStyleSheet(
                """
                QFrame {
                    background-color: rgba(20, 1, 1, 240);
                    border: 2px solid #ff3355;
                    border-radius: 8px;
                    padding: 12px;
                }
                """
            )
            self.title_label.setText("🔴 DEBUG MODE - Transcription Overlay")
        else:
            self.frame.setStyleSheet(
                """
                QFrame {
                    background-color: rgba(1, 13, 20, 240);
                    border: 2px solid #0d3347;
                    border-radius: 8px;
                    padding: 12px;
                }
                """
            )

    def toggle_visibility(self):
        """Toggle overlay visibility."""
        if self.isVisible():
            self.hide()
        else:
            self.show()

    def closeEvent(self, event):
        """Handle close button click."""
        self.hide()  # Just hide, don't actually close
        event.ignore()  # Prevent the window from actually closing

    def clear_history(self):
        """Clear transcription history."""
        self.buffer.clear()
        self.current_input = ""
        self.text_display.clear()

    def paintEvent(self, event):
        """Custom paint for rounded corners and styling."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(1, 13, 20, 200))
        gradient.setColorAt(1, QColor(1, 15, 24, 200))

        painter.fillRect(self.rect(), gradient)

        super().paintEvent(event)


class TranscriptionManager:
    """
    Manager for transcription overlay.
    Handles integration with audio processing.
    Lazy-initialized: overlay only created when explicitly enabled.
    """

    def __init__(self):
        self.overlay: Optional[TranscriptionOverlay] = None
        self._app: Optional[QApplication] = None
        self._overlay_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._initialized = False

    def initialize(self):
        """Initialize the overlay in a separate thread."""
        if self._initialized:
            return

        if self.overlay:
            return

        self._initialized = True
        self._stop_event.clear()
        
        try:
            self._overlay_thread = threading.Thread(
                target=self._run_overlay,
                daemon=True
            )
            self._overlay_thread.start()
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Failed to initialize: {e}")
            self._initialized = False

    def _run_overlay(self):
        """Run overlay in a separate thread (for non-blocking UI)."""
        try:
            app = QApplication.instance()
            if app is None:
                app = QApplication.instance() or QApplication([])
            self._app = app

            self.overlay = TranscriptionOverlay()
            self.overlay.show()

            # Run event loop until stop_event is set
            while not self._stop_event.is_set():
                try:
                    if self._app:
                        self._app.processEvents()
                    time.sleep(0.01)
                except Exception:
                    time.sleep(0.01)
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error in overlay thread: {e}")
        finally:
            self.overlay = None
            self._initialized = False

    def add_input_transcription(self, text: str, confidence: float = 1.0):
        """Add user input transcription."""
        try:
            if self.overlay and self._initialized:
                self.overlay.add_input_text(text, confidence)
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error adding input: {e}")

    def add_output_transcription(self, text: str, confidence: float = 1.0):
        """Add Jarvis output transcription."""
        try:
            if self.overlay and self._initialized:
                self.overlay.add_output_text(text, confidence)
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error adding output: {e}")

    def update_context(self, context_desc: str):
        """Update context display."""
        try:
            if self.overlay and self._initialized:
                self.overlay.update_context(context_desc)
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error updating context: {e}")

    def toggle_overlay(self):
        """Toggle overlay visibility."""
        try:
            if not self._initialized:
                # Lazy initialize on first toggle
                self.initialize()
                time.sleep(0.5)  # Wait for initialization
            
            if self.overlay:
                self.overlay.toggle_visibility()
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error toggling overlay: {e}")

    def set_debug_mode(self, enabled: bool):
        """Enable/disable debug mode."""
        try:
            if not self._initialized:
                self.initialize()
                time.sleep(0.5)
            
            if self.overlay:
                self.overlay.set_debug_mode(enabled)
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error setting debug mode: {e}")

    def shutdown(self):
        """Shutdown overlay gracefully."""
        try:
            self._stop_event.set()
            if self._overlay_thread:
                self._overlay_thread.join(timeout=2)
            self.overlay = None
            self._initialized = False
        except Exception as e:
            print(f"[TranscriptionOverlay] ❌ Error during shutdown: {e}")


# Global instance
_transcription_manager = None


def get_transcription_manager() -> TranscriptionManager:
    """Get or create the global transcription manager."""
    global _transcription_manager
    if _transcription_manager is None:
        _transcription_manager = TranscriptionManager()
    return _transcription_manager
