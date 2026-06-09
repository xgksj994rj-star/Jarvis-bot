import asyncio
import os
import re
import threading
import json
import sys
import io
import traceback
import shutil
import datetime
import time
import numpy as np
from pathlib import Path

from remote_server import start_remote_server

import sounddevice as sd
from google import genai
from google.genai import types

try:
    from ui import JarvisUI
except Exception as ui_error:
    print(f"[MAIN] ERROR: UI unavailable, Jarvis requires the UI to run: {ui_error}")
    traceback.print_exc()
    raise

from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message, check_twilio_configuration
from actions.reminder          import reminder, timer
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process, _capture_screen, _capture_camera
from actions.youtube_video     import youtube_video
from actions.social_media_creator import social_media_creator, social_media_manager
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.english_teacher   import english_teacher
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater
from actions.multi_llm          import multi_llm_action
from actions.music_control      import music_control
from actions.system_control     import system_control, volume_control, process_manager
from actions.advanced_automation import batch_file_operations, system_monitoring, package_management, scheduled_tasks, create_workflow, update_workflow, delete_workflow, list_workflows, run_workflow, create_conditional_automation
from actions.cross_app_automation import CrossAppAutomation
from actions.voice_system_control import VoiceSystemControl
from actions.ambient_awareness import AmbientAwareness
from actions.object_detection import ObjectDetector
from actions.ocr_text_extraction import OCRTextExtractor
from actions.gesture_recognition import GestureRecognizer
from actions.real_time_annotation import AnnotationOverlay
from actions.discord_integration import (
    check_messages as discord_check_messages,
    send_message as discord_send_discord_message,
    list_channels as discord_list_channels,
    list_voice_channels as discord_list_voice_channels,
    speak_in_voice_channel as discord_speak_in_voice_channel,
    check_engagement as discord_check_engagement,
    join_discord_channel as discord_join_text_channel,
    join_discord_voice_channel as discord_join_voice_channel,
    join_my_discord_voice_channel as discord_join_my_voice_channel,
    leave_discord_voice_channel as discord_leave_voice_channel,
    discord_voice_receive_support as discord_voice_receive_support,
    discord_play_music as discord_play_music,
    get_discord_bot,
)
from actions.email_intelligence import read_emails, send_email, search_emails, summarize_emails
from actions.calendar_master import schedule_meeting, get_next_meeting, find_available_slots, list_calendar_events, create_recurring_meeting
from actions.multi_model_router import route_task, analyze_task_type, send_to_claude, send_to_gpt4, compare_models, batch_process_tasks
from actions.data_visualization import generate_chart_data, create_productivity_dashboard, generate_sales_report, create_real_time_dashboard, export_chart, analyze_trends
from actions.smart_home_control import control_lights, set_thermostat, control_smart_device, get_device_status, create_scene, activate_scene, get_all_devices
from actions.image_generator import generate_image_dalle, generate_image_midjourney, generate_image_stable_diffusion, edit_image, upscale_image, remove_background, batch_generate_images
from actions.database_query import natural_language_to_sql, execute_query, query_customers, query_sales_data, generate_report, get_query_suggestions
from actions.macro_recorder import start_recording, stop_recording, log_action, replay_macro, list_macros, delete_macro, schedule_macro
from actions.collaboration_manager import start_screen_share, stop_screen_share, invite_collaborator, share_document, list_active_sessions, get_collaboration_stats, sync_files
from actions.predictive_automation import learn_from_action, predict_next_action, suggest_automation, auto_execute_routine, analyze_patterns, get_productivity_insights, personalize_suggestions
from actions.real_time_coding import analyze_code_quality, suggest_code_improvements, start_pair_programming_session, detect_code_smells, generate_unit_tests, optimize_performance
from actions.voice_cloning import train_custom_voice, synthesize_speech, clone_voice_from_recording, multi_language_synthesis, voice_emotion_analysis, real_time_voice_translation, voice_print_authentication, generate_voice_effects
from actions.ar_vr_integration import connect_ar_device, create_ar_overlay, control_vr_environment, track_hand_gestures, create_spatial_audio, vr_social_session, ar_navigation_guidance, mixed_reality_recording, haptic_feedback, eye_tracking_calibration
from actions.blockchain_crypto import create_crypto_wallet, check_wallet_balance, send_crypto_transaction, create_nft, interact_with_smart_contract, track_crypto_prices, generate_wallet_report, setup_crypto_alerts, analyze_blockchain_data
from actions.neural_network_training import train_custom_model, deploy_trained_model, fine_tune_existing_model, analyze_model_performance, create_dataset_from_user_data, optimize_model_hyperparameters, export_model_for_mobile, monitor_model_drift, federated_learning_setup
from actions.universal_translator import translate_text, real_time_voice_translation, detect_language, cultural_context_analysis, translate_document, create_translation_memory, batch_translate_texts, speech_to_speech_translation, train_custom_translation_model, live_conversation_translation
from actions.emotion_recognition import analyze_text_emotion, analyze_voice_emotion, analyze_facial_emotion, track_mood_over_time, suggest_mood_improvement, create_emotion_dashboard, real_time_emotion_monitoring, emotion_based_recommendations, analyze_emotional_intelligence, mood_journaling_assistant
from actions.audio_context import AudioContextManager, AppContext
from actions.transcription_overlay import get_transcription_manager
from actions.transcription_control import (
    toggle_transcription_display, enable_transcription_overlay, disable_transcription_overlay,
    enable_debug_mode, disable_debug_mode, show_listening_status, clear_transcription_history
)
from actions.startup_manager import startup_action as startup_manager_action


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:    
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, SMS, or initiates a phone call.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name or phone number (E.164 for SMS/call)"},
                "message_text": {"type": "STRING", "description": "The message to send or speak during a call"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, SMS, call, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "phone_call",
        "description": "Initiates a phone call through Twilio and speaks the provided message.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Phone number to call in E.164 format (e.g. +15551234567)"},
                "message_text": {"type": "STRING", "description": "Text to speak during the call"}
            },
            "required": ["receiver", "message_text"]
        }
    },
    {
        "name": "check_twilio_config",
        "description": "Checks Twilio credentials and verifies that SMS/call configuration is valid.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "social_media_creator",
        "description": (
            "Helps generate strategies, video ideas, faceless scripts, thumbnails, "
            "authorize YouTube, upload videos, publish to TikTok, schedule publishes, and track analytics."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "strategy | idea | script | thumbnail | open_upload | authorize_youtube | upload_video | publish_tiktok | auto_publish | schedule_publish | list_schedules | cancel_schedule | youtube_analytics | analytics_summary"
                },
                "platform": {"type": "STRING", "description": "youtube or tiktok"},
                "niche": {"type": "STRING", "description": "Content niche or topic"},
                "title": {"type": "STRING", "description": "Video title for script generation or upload"},
                "channel": {"type": "STRING", "description": "Optional channel name or id for reporting"},
                "description": {"type": "STRING", "description": "Video description for uploads"},
                "tags": {"type": "STRING", "description": "Comma-separated tags for uploads"},
                "privacy": {"type": "STRING", "description": "public | unlisted | private"},
                "length": {"type": "STRING", "description": "short | medium | long"},
                "count": {"type": "INTEGER", "description": "Number of video ideas to generate"},
                "prompt": {"type": "STRING", "description": "Thumbnail prompt for image generation"},
                "file_path": {"type": "STRING", "description": "Local path to a video file for upload"},
                "publish_time": {"type": "STRING", "description": "ISO datetime for scheduled publish"},
                "auto_create": {"type": "BOOLEAN", "description": "Create assets and video automatically before publishing"},
                "recurrence": {"type": "STRING", "description": "Recurrence pattern (daily, weekly, monthly)"},
                "thumbnail_prompt": {"type": "STRING", "description": "Prompt for thumbnail image generation"},
                "video_id": {"type": "STRING", "description": "YouTube video ID for analytics lookup"},
                "id": {"type": "STRING", "description": "Scheduled publish ID to cancel"}
            },
            "required": []
        }
    },
    {
        "name": "social_media_manager",
        "description": (
            "Provides a management workflow for creating ideas, generating scripts, auto-publishing, scheduling, and analytics for social media content."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "overview | idea | script | auto_publish | schedule_publish | list_schedules | cancel_schedule | analytics_summary | authorize_youtube"
                },
                "platform": {"type": "STRING", "description": "youtube or tiktok"},
                "niche": {"type": "STRING", "description": "Content niche or topic"},
                "title": {"type": "STRING", "description": "Video title for generation or publishing"},
                "channel": {"type": "STRING", "description": "Optional channel name or id for reporting"},
                "description": {"type": "STRING", "description": "Video description for uploads"},
                "tags": {"type": "STRING", "description": "Comma-separated tags for uploads"},
                "publish_time": {"type": "STRING", "description": "ISO datetime for scheduled publish"},
                "auto_create": {"type": "BOOLEAN", "description": "Create assets automatically before publishing"},
                "recurrence": {"type": "STRING", "description": "Recurrence pattern (daily, weekly, monthly)"},
                "thumbnail_prompt": {"type": "STRING", "description": "Prompt for thumbnail image generation"},
                "id": {"type": "STRING", "description": "Scheduled publish ID to cancel"}
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser including Opera GX. Use for: opening websites, searching the web, "
            "managing tabs (open/close), clicking elements, filling forms, scrolling, screenshots, navigation. "
            "Perfect for: look up info, open multiple tabs, close tabs, search with custom engines, fill out forms. "
            "Specify browser as 'operagx' to use Opera GX. Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | new_tab | close_tab | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Default: currently active. Use 'operagx' for Opera GX."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "english_teacher",
        "description": "Writes essays, papers, grammar checks, proofreading, editing, and English composition help.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | proofread | grammar_check | summarize | edit"},
                "description": {"type": "STRING", "description": "What to write or the editing instruction"},
                "text":        {"type": "STRING", "description": "Text to proofread, summarize, or edit"},
                "instruction": {"type": "STRING", "description": "Additional editing instructions"},
                "audience":    {"type": "STRING", "description": "Target audience or reader"},
                "tone":        {"type": "STRING", "description": "Tone: academic, formal, casual, persuasive, neutral"},
                "length":      {"type": "STRING", "description": "Desired length, e.g. 500 words or 1 page"},
                "output_path": {"type": "STRING", "description": "Where to save the generated text"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | hold | release | key_down | key_up | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "transcription_control",
        "description": (
            "Controls the real-time transcription overlay and debug mode. "
            "Use this to toggle the transcription display, enable/disable debug mode, "
            "or check the listening status and audio context. "
            "Perfect for debugging why commands aren't being recognized."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "toggle_overlay | enable_overlay | disable_overlay | enable_debug | disable_debug | show_status | clear_history"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_jarvis",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop Jarvis. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "timer",
        "description": "Sets a short countdown timer that notifies when complete.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "duration": {"type": "STRING", "description": "Timer duration, e.g. '10 minutes' or '30 seconds'"},
                "message":  {"type": "STRING", "description": "Message to show when the timer ends"}
            },
            "required": ["duration"]
        }
    },
    {
        "name": "multi_llm",
        "description": "Switch between different AI models (Gemini, OpenAI, Anthropic, Groq, Ollama). Use to change the AI provider or list available models.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING",  "description": "switch | list | add_key | current"},
                "provider":    {"type": "STRING",  "description": "LLM provider: gemini, openai, anthropic, groq, ollama"},
                "model":       {"type": "STRING",  "description": "Specific model name to use"},
                "api_key":     {"type": "STRING",  "description": "API key to add for a provider"},
                "ollama_host": {"type": "STRING",  "description": "Ollama host URL (default: http://localhost:11434)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "music_control",
        "description": "Control music playback: play, pause, skip, search, volume, now playing. Supports Spotify via native control or web API.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING",  "description": "play | pause | next | previous | playpause | search | nowplaying | volume | open | shuffle | repeat"},
                "query":  {"type": "STRING",  "description": "Search query or volume level (0-100)"},
                "track":  {"type": "STRING",  "description": "Track name to play"},
                "artist": {"type": "STRING",  "description": "Artist name"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "system_control",
        "description": (
            "Controls system-level operations like shutdown, restart, sleep, lock screen. "
            "Use for power management and system control commands."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action to perform: shutdown, restart, sleep, lock, hibernate"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "volume_control",
        "description": (
            "Controls system volume levels and mute state. "
            "Use for audio control commands."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action: up, down, mute, unmute, set"
                },
                "level": {
                    "type": "INTEGER",
                    "description": "Volume level 0-100 (only for set action)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "process_manager",
        "description": (
            "Manages system processes - list running processes, kill processes, start new ones. "
            "Use for process monitoring and management."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action: list, kill, start, monitor"
                },
                "process_name": {
                    "type": "STRING",
                    "description": "Process name (for kill/start actions)"
                },
                "pid": {
                    "type": "INTEGER",
                    "description": "Process ID (for kill action)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "batch_file_operations",
        "description": (
            "Perform batch operations on multiple files and directories. "
            "Use for copying, moving, deleting, or compressing multiple files at once."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action: copy, move, delete, compress"
                },
                "source_paths": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of source file/directory paths"
                },
                "destination": {
                    "type": "STRING",
                    "description": "Destination path (required for copy/move/compress)"
                },
                "archive_name": {
                    "type": "STRING",
                    "description": "Name for compressed archive (optional)"
                }
            },
            "required": ["action", "source_paths"]
        }
    },
    {
        "name": "system_monitoring",
        "description": (
            "Monitor system resources and performance metrics. "
            "Use to check CPU, memory, disk, network usage, or running processes."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "What to monitor: cpu, memory, disk, network, processes, all"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "package_management",
        "description": (
            "Manage software packages on the system. "
            "Use for installing, removing, or listing software packages."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action: list, install, remove, update"
                },
                "package_name": {
                    "type": "STRING",
                    "description": "Package name (required for install/remove)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "scheduled_tasks",
        "description": (
            "Manage basic scheduled tasks and cron jobs. "
            "Use for creating, listing, or removing scheduled tasks."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "Action: list, create, delete"
                },
                "task_name": {
                    "type": "STRING",
                    "description": "Task name (required for create/delete)"
                },
                "command": {
                    "type": "STRING",
                    "description": "Command to run (required for create)"
                },
                "schedule": {
                    "type": "STRING",
                    "description": "Cron schedule (required for create)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "discord_engagement_monitor",
        "description": "Monitor Discord mentions, engagement, and activity. Track mentions of you, server activity, unread messages, reactions, and engagement metrics across all your Discord servers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "check_mentions | engagement_summary | unread_count | activity_report | track_mentions | get_channel_activity"},
                "timeframe": {"type": "STRING", "description": "Time period: 1h | 6h | 24h | 7d | 30d (default: 24h)"},
                "channel_id": {"type": "STRING", "description": "Specific channel ID for get_channel_activity"},
                "include_reactions": {"type": "BOOLEAN", "description": "Include reaction counts in engagement (default: true)"},
                "include_replies": {"type": "BOOLEAN", "description": "Include reply counts (default: true)"},
                "sort_by": {"type": "STRING", "description": "Sort results by: recent | engagement | mentions (default: recent)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "check_discord_messages",
        "description": "Check recent messages in a Discord channel. Use this to read messages from Discord servers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel_id": {
                    "type": "STRING",
                    "description": "The Discord channel ID to check messages from"
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Number of recent messages to retrieve (default: 10, max: 50)"
                }
            },
            "required": ["channel_id"]
        }
    },
    {
        "name": "send_discord_message",
        "description": "Send a message to a Discord channel. Use this to post messages or updates to Discord servers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel_id": {
                    "type": "STRING",
                    "description": "The Discord channel ID to send the message to"
                },
                "message": {
                    "type": "STRING",
                    "description": "The message content to send"
                }
            },
            "required": ["channel_id", "message"]
        }
    },
    {
        "name": "list_discord_channels",
        "description": "List all accessible Discord channels. Use this to see available channels and their IDs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "list_discord_voice_channels",
        "description": "List all accessible Discord voice channels by guild and channel name.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "guild_id": {"type": "STRING", "description": "Optional guild ID to filter voice channels."}
            },
            "required": []
        }
    },
    {
        "name": "discord_voice_speak",
        "description": "Speak a message into the currently connected Discord voice channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "message_text": {"type": "STRING", "description": "Text to speak in the voice channel."}
            },
            "required": ["message_text"]
        }
    },
    {
        "name": "discord_play_music",
        "description": "Play music in a Discord voice channel using a song name or YouTube link.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {"type": "STRING", "description": "Song name or YouTube URL to play."},
                "channel_id": {"type": "STRING", "description": "Optional Discord voice channel ID to join before playing."}
            },
            "required": ["query"]
        }
    },
    {
        "name": "join_discord_channel",
        "description": "Join a Discord text channel by sending a join message or announcing Jarvis in the channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "channel_id": {"type": "STRING", "description": "The Discord text channel ID to join."},
                "join_message": {"type": "STRING", "description": "Optional message to send when joining the channel."}
            },
            "required": ["channel_id"]
        }
    },
    {
        "name": "join_discord_voice_channel",
        "description": "Join a Discord voice channel. Provide a voice channel ID, a member ID, a member name, or channel name, and optional guild ID.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "voice_channel_id": {"type": "STRING", "description": "The Discord voice channel ID to join."},
                "member_id": {"type": "STRING", "description": "The Discord member ID whose voice channel Jarvis should join."},
                "member_name": {"type": "STRING", "description": "The Discord member display name to join their current voice channel."},
                "channel_name": {"type": "STRING", "description": "The voice channel name to join if ID is not available."},
                "guild_id": {"type": "STRING", "description": "Optional guild ID to narrow voice channel search."}
            },
            "required": []
        }
    },
    {
        "name": "join_my_discord_voice_channel",
        "description": "Join the requesting user's Discord voice channel or join by member information when available.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "voice_channel_id": {"type": "STRING", "description": "The Discord voice channel ID to join."},
                "member_id": {"type": "STRING", "description": "The Discord member ID whose voice channel Jarvis should join."},
                "member_name": {"type": "STRING", "description": "The Discord member display name to join their current voice channel."},
                "channel_name": {"type": "STRING", "description": "The voice channel name to join if ID is not available."},
                "guild_id": {"type": "STRING", "description": "Optional guild ID to narrow voice channel search."}
            },
            "required": []
        }
    },
    {
        "name": "leave_discord_voice_channel",
        "description": "Leave the currently connected Discord voice channel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "guild_id": {"type": "STRING", "description": "Optional guild ID to leave voice chat from."}
            },
            "required": []
        }
    },
    {
        "name": "discord_voice_receive_support",
        "description": "Check whether Discord voice receive/listening support is available in the current environment.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "startup_manager",
        "description": "Enable, disable, or check Jarvis auto-start on Windows.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "add | remove | status | enable | disable"},
                "method": {"type": "STRING", "description": "registry | folder"}
            },
            "required": []
        }
    },
    {
        "name": "create_workflow",
        "description": "Create a custom workflow with triggers, conditions, and automated actions. Use for recurring tasks like daily backups or conditional automation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Unique name for the workflow"
                },
                "description": {
                    "type": "STRING",
                    "description": "Description of what the workflow does"
                },
                "trigger": {
                    "type": "STRING",
                    "description": "When to run: 'daily at 10:00', 'hourly', 'weekly on monday', 'manual'"
                },
                "condition": {
                    "type": "STRING",
                    "description": "Optional condition: 'weather tomorrow == rainy', 'time > 18:00', 'cpu > 80'"
                },
                "actions": {
                    "type": "ARRAY",
                    "description": "List of actions to perform",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type": {
                                "type": "STRING",
                                "description": "Action type: file_backup, send_message, reminder, system_control, notification"
                            },
                            "params": {
                                "type": "OBJECT",
                                "description": "Parameters for the action"
                            }
                        },
                        "required": ["type"]
                    }
                }
            },
            "required": ["name", "description", "trigger"]
        }
    },
    {
        "name": "update_workflow",
        "description": "Update an existing workflow's settings or actions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Name of the workflow to update"
                },
                "description": {
                    "type": "STRING",
                    "description": "New description (optional)"
                },
                "trigger": {
                    "type": "STRING",
                    "description": "New trigger schedule (optional)"
                },
                "condition": {
                    "type": "STRING",
                    "description": "New condition (optional)"
                },
                "actions": {
                    "type": "ARRAY",
                    "description": "New actions list (optional)",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type": {"type": "STRING"},
                            "params": {"type": "OBJECT"}
                        }
                    }
                },
                "enabled": {
                    "type": "BOOLEAN",
                    "description": "Enable or disable the workflow (optional)"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "delete_workflow",
        "description": "Delete a workflow permanently.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Name of the workflow to delete"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "list_workflows",
        "description": "List all available workflows with their status and settings.",
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
        "name": "run_workflow",
        "description": "Manually execute a workflow immediately.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Name of the workflow to run"
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "create_conditional_automation",
        "description": "Create conditional automation that triggers when specific conditions are met. Perfect for weather-based or system-based triggers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "name": {
                    "type": "STRING",
                    "description": "Unique name for the conditional automation"
                },
                "condition": {
                    "type": "STRING",
                    "description": "Condition to check: 'weather tomorrow == rainy', 'cpu > 80', 'time > 18:00'"
                },
                "actions": {
                    "type": "ARRAY",
                    "description": "Actions to perform when condition is met",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "type": {
                                "type": "STRING",
                                "description": "Action type: send_message, reminder, system_control, notification"
                            },
                            "params": {
                                "type": "OBJECT",
                                "description": "Parameters for the action"
                            }
                        },
                        "required": ["type"]
                    }
                },
                "check_interval": {
                    "type": "INTEGER",
                    "description": "How often to check condition in seconds (default: 60)",
                    "default": 60
                }
            },
            "required": ["name", "condition", "actions"]
        }
    },
    {
        "name": "email_intelligence",
        "description": "Email management: read unread emails, send emails, search emails, summarize emails from Gmail/Outlook.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "read | send | search | summarize"},
                "recipient": {"type": "STRING", "description": "Email address to send to (for send action)"},
                "subject": {"type": "STRING", "description": "Email subject (for send action)"},
                "body": {"type": "STRING", "description": "Email body/content (for send action)"},
                "query": {"type": "STRING", "description": "Search query (for search action)"},
                "limit": {"type": "INTEGER", "description": "Number of emails to fetch (default: 5)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "calendar_master",
        "description": "Google Calendar integration: schedule meetings, find available slots, list events, create recurring meetings.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "schedule | next_meeting | find_slots | list_events | recurring"},
                "title": {"type": "STRING", "description": "Meeting title (for schedule/recurring)"},
                "date": {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time": {"type": "STRING", "description": "Time in HH:MM format"},
                "attendees": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of attendee emails"},
                "description": {"type": "STRING", "description": "Meeting description"},
                "duration_minutes": {"type": "INTEGER", "description": "Meeting duration in minutes"},
                "recurrence": {"type": "STRING", "description": "Recurrence pattern (daily, weekly, monthly)"},
                "days_ahead": {"type": "INTEGER", "description": "Number of days to list (default: 7)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "multi_model_ai",
        "description": "Route tasks to optimal AI models: Claude for coding, GPT-4 for creative, Gemini for analysis. Switch between models as needed.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "route | analyze_type | compare | batch_process"},
                "task_description": {"type": "STRING", "description": "Description of the task"},
                "task_type": {"type": "STRING", "description": "coding | creative | analysis | research | writing | math | general"},
                "tasks": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of tasks for batch processing"},
                "prompt": {"type": "STRING", "description": "Prompt to send to AI model"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "data_visualization",
        "description": "Create interactive charts, dashboards, and reports from data. Generate productivity dashboards, sales reports, trend analysis.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "generate_chart | dashboard | sales_report | live_dashboard | export | analyze_trends"},
                "chart_type": {"type": "STRING", "description": "bar | line | pie | scatter (for generate_chart)"},
                "data": {"type": "ARRAY", "items": {"type": "NUMBER"}, "description": "Data points for visualization"},
                "metrics": {"type": "OBJECT", "description": "Metrics for dashboard"},
                "format": {"type": "STRING", "description": "png | pdf | svg | html (for export)"},
                "data_series": {"type": "ARRAY", "items": {"type": "NUMBER"}, "description": "Time series data for trend analysis"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "smart_home_control",
        "description": "Control smart home devices: lights, thermostat, locks, cameras. Create and activate scenes. Supports Alexa, Home Assistant, MQTT.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "control_lights | thermostat | device | status | scene | activate_scene | list_devices"},
                "room": {"type": "STRING", "description": "Room name (for control_lights)"},
                "device_action": {"type": "STRING", "description": "on | off | dim (for control_lights)"},
                "brightness": {"type": "INTEGER", "description": "Brightness level 0-100 (for control_lights)"},
                "temperature": {"type": "NUMBER", "description": "Target temperature in Fahrenheit"},
                "mode": {"type": "STRING", "description": "heat | cool | auto (for thermostat)"},
                "device_name": {"type": "STRING", "description": "Name of the smart device"},
                "parameters": {"type": "OBJECT", "description": "Device-specific parameters"},
                "scene_name": {"type": "STRING", "description": "Name of the scene"},
                "devices_config": {"type": "OBJECT", "description": "Device configurations for scene"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "image_generator",
        "description": "Generate, edit, and enhance images using DALL-E 3, Midjourney, or Stable Diffusion. Create hero images, upscale, remove backgrounds.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "dalle | midjourney | stable_diffusion | edit | upscale | remove_bg | batch"},
                "prompt": {"type": "STRING", "description": "Image generation prompt"},
                "style": {"type": "STRING", "description": "Art style (realistic, cinematic, abstract, etc.)"},
                "size": {"type": "STRING", "description": "Image size (1024x1024, 1280x720, etc.)"},
                "image_path": {"type": "STRING", "description": "Path to image file (for edit/upscale)"},
                "strength": {"type": "NUMBER", "description": "Edit strength 0-1 (for edit action)"},
                "scale_factor": {"type": "INTEGER", "description": "Upscale multiplier 2-4 (for upscale)"},
                "model": {"type": "STRING", "description": "Model choice for batch generation"},
                "prompts": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of prompts for batch generation"}
            },
            "required": ["action", "prompt"]
        }
    },
    {
        "name": "natural_language_database",
        "description": "Query databases with natural language. Convert English to SQL and execute queries. Analyze customers, sales data, generate reports.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "convert_sql | execute | query_customers | sales_data | report | suggestions"},
                "nl_query": {"type": "STRING", "description": "Natural language query"},
                "filter_criteria": {"type": "OBJECT", "description": "Filter criteria for queries"},
                "time_period": {"type": "STRING", "description": "last_month | last_week | last_year"},
                "product": {"type": "STRING", "description": "Product filter for sales data"},
                "partial_query": {"type": "STRING", "description": "Partial query for suggestions"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "keyboard_macro",
        "description": "Record and replay keyboard/mouse macros. Record complex workflows and replay them on demand or on schedule.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "start_recording | stop_recording | replay | list | delete | schedule"},
                "macro_name": {"type": "STRING", "description": "Name of the macro"},
                "action_type": {"type": "STRING", "description": "Type of action being recorded"},
                "details": {"type": "STRING", "description": "Details of the action"},
                "repeat_count": {"type": "INTEGER", "description": "Number of times to replay (default: 1)"},
                "run_time": {"type": "STRING", "description": "Time to schedule macro run (HH:MM format)"}
            },
            "required": ["action", "macro_name"]
        }
    },
    {
        "name": "collaboration_tools",
        "description": "Real-time collaboration: screen sharing, invite collaborators, share documents, sync files with team members.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "screen_share | stop_share | invite | share_doc | list_sessions | stats | sync"},
                "participant_email": {"type": "STRING", "description": "Email of collaboration participant"},
                "duration_minutes": {"type": "INTEGER", "description": "Duration of screen share (default: 60)"},
                "session_id": {"type": "STRING", "description": "Session ID to stop (for stop_share)"},
                "project_name": {"type": "STRING", "description": "Project name for collaboration"},
                "permissions": {"type": "STRING", "description": "edit | view | comment (default: edit)"},
                "document_path": {"type": "STRING", "description": "Path to document to share"},
                "access_level": {"type": "STRING", "description": "view | edit | admin"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "predictive_automation",
        "description": "ML-based learning from user patterns. Auto-suggest automations, predict next actions, execute learned routines automatically.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "learn | predict | suggest | execute_routine | analyze | productivity_insights | personalize"},
                "action_type": {"type": "STRING", "description": "Type of action to learn from"},
                "timestamp": {"type": "STRING", "description": "When the action occurred"},
                "context": {"type": "STRING", "description": "Context for the action"},
                "action_pattern": {"type": "STRING", "description": "Pattern to suggest automation for"},
                "routine_name": {"type": "STRING", "description": "morning | coding | shutdown (for execute_routine)"},
                "user_preferences": {"type": "OBJECT", "description": "User preferences for personalization"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "real_time_coding",
        "description": "AI-assisted coding with live suggestions, code review, pair programming, and automated testing.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "analyze_quality | suggest_improvements | pair_programming | detect_smells | generate_tests | optimize_performance"},
                "code": {"type": "STRING", "description": "Code snippet to analyze"},
                "language": {"type": "STRING", "description": "Programming language"},
                "partner_email": {"type": "STRING", "description": "Email for pair programming"},
                "project_name": {"type": "STRING", "description": "Project name for collaboration"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "voice_cloning",
        "description": "Custom voice training, synthesis, and advanced voice effects with emotion analysis.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "train_voice | synthesize | clone_voice | multi_lang | emotion_analysis | real_time_translate | authenticate | voice_effects"},
                "text": {"type": "STRING", "description": "Text to synthesize"},
                "voice_name": {"type": "STRING", "description": "Name for custom voice"},
                "audio_samples": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Audio sample paths"},
                "recording_path": {"type": "STRING", "description": "Path to voice recording"},
                "languages": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Languages for synthesis"},
                "target_language": {"type": "STRING", "description": "Target language for translation"},
                "emotion": {"type": "STRING", "description": "Voice emotion"},
                "effect_type": {"type": "STRING", "description": "Voice effect to apply"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "ar_vr_integration",
        "description": "Control AR glasses, VR headsets, create overlays, and manage mixed reality experiences.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "connect_device | create_overlay | control_environment | track_gestures | spatial_audio | vr_social | navigation | recording | haptic | calibrate"},
                "device_type": {"type": "STRING", "description": "glasses | headset | hmd"},
                "content": {"type": "STRING", "description": "Content for overlay"},
                "position": {"type": "STRING", "description": "3D position coordinates"},
                "environment_name": {"type": "STRING", "description": "VR environment name"},
                "friends_list": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of participant emails"},
                "destination": {"type": "STRING", "description": "Navigation destination"},
                "intensity": {"type": "NUMBER", "description": "Haptic feedback intensity"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "blockchain_crypto",
        "description": "Manage cryptocurrency wallets, NFTs, smart contracts, and blockchain interactions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "create_wallet | check_balance | send_transaction | create_nft | smart_contract | track_prices | wallet_report | setup_alerts | analyze_data"},
                "wallet_type": {"type": "STRING", "description": "ethereum | bitcoin"},
                "wallet_address": {"type": "STRING", "description": "Wallet address"},
                "to_address": {"type": "STRING", "description": "Recipient address"},
                "amount": {"type": "STRING", "description": "Transaction amount"},
                "currency": {"type": "STRING", "description": "ETH | BTC | USDT"},
                "metadata": {"type": "OBJECT", "description": "NFT metadata"},
                "contract_address": {"type": "STRING", "description": "Smart contract address"},
                "function_name": {"type": "STRING", "description": "Contract function"},
                "symbols": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Crypto symbols to track"},
                "timeframe": {"type": "STRING", "description": "Report timeframe"},
                "conditions": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Alert conditions"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "neural_network_training",
        "description": "Train custom AI models, deploy them, and manage machine learning workflows.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "train_model | deploy_model | fine_tune | analyze_performance | create_dataset | optimize_hyperparams | export_mobile | monitor_drift | federated_learning"},
                "dataset_path": {"type": "STRING", "description": "Path to training data"},
                "model_type": {"type": "STRING", "description": "classification | regression | detection"},
                "model_path": {"type": "STRING", "description": "Path to model file"},
                "deployment_target": {"type": "STRING", "description": "local | cloud | mobile"},
                "base_model": {"type": "STRING", "description": "Base model to fine-tune"},
                "new_data": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "New training data"},
                "data_sources": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Data sources for dataset"},
                "search_space": {"type": "OBJECT", "description": "Hyperparameter search space"},
                "target_platform": {"type": "STRING", "description": "android | ios"},
                "participants": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Federated learning participants"},
                "model_architecture": {"type": "OBJECT", "description": "Model architecture config"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "universal_translator",
        "description": "Real-time translation of any language with cultural context and custom model training.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "translate_text | voice_translate | detect_lang | cultural_analysis | translate_doc | create_memory | batch_translate | speech_translate | train_model | live_conversation"},
                "text": {"type": "STRING", "description": "Text to translate"},
                "source_lang": {"type": "STRING", "description": "Source language"},
                "target_lang": {"type": "STRING", "description": "Target language"},
                "context": {"type": "STRING", "description": "Translation context"},
                "audio_stream": {"type": "STRING", "description": "Audio stream for voice translation"},
                "source_culture": {"type": "STRING", "description": "Source culture"},
                "target_culture": {"type": "STRING", "description": "Target culture"},
                "document_path": {"type": "STRING", "description": "Document to translate"},
                "translation": {"type": "STRING", "description": "Translation text for memory"},
                "domain": {"type": "STRING", "description": "Translation domain"},
                "texts": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Texts for batch translation"},
                "audio_input": {"type": "STRING", "description": "Audio input for speech translation"},
                "training_data": {"type": "ARRAY", "items": {"type": "OBJECT"}, "description": "Training data for custom model"},
                "participants": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Conversation participants"},
                "languages": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Languages for conversation"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "emotion_recognition",
        "description": "Analyze emotions from voice, text, and facial expressions with mood tracking and recommendations.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "analyze_text | analyze_voice | analyze_facial | track_mood | suggest_improvement | create_dashboard | real_time_monitor | recommendations | analyze_ei | mood_journal"},
                "text": {"type": "STRING", "description": "Text to analyze"},
                "audio_data": {"type": "STRING", "description": "Audio data path"},
                "image_path": {"type": "STRING", "description": "Image path for facial analysis"},
                "timeframe": {"type": "STRING", "description": "Time period for tracking"},
                "current_mood": {"type": "STRING", "description": "Current mood state"},
                "context": {"type": "STRING", "description": "Context for mood analysis"},
                "user_id": {"type": "STRING", "description": "User ID for dashboard"},
                "activity_type": {"type": "STRING", "description": "Type of activity for recommendations"},
                "text_or_audio": {"type": "STRING", "description": "Content for EI analysis"},
                "entry_text": {"type": "STRING", "description": "Journal entry text"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "cross_app_automation",
        "description": "Chain actions across multiple applications automatically (e.g., open Discord -> go to #announcements -> send message)",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {"type": "STRING", "description": "Main application to control (discord, chrome, firefox, etc)"},
                "workflow_name": {"type": "STRING", "description": "Optional saved workflow name to execute"},
                "steps": {
                    "type": "ARRAY",
                    "description": "List of steps to execute",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "action": {"type": "STRING", "description": "click | type | hotkey | wait | screenshot | scroll | go_to_channel | send_message"},
                            "params": {"type": "OBJECT", "description": "Action parameters"}
                        }
                    }
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "voice_system_control",
        "description": "Control system operations via voice: restart apps, close windows, change settings, lock/sleep system",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "restart_app | close_window | open_app | change_setting | restart_system | shutdown_system | lock | sleep | status | list_apps | toggle_wifi"},
                "app_name": {"type": "STRING", "description": "Application name (for restart/close/open)"},
                "setting": {"type": "STRING", "description": "Setting name (brightness, volume, theme)"},
                "value": {"type": "STRING", "description": "Setting value"},
                "delay": {"type": "INTEGER", "description": "Delay in seconds (for restart/shutdown)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "ambient_awareness",
        "description": "Detect current context/application without asking, offer relevant help based on what's on screen",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "detect_scene | offer_help | get_status | get_history | detect_inactivity | suggest_action"},
                "minutes": {"type": "INTEGER", "description": "Minutes for history (detect_scene default: auto)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "object_detection",
        "description": "Detect, count, and track objects on screen with highlighting",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "detect | count | highlight | track_motion"},
                "object_type": {"type": "STRING", "description": "Type of object to detect/count (person, car, text, etc)"},
                "angle": {"type": "STRING", "description": "screen or camera (default: screen)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "ocr_text_extraction",
        "description": "Extract text from screen, find errors, extract code/emails/URLs/phone numbers",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "extract_text | find_errors | extract_code | extract_table | read_log | find_urls | find_emails | find_phones | highlight_text"},
                "search_patterns": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "Regex patterns to search for"
                },
                "file_path": {"type": "STRING", "description": "Path to log file (for read_log action)"},
                "search_text": {"type": "STRING", "description": "Text to highlight on screen"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "gesture_recognition",
        "description": "Detect hand gestures and body movements for hands-free control",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "detect_hand | detect_body | detect_swipe | detect_click | get_history | detect_posture"},
                "angle": {"type": "STRING", "description": "screen or camera (default: camera)"}
            },
            "required": ["action"]
        }
    },
    {
        "name": "real_time_annotation",
        "description": "Display AI insights and labels on screen in real-time with overlays",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "annotate_screen | create_insight_panel | create_debug_overlay | create_heatmap | get_statistics"},
                "annotations": {
                    "type": "ARRAY",
                    "description": "List of annotations to add",
                    "items": {"type": "OBJECT"}
                },
                "insights": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of insight strings"
                },
                "position": {"type": "STRING", "description": "Position for overlay: top_left | top_right | bottom_left | bottom_right"}
            },
            "required": ["action"]
        }
    },
]

class JarvisLive:

    def __init__(self, ui: JarvisUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: asyncio.Event | None = None
        self._stop_requested = asyncio.Event()
        self._wake_word_active = False
        self._wake_word_expires = datetime.datetime.now(datetime.timezone.utc)
        self._manual_listen_override_expires = datetime.datetime.now(datetime.timezone.utc)
        self._manual_listen_return_state = None
        self._manual_listen_timer: threading.Timer | None = None

        # Audio context and transcription overlay
        self.audio_context_mgr = AudioContextManager(
            update_callback=self._on_audio_context_changed
        )
        self.audio_context_mgr.start_monitoring(interval=1.0)
        
        # Transcription overlay - lazy initialized (only on demand)
        self.transcription_mgr = get_transcription_manager()
        self._debug_mode = False
        self._transcription_enabled = False  # Disabled by default
        
        # New feature modules
        self.cross_app_automation = CrossAppAutomation()
        self.voice_system_control = VoiceSystemControl()
        self.ambient_awareness = AmbientAwareness()
        self.object_detector = ObjectDetector()
        self.ocr_text_extractor = OCRTextExtractor()
        self.gesture_recognizer = GestureRecognizer()
        self.annotation_overlay = AnnotationOverlay()

    def _on_text_command(self, text: str):
        if self._is_stop_phrase(text):
            if self._loop:
                asyncio.run_coroutine_threadsafe(self._request_stop(), self._loop)
            return

        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def _on_audio_context_changed(self, context_info):
        """Callback when audio context changes."""
        if self.transcription_mgr and self.transcription_mgr._initialized and self.transcription_mgr.overlay:
            self.transcription_mgr.update_context(context_info.description)
        active_override = self._wake_word_is_or_manual_override_active()
        badge_state = "Listening" if context_info.should_listen or active_override else "Paused"
        context_label = context_info.context.value.title()
        status_text = f"{context_label} · {badge_state} · Sensitivity {int(context_info.sensitivity_multiplier * 100)}%"
        self.ui.set_context_status(status_text)

        print(f"[JARVIS] 📍 Context: {context_info.description} | "
              f"Listen: {context_info.should_listen} | "
              f"Sensitivity: {context_info.sensitivity_multiplier:.1f}")
        if self.ui.muted:
            return
        if not context_info.should_listen and not active_override:
            self.ui.set_state("PAUSED")
        elif not self.ui.speaking:
            self.ui.set_state("LISTENING")

    def _wake_word_is_active(self) -> bool:
        if not self._wake_word_active:
            return False
        if datetime.datetime.now(datetime.timezone.utc) >= self._wake_word_expires:
            self._wake_word_active = False
            return False
        return True

    def _manual_listen_override_is_active(self) -> bool:
        return datetime.datetime.now(datetime.timezone.utc) < self._manual_listen_override_expires

    def _cancel_manual_listen_timer(self):
        if self._manual_listen_timer is not None:
            try:
                self._manual_listen_timer.cancel()
            except Exception:
                pass
            self._manual_listen_timer = None

    def _activate_manual_listen(self, duration: int = 30):
        self._cancel_manual_listen_timer()
        self._manual_listen_override_expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration)
        self._manual_listen_return_state = (
            "MUTED" if self.ui.muted else
            "PAUSED" if not self.audio_context_mgr.should_listen() else
            "LISTENING"
        )
        self._manual_listen_timer = threading.Timer(duration, self._end_manual_listen_override)
        self._manual_listen_timer.daemon = True
        self._manual_listen_timer.start()
        self.ui.write_log(f"SYS: Manual listen override activated for {duration} seconds.")
        if not self.ui.muted:
            self.ui.set_state("LISTENING")

    def _end_manual_listen_override(self):
        self._manual_listen_override_expires = datetime.datetime.now(datetime.timezone.utc)
        self._cancel_manual_listen_timer()
        restore_state = self._manual_listen_return_state or "LISTENING"
        self._manual_listen_return_state = None
        if not self.ui.speaking:
            self.ui.write_log(f"SYS: Manual listen override ended; restoring {restore_state}.")
            self.ui.set_state(restore_state)

    def _wake_word_is_or_manual_override_active(self) -> bool:
        return self._wake_word_is_active() or self._manual_listen_override_is_active()

    def _activate_wake_word(self, duration: int = 60):
        self._wake_word_active = True
        self._wake_word_expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=duration)
        self.ui.write_log("SYS: Wake word detected. Listening for the next command.")
        print("[JARVIS] 🔔 Wake word activated")

    def _contains_wake_word(self, text: str) -> bool:
        normalized = re.sub(r"[^\w\s]", "", text.lower())
        return bool(re.search(r"\bjarvis\b", normalized))

    def toggle_transcription_overlay(self):
        """Toggle transcription overlay visibility."""
        if self.transcription_mgr:
            if not self.transcription_mgr._initialized:
                # Lazy init on first toggle
                self.transcription_mgr.initialize()
                import time
                time.sleep(0.3)
            
            if self.transcription_mgr.overlay:
                self.transcription_mgr.overlay.toggle_visibility()
                self._transcription_enabled = self.transcription_mgr.overlay.isVisible()
            
            state = "enabled" if self._transcription_enabled else "disabled"
            print(f"[JARVIS] 📝 Transcription overlay {state}")

    def toggle_debug_mode(self):
        """Toggle debug mode for transcription overlay."""
        if self.transcription_mgr:
            # Make sure overlay is initialized first
            if not self.transcription_mgr._initialized:
                self.transcription_mgr.initialize()
                import time
                time.sleep(0.3)
            
            self._debug_mode = not self._debug_mode
            self.transcription_mgr.set_debug_mode(self._debug_mode)
            state = "ON" if self._debug_mode else "OFF"
            print(f"[JARVIS] 🔴 DEBUG MODE {state}")
            self.ui.write_log(f"SYS: Debug mode {state}")

    def _save_to_photos(self, image_path: Path) -> str:
        photos_dir = Path(__file__).resolve().parent / "photos"
        photos_dir.mkdir(exist_ok=True)
        target_path = photos_dir / image_path.name
        shutil.copy2(image_path, target_path)
        return str(target_path)

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _is_stop_phrase(self, text: str) -> bool:
        if not text:
            return False
        normalized = re.sub(r"[^\w\s]", "", text.lower()).strip()
        stop_phrases = ("jarvis stop", "stop jarvis", "stop", "pause")
        return any(phrase == normalized or phrase in normalized for phrase in stop_phrases)

    async def _request_stop(self):
        if self._stop_requested.is_set():
            return
        self._stop_requested.set()
        self.ui.write_log("SYS: Stop command detected. Returning to listening mode.")
        self.ui.stop_speaking()
        self._drain_audio_queue()
        if self._turn_done_event:
            self._turn_done_event.set()

    def _drain_audio_queue(self):
        if not self.audio_in_queue:
            return
        while not self.audio_in_queue.empty():
            try:
                self.audio_in_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[JARVIS] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "music_control":
                r = await loop.run_in_executor(None, lambda: music_control(
                    action=args.get("action", "play"),
                    query=args.get("query", ""),
                    track=args.get("track", ""),
                    artist=args.get("artist", ""),
                    player=self.ui,
                ))
                result = r or "Music control action completed."

            elif name == "system_control":
                r = await loop.run_in_executor(None, lambda: system_control(
                    action=args.get("action", "status"),
                    player=self.ui,
                ))
                result = r or "System control action completed."

            elif name == "volume_control":
                r = await loop.run_in_executor(None, lambda: volume_control(
                    action=args.get("action", "set"),
                    level=args.get("level"),
                    player=self.ui,
                ))
                result = r or "Volume control action completed."

            elif name == "process_manager":
                r = await loop.run_in_executor(None, lambda: process_manager(
                    action=args.get("action", "list"),
                    process_name=args.get("process_name"),
                    pid=args.get("pid"),
                    player=self.ui,
                ))
                result = r or "Process manager action completed."

            elif name == "batch_file_operations":
                r = await loop.run_in_executor(None, lambda: batch_file_operations(
                    action=args.get("action", "copy"),
                    source_paths=args.get("source_paths", []),
                    destination=args.get("destination"),
                    archive_name=args.get("archive_name"),
                ))
                result = r or "Batch file operation completed."

            elif name == "system_monitoring":
                r = await loop.run_in_executor(None, lambda: system_monitoring(
                    action=args.get("action", "all"),
                ))
                result = r or "System monitoring completed."

            elif name == "package_management":
                r = await loop.run_in_executor(None, lambda: package_management(
                    action=args.get("action", "list"),
                    package_name=args.get("package_name"),
                ))
                result = r or "Package management action completed."

            elif name == "scheduled_tasks":
                r = await loop.run_in_executor(None, lambda: scheduled_tasks(
                    action=args.get("action", "list"),
                    task_name=args.get("task_name"),
                    command=args.get("command"),
                    schedule=args.get("schedule"),
                ))
                result = r or "Scheduled task action completed."

            elif name == "create_workflow":
                r = await loop.run_in_executor(None, lambda: create_workflow(
                    name=args.get("name", ""),
                    description=args.get("description", ""),
                    trigger=args.get("trigger", ""),
                    condition=args.get("condition"),
                    actions=args.get("actions", []),
                ))
                result = r or "Workflow created."

            elif name == "update_workflow":
                r = await loop.run_in_executor(None, lambda: update_workflow(
                    name=args.get("name", ""),
                    description=args.get("description"),
                    trigger=args.get("trigger"),
                    condition=args.get("condition"),
                    actions=args.get("actions"),
                    enabled=args.get("enabled"),
                ))
                result = r or "Workflow updated."

            elif name == "delete_workflow":
                r = await loop.run_in_executor(None, lambda: delete_workflow(
                    name=args.get("name", ""),
                ))
                result = r or "Workflow deleted."

            elif name == "list_workflows":
                r = await loop.run_in_executor(None, lambda: list_workflows())
                result = r or "Workflows listed."

            elif name == "run_workflow":
                r = await loop.run_in_executor(None, lambda: run_workflow(
                    name=args.get("name", ""),
                ))
                result = r or "Workflow executed."

            elif name == "create_conditional_automation":
                r = await loop.run_in_executor(None, lambda: create_conditional_automation(
                    name=args.get("name", ""),
                    condition=args.get("condition", ""),
                    actions=args.get("actions", []),
                    check_interval=args.get("check_interval", 60),
                ))
                result = r or "Conditional automation created."

            elif name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "discord_engagement_monitor":
                r = await discord_check_engagement(
                    action=args.get("action", "engagement_summary"),
                    timeframe=args.get("timeframe", "24h"),
                    channel_id=args.get("channel_id"),
                    include_reactions=args.get("include_reactions", True),
                    include_replies=args.get("include_replies", True),
                    sort_by=args.get("sort_by", "recent")
                )
                result = r or "Discord engagement checked."

            elif name == "check_discord_messages":
                r = await discord_check_messages(
                    channel_id=args.get("channel_id", ""),
                    limit=args.get("limit", 10)
                )
                result = r or "Discord messages checked."

            elif name == "send_discord_message":
                r = await discord_send_discord_message(
                    channel_id=args.get("channel_id", ""),
                    message=args.get("message", "")
                )
                result = r or "Discord message sent."

            elif name == "list_discord_voice_channels":
                r = await discord_list_voice_channels(
                    guild_id=args.get("guild_id", "")
                )
                result = r or "Discord voice channels listed."

            elif name == "discord_voice_speak":
                r = await loop.run_in_executor(None, lambda: discord_speak_in_voice_channel(
                    message=args.get("message_text", "")
                ))
                result = r or "Spoke in Discord voice channel."

            elif name == "discord_play_music":
                r = await loop.run_in_executor(None, lambda: discord_play_music(
                    query=args.get("query", ""),
                    channel_id=args.get("channel_id", "")
                ))
                result = r or "Discord music play requested."

            elif name == "join_discord_channel":
                r = await loop.run_in_executor(None, lambda: discord_join_text_channel(
                    channel_id=args.get("channel_id", ""),
                    join_message=args.get("join_message", "Jarvis has joined the channel.")
                ))
                result = r or f"Joined Discord channel {args.get('channel_id')}"

            elif name == "join_discord_voice_channel":
                r = await loop.run_in_executor(None, lambda: discord_join_voice_channel(
                    voice_channel_id=args.get("voice_channel_id", ""),
                    member_id=args.get("member_id", ""),
                    member_name=args.get("member_name", ""),
                    channel_name=args.get("channel_name", ""),
                    guild_id=args.get("guild_id", "")
                ))
                result = r or "Joined Discord voice channel."

            elif name == "join_my_discord_voice_channel":
                r = await loop.run_in_executor(None, lambda: discord_join_my_voice_channel(
                    voice_channel_id=args.get("voice_channel_id", ""),
                    member_id=args.get("member_id", ""),
                    member_name=args.get("member_name", ""),
                    channel_name=args.get("channel_name", ""),
                    guild_id=args.get("guild_id", "")
                ))
                result = r or "Joined Discord voice channel."

            elif name == "leave_discord_voice_channel":
                r = await loop.run_in_executor(None, lambda: discord_leave_voice_channel(
                    guild_id=args.get("guild_id", "")
                ))
                result = r or "Left Discord voice channel."

            elif name == "discord_voice_receive_support":
                r = await loop.run_in_executor(None, lambda: discord_voice_receive_support())
                result = r or "Discord voice receive support checked."

            elif name == "startup_manager":
                r = await loop.run_in_executor(None, lambda: startup_manager_action(
                    action=args.get("action", "status"),
                    method=args.get("method", "registry")
                ))
                result = r or "Startup manager action completed."

            elif name == "list_discord_channels":
                r = await loop.run_in_executor(None, lambda: discord_list_channels())
                result = r or "Discord channels listed."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "phone_call":
                if not args.get("receiver") or not args.get("message_text"):
                    result = "Please provide both receiver and message_text for the phone call."
                else:
                    call_args = {
                        "receiver": args.get("receiver"),
                        "message_text": args.get("message_text"),
                        "platform": "call",
                    }
                    r = await loop.run_in_executor(None, lambda: send_message(parameters=call_args, response=None, player=self.ui, session_memory=None))
                    result = r or f"Call initiated to {args.get('receiver')}"

            elif name == "check_twilio_config":
                r = await loop.run_in_executor(None, lambda: check_twilio_configuration())
                result = r or "Twilio configuration checked."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "social_media_creator":
                r = await loop.run_in_executor(None, lambda: social_media_creator(parameters=args, response=None, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "social_media_manager":
                r = await loop.run_in_executor(None, lambda: social_media_manager(parameters=args, response=None, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "english_teacher":
                r = await loop.run_in_executor(None, lambda: english_teacher(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "transcription_control":
                action = args.get("action", "show_status").lower()
                try:
                    if action == "toggle_overlay":
                        result = toggle_transcription_display("overlay")
                    elif action == "enable_overlay":
                        result = enable_transcription_overlay()
                    elif action == "disable_overlay":
                        result = disable_transcription_overlay()
                    elif action == "enable_debug":
                        result = enable_debug_mode()
                    elif action == "disable_debug":
                        result = disable_debug_mode()
                    elif action == "show_status":
                        result = show_listening_status()
                    elif action == "clear_history":
                        result = clear_transcription_history()
                    else:
                        result = f"Unknown transcription action: {action}"
                except Exception as e:
                    result = f"Error: {str(e)}"
                
                self.ui.write_log(result)

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "email_intelligence":
                action = args.get("action", "read")
                if action == "send":
                    r = await loop.run_in_executor(None, lambda: send_email(
                        recipient=args.get("recipient", ""),
                        subject=args.get("subject", ""),
                        body=args.get("body", ""),
                        email_address=args.get("email_address", ""),
                        password=args.get("password", "")
                    ))
                elif action == "search":
                    r = await loop.run_in_executor(None, lambda: search_emails(
                        query=args.get("query", ""),
                        email_address=args.get("email_address", ""),
                        password=args.get("password", "")
                    ))
                elif action == "summarize":
                    r = await loop.run_in_executor(None, lambda: summarize_emails(
                        email_address=args.get("email_address", ""),
                        password=args.get("password", ""),
                        num_emails=args.get("limit", 5)
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: read_emails(
                        email_address=args.get("email_address", ""),
                        password=args.get("password", ""),
                        limit=args.get("limit", 5)
                    ))
                result = r or "Email action completed."

            elif name == "calendar_master":
                action = args.get("action", "next_meeting")
                if action == "schedule":
                    r = await loop.run_in_executor(None, lambda: schedule_meeting(
                        title=args.get("title", ""),
                        date=args.get("date", ""),
                        time=args.get("time", ""),
                        attendees=args.get("attendees", []),
                        description=args.get("description", "")
                    ))
                elif action == "recurring":
                    r = await loop.run_in_executor(None, lambda: create_recurring_meeting(
                        title=args.get("title", ""),
                        recurrence=args.get("recurrence", ""),
                        start_date=args.get("date", ""),
                        time=args.get("time", "")
                    ))
                elif action == "find_slots":
                    r = await loop.run_in_executor(None, lambda: find_available_slots(
                        attendees=args.get("attendees", []),
                        duration_minutes=args.get("duration_minutes", 60)
                    ))
                elif action == "list_events":
                    r = await loop.run_in_executor(None, lambda: list_calendar_events(
                        days_ahead=args.get("days_ahead", 7)
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: get_next_meeting())
                result = r or "Calendar action completed."

            elif name == "multi_model_ai":
                action = args.get("action", "route")
                if action == "compare":
                    r = await loop.run_in_executor(None, lambda: compare_models(
                        prompt=args.get("prompt", "")
                    ))
                elif action == "batch_process":
                    r = await loop.run_in_executor(None, lambda: batch_process_tasks(
                        tasks=args.get("tasks", [])
                    ))
                elif action == "analyze_type":
                    r = await loop.run_in_executor(None, lambda: analyze_task_type(
                        task_description=args.get("task_description", "")
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: route_task(
                        task_description=args.get("task_description", ""),
                        task_type=args.get("task_type", "general")
                    ))
                result = r or "AI routing completed."

            elif name == "data_visualization":
                action = args.get("action", "generate_chart")
                if action == "dashboard":
                    r = await loop.run_in_executor(None, lambda: create_productivity_dashboard(
                        daily_logs=args.get("data", [])
                    ))
                elif action == "sales_report":
                    r = await loop.run_in_executor(None, lambda: generate_sales_report(
                        sales_data=args.get("data", [])
                    ))
                elif action == "analyze_trends":
                    r = await loop.run_in_executor(None, lambda: analyze_trends(
                        data_series=args.get("data_series", [])
                    ))
                elif action == "export":
                    r = await loop.run_in_executor(None, lambda: export_chart(
                        chart_data=args.get("data", {}),
                        format=args.get("format", "png")
                    ))
                elif action == "live_dashboard":
                    r = await loop.run_in_executor(None, lambda: create_real_time_dashboard(
                        metrics=args.get("metrics", {})
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: generate_chart_data(
                        chart_type=args.get("chart_type", "line"),
                        data_points=args.get("data", [])
                    ))
                result = r or "Visualization created."

            elif name == "smart_home_control":
                action = args.get("action", "status")
                if action == "control_lights":
                    r = await loop.run_in_executor(None, lambda: control_lights(
                        room=args.get("room", ""),
                        action=args.get("device_action", "on"),
                        brightness=args.get("brightness", 100)
                    ))
                elif action == "thermostat":
                    r = await loop.run_in_executor(None, lambda: set_thermostat(
                        temperature=args.get("temperature", 72),
                        mode=args.get("mode", "heat")
                    ))
                elif action == "scene":
                    r = await loop.run_in_executor(None, lambda: create_scene(
                        scene_name=args.get("scene_name", ""),
                        devices_config=args.get("devices_config", {})
                    ))
                elif action == "activate_scene":
                    r = await loop.run_in_executor(None, lambda: activate_scene(
                        scene_name=args.get("scene_name", "")
                    ))
                elif action == "list_devices":
                    r = await loop.run_in_executor(None, lambda: get_all_devices())
                elif action == "device":
                    r = await loop.run_in_executor(None, lambda: control_smart_device(
                        device_name=args.get("device_name", ""),
                        action=args.get("device_action", ""),
                        parameters=args.get("parameters")
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: get_device_status(
                        device_name=args.get("device_name", "")
                    ))
                result = r or "Smart home action completed."

            elif name == "image_generator":
                action = args.get("action", "dalle")
                if action == "midjourney":
                    r = await loop.run_in_executor(None, lambda: generate_image_midjourney(
                        prompt=args.get("prompt", ""),
                        style=args.get("style", "cinematic")
                    ))
                elif action == "stable_diffusion":
                    r = await loop.run_in_executor(None, lambda: generate_image_stable_diffusion(
                        prompt=args.get("prompt", ""),
                        steps=args.get("steps", 50),
                        guidance_scale=args.get("guidance_scale", 7.5)
                    ))
                elif action == "edit":
                    r = await loop.run_in_executor(None, lambda: edit_image(
                        image_path=args.get("image_path", ""),
                        prompt=args.get("prompt", ""),
                        strength=args.get("strength", 0.8)
                    ))
                elif action == "upscale":
                    r = await loop.run_in_executor(None, lambda: upscale_image(
                        image_path=args.get("image_path", ""),
                        scale_factor=args.get("scale_factor", 2)
                    ))
                elif action == "remove_bg":
                    r = await loop.run_in_executor(None, lambda: remove_background(
                        image_path=args.get("image_path", "")
                    ))
                elif action == "batch":
                    r = await loop.run_in_executor(None, lambda: batch_generate_images(
                        prompts=args.get("prompts", []),
                        model=args.get("model", "dall-e")
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: generate_image_dalle(
                        prompt=args.get("prompt", ""),
                        style=args.get("style", "realistic"),
                        size=args.get("size", "1024x1024")
                    ))
                if isinstance(r, str) and Path(r).is_file():
                    image_path = Path(r)
                    approved = self.ui.show_image_approval(
                        str(image_path), prompt=args.get("prompt", "")
                    )
                    if approved:
                        saved_path = self._save_to_photos(image_path)
                        r = f"Image saved to photos folder: {saved_path}"
                    else:
                        edit_prompt = args.get("prompt", "")
                        edited = await loop.run_in_executor(None, lambda: edit_image(
                            image_path=str(image_path),
                            prompt=f"Refine face and composition: {edit_prompt}",
                            strength=0.8
                        ))
                        if isinstance(edited, str) and Path(edited).is_file():
                            approved_edit = self.ui.show_image_approval(
                                str(Path(edited)), prompt=edit_prompt, edited=True
                            )
                            if approved_edit:
                                saved_path = self._save_to_photos(Path(edited))
                                r = f"Edited image saved to photos folder: {saved_path}"
                            else:
                                r = f"Edited image ready at {edited}." \
                                    f" If you want another revision, ask Jarvis to edit it again."
                        else:
                            r = edited
                result = r or "Image generated."

            elif name == "natural_language_database":
                action = args.get("action", "execute")
                if action == "convert_sql":
                    r = await loop.run_in_executor(None, lambda: natural_language_to_sql(
                        nl_query=args.get("nl_query", "")
                    ))
                elif action == "query_customers":
                    r = await loop.run_in_executor(None, lambda: query_customers(
                        filter_criteria=args.get("filter_criteria")
                    ))
                elif action == "sales_data":
                    r = await loop.run_in_executor(None, lambda: query_sales_data(
                        time_period=args.get("time_period", "last_month"),
                        product=args.get("product")
                    ))
                elif action == "report":
                    r = await loop.run_in_executor(None, lambda: generate_report(
                        query_text=args.get("nl_query", "")
                    ))
                elif action == "suggestions":
                    r = await loop.run_in_executor(None, lambda: get_query_suggestions(
                        partial_query=args.get("partial_query", "")
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: execute_query(
                        query_text=args.get("nl_query", "")
                    ))
                result = r or "Database query completed."

            elif name == "keyboard_macro":
                action = args.get("action", "list")
                macro_name = args.get("macro_name", "")
                if action == "start_recording":
                    r = await loop.run_in_executor(None, lambda: start_recording(macro_name))
                elif action == "stop_recording":
                    r = await loop.run_in_executor(None, lambda: stop_recording(macro_name))
                elif action == "replay":
                    r = await loop.run_in_executor(None, lambda: replay_macro(
                        macro_name=macro_name,
                        repeat_count=args.get("repeat_count", 1)
                    ))
                elif action == "delete":
                    r = await loop.run_in_executor(None, lambda: delete_macro(macro_name))
                elif action == "schedule":
                    r = await loop.run_in_executor(None, lambda: schedule_macro(
                        macro_name=macro_name,
                        run_time=args.get("run_time", "")
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: list_macros())
                result = r or "Macro operation completed."

            elif name == "collaboration_tools":
                action = args.get("action", "list_sessions")
                if action == "screen_share":
                    r = await loop.run_in_executor(None, lambda: start_screen_share(
                        participant_email=args.get("participant_email", ""),
                        duration_minutes=args.get("duration_minutes", 60)
                    ))
                elif action == "stop_share":
                    r = await loop.run_in_executor(None, lambda: stop_screen_share(
                        session_id=args.get("session_id", "")
                    ))
                elif action == "invite":
                    r = await loop.run_in_executor(None, lambda: invite_collaborator(
                        email=args.get("participant_email", ""),
                        project_name=args.get("project_name", ""),
                        permissions=args.get("permissions", "edit")
                    ))
                elif action == "share_doc":
                    r = await loop.run_in_executor(None, lambda: share_document(
                        document_path=args.get("document_path", ""),
                        email=args.get("participant_email", ""),
                        access_level=args.get("access_level", "view")
                    ))
                elif action == "stats":
                    r = await loop.run_in_executor(None, lambda: get_collaboration_stats())
                elif action == "sync":
                    r = await loop.run_in_executor(None, lambda: sync_files(
                        project_name=args.get("project_name", ""),
                        target_collaborator=args.get("participant_email")
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: list_active_sessions())
                result = r or "Collaboration action completed."

            elif name == "predictive_automation":
                action = args.get("action", "predict")
                if action == "learn":
                    r = await loop.run_in_executor(None, lambda: learn_from_action(
                        action_type=args.get("action_type", ""),
                        timestamp=args.get("timestamp", ""),
                        context=args.get("context")
                    ))
                elif action == "suggest":
                    r = await loop.run_in_executor(None, lambda: suggest_automation(
                        action_pattern=args.get("action_pattern", "")
                    ))
                elif action == "execute_routine":
                    r = await loop.run_in_executor(None, lambda: auto_execute_routine(
                        routine_name=args.get("routine_name", "")
                    ))
                elif action == "analyze":
                    r = await loop.run_in_executor(None, lambda: analyze_patterns())
                elif action == "productivity_insights":
                    r = await loop.run_in_executor(None, lambda: get_productivity_insights())
                elif action == "personalize":
                    r = await loop.run_in_executor(None, lambda: personalize_suggestions(
                        user_preferences=args.get("user_preferences", {})
                    ))
                else:
                    r = await loop.run_in_executor(None, lambda: predict_next_action())
                result = r or "Predictive automation completed."

            elif name == "real_time_coding":
                action = args.get("action", "analyze_quality")
                if action == "analyze_quality":
                    r = await loop.run_in_executor(None, lambda: analyze_code_quality(
                        code=args.get("code", ""),
                        language=args.get("language", "")
                    ))
                elif action == "suggest_improvements":
                    r = await loop.run_in_executor(None, lambda: suggest_code_improvements(
                        code=args.get("code", ""),
                        language=args.get("language", "")
                    ))
                elif action == "pair_programming":
                    r = await loop.run_in_executor(None, lambda: start_pair_programming_session(
                        partner_email=args.get("partner_email", ""),
                        project_name=args.get("project_name", "")
                    ))
                elif action == "detect_smells":
                    r = await loop.run_in_executor(None, lambda: detect_code_smells(
                        code=args.get("code", ""),
                        language=args.get("language", "")
                    ))
                elif action == "generate_tests":
                    r = await loop.run_in_executor(None, lambda: generate_unit_tests(
                        code=args.get("code", ""),
                        language=args.get("language", "")
                    ))
                elif action == "optimize_performance":
                    r = await loop.run_in_executor(None, lambda: optimize_performance(
                        code=args.get("code", ""),
                        language=args.get("language", "")
                    ))
                result = r or "Real-time coding completed."

            elif name == "voice_cloning":
                action = args.get("action", "train_voice")
                if action == "train_voice":
                    r = await loop.run_in_executor(None, lambda: train_custom_voice(
                        voice_name=args.get("voice_name", ""),
                        audio_samples=args.get("audio_samples", [])
                    ))
                elif action == "synthesize":
                    r = await loop.run_in_executor(None, lambda: synthesize_speech(
                        text=args.get("text", ""),
                        voice_name=args.get("voice_name", "")
                    ))
                elif action == "clone_voice":
                    r = await loop.run_in_executor(None, lambda: clone_voice_from_recording(
                        recording_path=args.get("recording_path", ""),
                        voice_name=args.get("voice_name", "")
                    ))
                elif action == "multi_lang":
                    r = await loop.run_in_executor(None, lambda: multi_language_synthesis(
                        text=args.get("text", ""),
                        languages=args.get("languages", []),
                        voice_name=args.get("voice_name", "")
                    ))
                elif action == "emotion_analysis":
                    r = await loop.run_in_executor(None, lambda: voice_emotion_analysis(
                        audio_data=args.get("audio_data", "")
                    ))
                elif action == "real_time_translate":
                    r = await loop.run_in_executor(None, lambda: real_time_voice_translation(
                        audio_stream=args.get("audio_stream", ""),
                        target_language=args.get("target_language", "")
                    ))
                elif action == "authenticate":
                    r = await loop.run_in_executor(None, lambda: voice_print_authentication(
                        audio_sample=args.get("audio_data", ""),
                        voice_name=args.get("voice_name", "")
                    ))
                elif action == "voice_effects":
                    r = await loop.run_in_executor(None, lambda: generate_voice_effects(
                        audio_data=args.get("audio_data", ""),
                        effect_type=args.get("effect_type", ""),
                        emotion=args.get("emotion", "")
                    ))
                result = r or "Voice cloning completed."

            elif name == "ar_vr_integration":
                action = args.get("action", "connect_device")
                if action == "connect_device":
                    r = await loop.run_in_executor(None, lambda: connect_ar_device(
                        device_type=args.get("device_type", "")
                    ))
                elif action == "create_overlay":
                    r = await loop.run_in_executor(None, lambda: create_ar_overlay(
                        content=args.get("content", ""),
                        position=args.get("position", "")
                    ))
                elif action == "control_environment":
                    r = await loop.run_in_executor(None, lambda: control_vr_environment(
                        environment_name=args.get("environment_name", ""),
                        action=args.get("device_action", "")
                    ))
                elif action == "track_gestures":
                    r = await loop.run_in_executor(None, lambda: track_hand_gestures())
                elif action == "spatial_audio":
                    r = await loop.run_in_executor(None, lambda: create_spatial_audio(
                        audio_source=args.get("audio_data", ""),
                        position=args.get("position", "")
                    ))
                elif action == "vr_social":
                    r = await loop.run_in_executor(None, lambda: vr_social_session(
                        friends_list=args.get("friends_list", []),
                        environment_name=args.get("environment_name", "")
                    ))
                elif action == "navigation":
                    r = await loop.run_in_executor(None, lambda: ar_navigation_guidance(
                        destination=args.get("destination", "")
                    ))
                elif action == "recording":
                    r = await loop.run_in_executor(None, lambda: mixed_reality_recording(
                        duration_minutes=args.get("duration_minutes", 10)
                    ))
                elif action == "haptic":
                    r = await loop.run_in_executor(None, lambda: haptic_feedback(
                        intensity=args.get("intensity", 0.5)
                    ))
                elif action == "calibrate":
                    r = await loop.run_in_executor(None, lambda: eye_tracking_calibration())
                result = r or "AR/VR integration completed."

            elif name == "blockchain_crypto":
                action = args.get("action", "create_wallet")
                if action == "create_wallet":
                    r = await loop.run_in_executor(None, lambda: create_crypto_wallet(
                        wallet_type=args.get("wallet_type", "ethereum")
                    ))
                elif action == "check_balance":
                    r = await loop.run_in_executor(None, lambda: check_wallet_balance(
                        wallet_address=args.get("wallet_address", ""),
                        currency=args.get("currency", "ETH")
                    ))
                elif action == "send_transaction":
                    r = await loop.run_in_executor(None, lambda: send_crypto_transaction(
                        from_address=args.get("wallet_address", ""),
                        to_address=args.get("to_address", ""),
                        amount=args.get("amount", ""),
                        currency=args.get("currency", "ETH")
                    ))
                elif action == "create_nft":
                    r = await loop.run_in_executor(None, lambda: create_nft(
                        metadata=args.get("metadata", {}),
                        wallet_address=args.get("wallet_address", "")
                    ))
                elif action == "smart_contract":
                    r = await loop.run_in_executor(None, lambda: interact_with_smart_contract(
                        contract_address=args.get("contract_address", ""),
                        function_name=args.get("function_name", ""),
                        parameters=args.get("parameters", {})
                    ))
                elif action == "track_prices":
                    r = await loop.run_in_executor(None, lambda: track_crypto_prices(
                        symbols=args.get("symbols", [])
                    ))
                elif action == "wallet_report":
                    r = await loop.run_in_executor(None, lambda: generate_wallet_report(
                        wallet_address=args.get("wallet_address", ""),
                        timeframe=args.get("timeframe", "last_month")
                    ))
                elif action == "setup_alerts":
                    r = await loop.run_in_executor(None, lambda: setup_crypto_alerts(
                        symbols=args.get("symbols", []),
                        conditions=args.get("conditions", [])
                    ))
                elif action == "analyze_data":
                    r = await loop.run_in_executor(None, lambda: analyze_blockchain_data(
                        contract_address=args.get("contract_address", ""),
                        timeframe=args.get("timeframe", "last_week")
                    ))
                result = r or "Blockchain crypto completed."

            elif name == "neural_network_training":
                action = args.get("action", "train_model")
                if action == "train_model":
                    r = await loop.run_in_executor(None, lambda: train_custom_model(
                        dataset_path=args.get("dataset_path", ""),
                        model_type=args.get("model_type", "classification")
                    ))
                elif action == "deploy_model":
                    r = await loop.run_in_executor(None, lambda: deploy_trained_model(
                        model_path=args.get("model_path", ""),
                        deployment_target=args.get("deployment_target", "local")
                    ))
                elif action == "fine_tune":
                    r = await loop.run_in_executor(None, lambda: fine_tune_existing_model(
                        base_model=args.get("base_model", ""),
                        new_data=args.get("new_data", [])
                    ))
                elif action == "analyze_performance":
                    r = await loop.run_in_executor(None, lambda: analyze_model_performance(
                        model_path=args.get("model_path", "")
                    ))
                elif action == "create_dataset":
                    r = await loop.run_in_executor(None, lambda: create_dataset_from_user_data(
                        data_sources=args.get("data_sources", [])
                    ))
                elif action == "optimize_hyperparams":
                    r = await loop.run_in_executor(None, lambda: optimize_model_hyperparameters(
                        model_path=args.get("model_path", ""),
                        search_space=args.get("search_space", {})
                    ))
                elif action == "export_mobile":
                    r = await loop.run_in_executor(None, lambda: export_model_for_mobile(
                        model_path=args.get("model_path", ""),
                        target_platform=args.get("target_platform", "android")
                    ))
                elif action == "monitor_drift":
                    r = await loop.run_in_executor(None, lambda: monitor_model_drift(
                        model_path=args.get("model_path", "")
                    ))
                elif action == "federated_learning":
                    r = await loop.run_in_executor(None, lambda: federated_learning_setup(
                        participants=args.get("participants", []),
                        model_architecture=args.get("model_architecture", {})
                    ))
                result = r or "Neural network training completed."

            elif name == "universal_translator":
                action = args.get("action", "translate_text")
                if action == "translate_text":
                    r = await loop.run_in_executor(None, lambda: translate_text(
                        text=args.get("text", ""),
                        source_lang=args.get("source_lang", ""),
                        target_lang=args.get("target_lang", ""),
                        context=args.get("context", "")
                    ))
                elif action == "voice_translate":
                    r = await loop.run_in_executor(None, lambda: real_time_voice_translation(
                        audio_stream=args.get("audio_stream", ""),
                        target_lang=args.get("target_lang", "")
                    ))
                elif action == "detect_lang":
                    r = await loop.run_in_executor(None, lambda: detect_language(
                        text=args.get("text", "")
                    ))
                elif action == "cultural_analysis":
                    r = await loop.run_in_executor(None, lambda: cultural_context_analysis(
                        text=args.get("text", ""),
                        source_culture=args.get("source_culture", ""),
                        target_culture=args.get("target_culture", "")
                    ))
                elif action == "translate_doc":
                    r = await loop.run_in_executor(None, lambda: translate_document(
                        document_path=args.get("document_path", ""),
                        target_lang=args.get("target_lang", "")
                    ))
                elif action == "create_memory":
                    r = await loop.run_in_executor(None, lambda: create_translation_memory(
                        text=args.get("text", ""),
                        translation=args.get("translation", ""),
                        domain=args.get("domain", "")
                    ))
                elif action == "batch_translate":
                    r = await loop.run_in_executor(None, lambda: batch_translate_texts(
                        texts=args.get("texts", []),
                        target_lang=args.get("target_lang", "")
                    ))
                elif action == "speech_translate":
                    r = await loop.run_in_executor(None, lambda: speech_to_speech_translation(
                        audio_input=args.get("audio_input", ""),
                        target_lang=args.get("target_lang", "")
                    ))
                elif action == "train_model":
                    r = await loop.run_in_executor(None, lambda: train_custom_translation_model(
                        training_data=args.get("training_data", []),
                        domain=args.get("domain", "")
                    ))
                elif action == "live_conversation":
                    r = await loop.run_in_executor(None, lambda: live_conversation_translation(
                        participants=args.get("participants", []),
                        languages=args.get("languages", [])
                    ))
                result = r or "Universal translator completed."

            elif name == "emotion_recognition":
                action = args.get("action", "analyze_text")
                if action == "analyze_text":
                    r = await loop.run_in_executor(None, lambda: analyze_text_emotion(
                        text=args.get("text", "")
                    ))
                elif action == "analyze_voice":
                    r = await loop.run_in_executor(None, lambda: analyze_voice_emotion(
                        audio_data=args.get("audio_data", "")
                    ))
                elif action == "analyze_facial":
                    r = await loop.run_in_executor(None, lambda: analyze_facial_emotion(
                        image_path=args.get("image_path", "")
                    ))
                elif action == "track_mood":
                    r = await loop.run_in_executor(None, lambda: track_mood_over_time(
                        timeframe=args.get("timeframe", "last_week")
                    ))
                elif action == "suggest_improvement":
                    r = await loop.run_in_executor(None, lambda: suggest_mood_improvement(
                        current_mood=args.get("current_mood", ""),
                        context=args.get("context", "")
                    ))
                elif action == "create_dashboard":
                    r = await loop.run_in_executor(None, lambda: create_emotion_dashboard(
                        user_id=args.get("user_id", "")
                    ))
                elif action == "real_time_monitor":
                    r = await loop.run_in_executor(None, lambda: real_time_emotion_monitoring(
                        activity_type=args.get("activity_type", "")
                    ))
                elif action == "recommendations":
                    r = await loop.run_in_executor(None, lambda: emotion_based_recommendations(
                        activity_type=args.get("activity_type", "")
                    ))
                elif action == "analyze_ei":
                    r = await loop.run_in_executor(None, lambda: analyze_emotional_intelligence(
                        text_or_audio=args.get("text_or_audio", "")
                    ))
                elif action == "mood_journal":
                    r = await loop.run_in_executor(None, lambda: mood_journaling_assistant(
                        entry_text=args.get("entry_text", "")
                    ))
                result = r or "Emotion recognition completed."

            elif name == "cross_app_automation":
                workflow_name = args.get("workflow_name", "")
                steps = args.get("steps", [])
                app_name = args.get("app_name", "")
                if workflow_name and steps:
                    self.cross_app_automation.create_workflow(workflow_name, steps)
                    result = f"Workflow '{workflow_name}' saved."
                elif workflow_name:
                    result = await self.cross_app_automation.execute_workflow(workflow_name)
                else:
                    result = await self.cross_app_automation.navigate_app_and_execute(
                        app_name=app_name,
                        navigation_steps=steps,
                        delay=float(args.get("delay", 0.5))
                    )

            elif name == "voice_system_control":
                action = args.get("action", "status").lower()
                if action == "restart_app":
                    r = await self.voice_system_control.restart_application(args.get("app_name", ""))
                elif action == "close_window":
                    r = await self.voice_system_control.close_window(args.get("app_name", ""))
                elif action == "open_app":
                    r = await self.voice_system_control.open_application(args.get("app_name", ""))
                elif action == "change_setting":
                    r = await self.voice_system_control.change_system_setting(
                        setting=args.get("setting", ""),
                        value=args.get("value", "")
                    )
                elif action == "restart_system":
                    r = await self.voice_system_control.restart_system(int(args.get("delay", 60)))
                elif action == "shutdown_system":
                    r = await self.voice_system_control.shutdown_system(int(args.get("delay", 60)))
                elif action == "lock":
                    r = await self.voice_system_control.lock_system()
                elif action == "sleep":
                    r = await self.voice_system_control.sleep_system()
                elif action == "list_apps":
                    r = await self.voice_system_control.list_running_apps()
                elif action == "status":
                    r = await self.voice_system_control.get_system_status()
                elif action == "toggle_wifi":
                    r = await self.voice_system_control.toggle_wifi(bool(args.get("value", True)))
                else:
                    r = f"Unknown voice system control action: {action}"
                result = r

            elif name == "ambient_awareness":
                action = args.get("action", "detect_scene")
                if action == "detect_scene":
                    r = await self.ambient_awareness.detect_scene(app_name=args.get("app_name"))
                elif action == "offer_help":
                    r = await self.ambient_awareness.offer_help()
                elif action == "get_status":
                    r = await self.ambient_awareness.get_ambient_status()
                elif action == "get_history":
                    r = await self.ambient_awareness.get_scene_history(minutes=int(args.get("minutes", 60)))
                elif action == "detect_inactivity":
                    r = await self.ambient_awareness.detect_inactivity(seconds=int(args.get("minutes", 300)))
                elif action == "suggest_action":
                    r = await self.ambient_awareness.suggest_action()
                else:
                    r = f"Unknown ambient awareness action: {action}"
                result = r

            elif name == "object_detection":
                action = args.get("action", "detect")
                angle = args.get("angle", "screen")
                image_data = None
                image = None
                try:
                    if angle == "camera":
                        raw, _ = _capture_camera()
                    else:
                        raw, _ = _capture_screen()
                    image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(raw)).convert("RGB")
                except Exception as e:
                    image = None
                    result = f"Could not capture image: {e}"
                if image is not None:
                    if action == "detect":
                        r = await self.object_detector.detect_objects(image)
                    elif action == "count":
                        r = await self.object_detector.count_objects(image, object_type=args.get("object_type"))
                    elif action == "highlight":
                        highlighted = await self.object_detector.highlight_object_type(image, object_type=args.get("object_type", "object"))
                        output_path = Path(__file__).resolve().parent / "photos" / f"object_highlight_{int(time.time())}.png"
                        output_path.parent.mkdir(exist_ok=True)
                        highlighted.save(output_path)
                        r = {"message": "Object highlight saved", "file": str(output_path)}
                    elif action == "track_motion":
                        try:
                            raw_prev, _ = _capture_screen() if angle == "screen" else _capture_camera()
                            prev_image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(raw_prev)).convert("RGB")
                            r = await self.object_detector.track_motion(prev_image, image)
                        except Exception as e:
                            r = f"Could not capture previous frame: {e}"
                    else:
                        r = f"Unknown object detection action: {action}"
                    result = r

            elif name == "ocr_text_extraction":
                action = args.get("action", "extract_text")
                image = None
                if args.get("file_path"):
                    try:
                        image = __import__("PIL.Image", fromlist=["Image"]).open(args.get("file_path")).convert("RGB")
                    except Exception as e:
                        image = None
                        result = f"Could not open image file: {e}"
                else:
                    try:
                        raw, _ = _capture_screen()
                        image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(raw)).convert("RGB")
                    except Exception as e:
                        image = None
                        result = f"Could not capture screen image: {e}"
                if image is not None:
                    if action == "extract_text":
                        r = await self.ocr_text_extractor.extract_text_from_image(image)
                    elif action == "find_errors":
                        r = await self.ocr_text_extractor.extract_error_messages(image)
                    elif action == "extract_code":
                        r = await self.ocr_text_extractor.extract_code_from_screen(image)
                    elif action == "extract_table":
                        r = await self.ocr_text_extractor.extract_table_data(image)
                    elif action == "find_urls":
                        r = await self.ocr_text_extractor.extract_urls(image)
                    elif action == "find_emails":
                        r = await self.ocr_text_extractor.extract_email_addresses(image)
                    elif action == "find_phones":
                        r = await self.ocr_text_extractor.extract_phone_numbers(image)
                    elif action == "highlight_text":
                        r_image = await self.ocr_text_extractor.highlight_text_on_image(image, args.get("search_text", ""))
                        r = "Text highlighted on image." if r_image else "Failed to highlight text."
                    elif action == "read_log":
                        r = await self.ocr_text_extractor.read_log_file(args.get("file_path", ""), search_patterns=args.get("search_patterns", []))
                    else:
                        r = f"Unknown OCR action: {action}"
                    result = r

            elif name == "gesture_recognition":
                action = args.get("action", "detect_hand")
                image = None
                if args.get("file_path"):
                    try:
                        image = __import__("PIL.Image", fromlist=["Image"]).open(args.get("file_path")).convert("RGB")
                    except Exception as e:
                        image = None
                        result = f"Could not open image file: {e}"
                else:
                    try:
                        raw, _ = _capture_camera()
                        image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(raw)).convert("RGB")
                    except Exception as e:
                        image = None
                        result = f"Could not capture camera image: {e}"
                if image is not None:
                    if action == "detect_hand":
                        r = await self.gesture_recognizer.detect_hand_gesture(image)
                    elif action == "detect_body":
                        r = await self.gesture_recognizer.detect_body_gesture(image)
                    elif action == "detect_swipe":
                        raw_prev, _ = _capture_camera()
                        prev_image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(raw_prev)).convert("RGB")
                        r = await self.gesture_recognizer.detect_swipe_gesture(prev_image, image)
                    elif action == "detect_click":
                        r = await self.gesture_recognizer.detect_click_gesture(image)
                    elif action == "get_history":
                        r = await self.gesture_recognizer.get_gesture_history()
                    else:
                        r = f"Unknown gesture recognition action: {action}"
                    result = r

            elif name == "real_time_annotation":
                action = args.get("action", "annotate_screen")
                annotations = args.get("annotations", [])
                insights = args.get("insights", [])
                position = args.get("position", "top_right")
                image = None
                if args.get("file_path"):
                    try:
                        image = __import__("PIL.Image", fromlist=["Image"]).open(args.get("file_path")).convert("RGB")
                    except Exception as e:
                        image = None
                        result = f"Could not open image file: {e}"
                else:
                    try:
                        raw, _ = _capture_screen()
                        image = __import__("PIL.Image", fromlist=["Image"]).open(io.BytesIO(raw)).convert("RGB")
                    except Exception as e:
                        image = None
                        result = f"Could not capture screen image: {e}"
                if image is not None:
                    if action == "annotate_screen":
                        annotated = await self.annotation_overlay.annotate_screen(image, annotations)
                        output_path = Path(__file__).resolve().parent / "photos" / f"annotation_{int(time.time())}.png"
                        output_path.parent.mkdir(exist_ok=True)
                        annotated.save(output_path)
                        r = {"message": "Screen annotated", "file": str(output_path)}
                    elif action == "create_insight_panel":
                        annotated = await self.annotation_overlay.create_insight_overlay(image, insights, position=position)
                        output_path = Path(__file__).resolve().parent / "photos" / f"insight_{int(time.time())}.png"
                        output_path.parent.mkdir(exist_ok=True)
                        annotated.save(output_path)
                        r = {"message": "Insight overlay created", "file": str(output_path)}
                    elif action == "create_debug_overlay":
                        r = await self.annotation_overlay.create_debug_overlay(image, args.get("debug_info", {}))
                        output_path = Path(__file__).resolve().parent / "photos" / f"debug_{int(time.time())}.png"
                        output_path.parent.mkdir(exist_ok=True)
                        r.save(output_path)
                        r = {"message": "Debug overlay created", "file": str(output_path)}
                    elif action == "create_heatmap":
                        heatmap_data = np.array(args.get("heatmap_data", []), dtype=np.uint8)
                        annotated = await self.annotation_overlay.create_heatmap_overlay(image, heatmap_data, alpha=float(args.get("alpha", 0.5)))
                        output_path = Path(__file__).resolve().parent / "photos" / f"heatmap_{int(time.time())}.png"
                        output_path.parent.mkdir(exist_ok=True)
                        annotated.save(output_path)
                        r = {"message": "Heatmap overlay created", "file": str(output_path)}
                    elif action == "get_statistics":
                        r = await self.annotation_overlay.get_annotation_statistics()
                    else:
                        r = f"Unknown real time annotation action: {action}"
                    result = r

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        # Restore UI state after tool execution. If muted, show MUTED instead
        # of leaving the UI stuck in THINKING.
        self.ui.set_state("MUTED" if self.ui.muted else "LISTENING")

        print(f"[JARVIS] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    def _is_service_unavailable_error(self, exc: Exception) -> bool:
        if exc is None:
            return False
        status_code = getattr(exc, 'status_code', None)
        if status_code == 1011:
            return True
        class_name = exc.__class__.__name__
        if class_name == 'ConnectionClosedError':
            return True
        message = str(exc).lower()
        if 'service is currently unavailable' in message or 'received 1011' in message:
            return True
        if isinstance(exc, BaseExceptionGroup):
            for sub in exc.exceptions:
                if self._is_service_unavailable_error(sub):
                    return True
        return False

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        print("[JARVIS] 🎤 Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            if self.ui.muted:
                return
            
            # Continue streaming audio even when paused so we can detect wake-word or "Jarvis, listen now" overrides.
            context_info = self.audio_context_mgr.get_current_context()
            data = indata.tobytes()
            loop.call_soon_threadsafe(
                self.out_queue.put_nowait,
                {"data": data, "mime_type": "audio/pcm"}
            )

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                print("[JARVIS] 🎤 Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[JARVIS] ❌ Mic: {e}")
            raise

    async def _receive_audio(self):
        print("[JARVIS] 👂 Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                async for response in self.session.receive():
                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)
                                if (self.transcription_mgr and 
                                    self.transcription_mgr._initialized and 
                                    self.transcription_mgr.overlay and 
                                    self.transcription_mgr.overlay.isVisible()):
                                    self.transcription_mgr.add_output_transcription(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                normalized_txt = txt.strip().lower()
                                if not self.audio_context_mgr.should_listen() and not self._wake_word_is_or_manual_override_active():
                                    if "jarvis listen now" in normalized_txt:
                                        self._activate_manual_listen(duration=30)
                                        continue
                                    if self._contains_wake_word(txt):
                                        self._activate_wake_word()
                                        if normalized_txt == "jarvis":
                                            continue
                                    else:
                                        continue

                                in_buf.append(txt)
                                if (self.transcription_mgr and 
                                    self.transcription_mgr._initialized and 
                                    self.transcription_mgr.overlay and 
                                    self.transcription_mgr.overlay.isVisible()):
                                    self.transcription_mgr.add_input_transcription(txt)
                                if self._is_stop_phrase(txt):
                                    await self._request_stop()
                                    in_buf = []
                                    out_buf = []
                                    continue

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                full_in_lower = full_in.strip().lower()
                                if self._contains_wake_word(full_in) and full_in_lower == "jarvis":
                                    self.ui.write_log("SYS: Wake word recognized. Awaiting your next command.")
                                    in_buf = []
                                    out_buf = []
                                    continue

                                if full_in_lower.startswith("jarvis "):
                                    command_text = full_in[len("jarvis "):].strip()
                                    if command_text:
                                        loop = asyncio.get_running_loop()
                                        result = await loop.run_in_executor(
                                            None,
                                            lambda: discord_speak_in_voice_channel(command_text)
                                        )
                                        self.ui.write_log(f"Discord voice command: {result}")
                                        in_buf = []
                                        out_buf = []
                                        continue

                                    self.ui.write_log(f"You: {full_in}")
                            if self._is_stop_phrase(full_in):
                                await self._request_stop()
                                in_buf = []
                                out_buf = []
                                continue
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                            out_buf = []

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[JARVIS] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            if self._is_service_unavailable_error(e):
                print("[JARVIS] ❌ Recv: Gemini live service unavailable. Reconnecting...")
            else:
                print(f"[JARVIS] ❌ Recv: {e}")
                traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[JARVIS] 🔊 Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                if self._stop_requested.is_set():
                    self._drain_audio_queue()
                    self._stop_requested.clear()
                    self.set_speaking(False)
                    continue

                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)
        except Exception as e:
            print(f"[JARVIS] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        while True:
            try:
                print("[JARVIS] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()

                    print("[JARVIS] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: JARVIS online.")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except Exception as e:
                if self._is_service_unavailable_error(e):
                    print("[JARVIS] ⚠️ Gemini live service unavailable. Reconnecting in 3s...")
                else:
                    print(f"[JARVIS] ⚠️ {e}")
                    traceback.print_exc()
            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[JARVIS] 🔄 Reconnecting in 3s...")
            await asyncio.sleep(3)


def _restart_program(reason: str):
    print(f"[MAIN] 🔁 Restarting Jarvis due to: {reason}")
    time.sleep(2)
    restart_count = int(os.environ.get("JARVIS_RESTART_COUNT", "0")) + 1
    if restart_count > 5:
        print("[MAIN] Too many automatic restarts, aborting.")
        sys.exit(1)
    os.environ["JARVIS_RESTART_COUNT"] = str(restart_count)

    script_path = None
    if len(sys.argv) > 0:
        arg0 = os.path.abspath(sys.argv[0])
        if os.path.isfile(arg0) and arg0.lower().endswith(".py"):
            script_path = arg0
    if not script_path:
        script_path = os.path.abspath(__file__)
    if not script_path:
        print("[MAIN] ERROR: Could not determine script path for restart.")
        sys.exit(1)

    print(f"[MAIN] Restarting from python={sys.executable} script={script_path}")
    os.chdir(os.path.dirname(script_path))
    os.execv(sys.executable, [sys.executable, script_path] + sys.argv[1:])


def _start_remote_server(ui: JarvisUI):
    if hasattr(ui, "_set_remote_urls"):
        print("[MAIN] _set_remote_urls method found on UI")

        def _remote_command(command: str) -> None:
            ui.write_log(f"SYS: Remote command received: {command}")
            if getattr(ui, "on_text_command", None):
                threading.Thread(target=ui.on_text_command, args=(command,), daemon=True).start()
            else:
                ui.write_log("SYS: Remote command handler not available.")

        try:
            print("[MAIN] Starting remote server...")
            local_url, public_url = start_remote_server(command_callback=_remote_command)
            print(f"[MAIN] Remote server started: local={local_url}, public={public_url}")
            ui._set_remote_urls(local_url, public_url, "Remote control active")
            print("[MAIN] _set_remote_urls called")
            ui.write_log(f"SYS: Remote URL active at {public_url or local_url}")
        except Exception as exc:
            print(f"[MAIN] Remote server failed: {exc}")
            traceback.print_exc()
            ui.write_log(f"SYS: Remote control server failed: {exc}")
    else:
        print("[MAIN] WARNING: _set_remote_urls method NOT found on UI")


def _start_discord(ui: JarvisUI):
    try:
        bot = get_discord_bot()
        bot.set_status_callback(ui.set_discord_status)
        bot.set_poll_image_picker_callback(ui.open_poll_image_picker)
        ui.set_discord_restart_callback(bot.restart_bot)

        def _toggle_bot():
            try:
                if getattr(bot, 'is_running', False):
                    ui.set_discord_status("STOPPING")
                    bot.stop_bot()
                    ui.set_discord_status("OFFLINE")
                else:
                    ui.set_discord_status("STARTING")
                    bot.ensure_running()
            except Exception as exc:
                print(f"[MAIN] Discord toggle error: {exc}")

        ui.set_discord_toggle_callback(lambda: threading.Thread(target=_toggle_bot, daemon=True).start())
        bot.ensure_running()

        def _sync_discord_commands():
            try:
                bot.sync_commands(timeout=120.0)
                ui.write_log("SYS: Discord slash commands sync requested.")
            except Exception as exc:
                print(f"[MAIN] Discord sync error: {type(exc).__name__}: {exc}")
                ui.write_log(f"SYS: Discord sync failed: {type(exc).__name__}: {exc}")

        ui.set_discord_sync_callback(lambda: threading.Thread(target=_sync_discord_commands, daemon=True).start())

        def _sync_on_startup():
            while not getattr(bot, '_is_ready', False):
                time.sleep(1.0)
            try:
                bot.sync_commands(timeout=120.0)
                ui.write_log("SYS: Discord slash commands sync requested on startup.")
            except Exception as exc:
                print(f"[MAIN] Discord startup sync error: {type(exc).__name__}: {exc}")
                ui.write_log(f"SYS: Discord startup sync failed: {type(exc).__name__}: {exc}")

        threading.Thread(target=_sync_on_startup, daemon=True).start()
    except Exception as e:
        print(f"[MAIN] Could not start Discord bot: {e}")
        ui.set_discord_status("OFFLINE")


def _run_jarvis(ui: JarvisUI):
    ui.wait_for_api_key()
    jarvis = JarvisLive(ui)
    try:
        asyncio.run(jarvis.run())
    except KeyboardInterrupt:
        print("\n🔴 Shutting down Jarvis thread...")
    except Exception as exc:
        print(f"[MAIN] Jarvis runtime failure: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        _restart_program("Jarvis runtime failure")


def main():
    print(f"[MAIN] python executable: {sys.executable}")
    print(f"[MAIN] working directory: {os.getcwd()}")
    ui = JarvisUI("face.png")

    print("[MAIN] UI initialized, starting services...")
    _start_remote_server(ui)
    _start_discord(ui)

    jarvis_thread = threading.Thread(target=_run_jarvis, args=(ui,), daemon=True)
    jarvis_thread.start()

    if hasattr(ui, '_app') and getattr(ui._app, 'aboutToQuit', None) is not None:
        ui._app.aboutToQuit.connect(lambda: print("[MAIN] UI quitting, restarting Jarvis..."))

    ui.root.mainloop()
    print("[MAIN] UI mainloop ended, restarting Jarvis...")
    _restart_program("UI closed or failed")

if __name__ == "__main__":
    main()