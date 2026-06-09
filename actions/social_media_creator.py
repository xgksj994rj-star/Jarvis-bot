import json
import os
import sys
import subprocess
import threading
import time
import uuid
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "content"
THUMBNAIL_DIR = OUTPUT_DIR / "thumbnails"
CONFIG_DIR = BASE_DIR / "config"
YOUTUBE_CREDENTIALS = CONFIG_DIR / "youtube_credentials.json"
YOUTUBE_SECRETS = CONFIG_DIR / "youtube_oauth_client_secrets.json"
SCHEDULE_FILE = CONFIG_DIR / "social_publish_schedule.json"
ANALYTICS_FILE = CONFIG_DIR / "social_analytics.json"
OUTPUT_DIR.mkdir(exist_ok=True)
THUMBNAIL_DIR.mkdir(exist_ok=True)
CONFIG_DIR.mkdir(exist_ok=True)

YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

LOCK = threading.Lock()


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get_api_keys() -> dict:
    return _read_json(CONFIG_DIR / "api_keys.json", {})


def _open_url(url: str) -> None:
    try:
        if sys.platform.startswith("darwin"):
            subprocess.Popen(["open", url])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", url])
        else:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
    except Exception:
        pass


def _save_text_asset(name: str, content: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "_".join([p for p in name.lower().split() if p.isalnum()])[:48] or "asset"
    path = OUTPUT_DIR / f"{safe_name}_{ts}.txt"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _generate_ai_text(prompt: str) -> str:
    try:
        import google.generativeai as genai
        api_key = _get_api_keys().get("gemini_api_key")
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name="gemini-2.5-flash")
            response = model.generate_content(prompt)
            return response.text.strip()
    except Exception:
        pass

    return f"AI generation unavailable. Please provide this prompt to your model: {prompt}"


def _create_placeholder_thumbnail(prompt: str) -> str:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return ""

    width, height = 1280, 720
    image = Image.new("RGB", (width, height), (18, 24, 34))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except Exception:
        font = ImageFont.load_default()

    text = prompt or "Faceless AI video"
    lines = []
    for part in text.split(" - "):
        lines.extend(partwrap(part, width=30))
    y = 120
    for line in lines[:6]:
        w, h = draw.textsize(line, font=font)
        draw.text(((width - w) / 2, y), line, font=font, fill=(255, 255, 255))
        y += h + 14

    thumb_path = THUMBNAIL_DIR / f"placeholder_thumbnail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    image.save(thumb_path)
    return str(thumb_path)


def partwrap(text: str, width: int = 30) -> list[str]:
    words = text.split()
    lines = []
    line = ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            lines.append(line.strip())
            line = word + " "
        else:
            line += word + " "
    if line:
        lines.append(line.strip())
    return lines


def _make_thumbnail(prompt: str) -> str:
    try:
        from actions.image_generator import generate_image_dalle
        image_path = generate_image_dalle(prompt, style="minimal", size="1280x720")
        if image_path and Path(image_path).exists():
            return image_path
    except Exception:
        pass
    return _create_placeholder_thumbnail(prompt)


def _get_ffmpeg_path() -> str | None:
    for name in ("ffmpeg", "ffmpeg.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _synthesize_audio(text: str, output_path: Path) -> str | None:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        return str(output_path) if output_path.exists() else None
    except Exception:
        return None


def _make_video_from_image_and_audio(image_path: str, audio_path: str, output_path: Path) -> str | None:
    ffmpeg = _get_ffmpeg_path()
    if not ffmpeg:
        return None

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [
            ffmpeg,
            "-y",
            "-loop", "1",
            "-framerate", "2",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ]
        subprocess.run(command, capture_output=True, text=True, check=True)
        return str(output_path) if output_path.exists() else None
    except Exception:
        return None


def _generate_video_title(platform: str, niche: str) -> str:
    prompt = (
        f"Write one clickable video title for a faceless {platform} channel in the '{niche}' niche. "
        "Use a hook that is easy to produce with AI visuals and voiceover only."
    )
    result = _generate_ai_text(prompt)
    return result.split("\n")[0].strip() if result else f"Faceless {platform} video"


def _generate_video_script(platform: str, title: str, niche: str) -> str:
    prompt = (
        f"Write a voiceover script for a faceless {platform} video titled '{title}' in the '{niche}' niche. "
        "Use simple narration, short paragraphs, and include a compelling hook, main value, and call to action. "
        "Keep it under 250 words."
    )
    return _generate_ai_text(prompt)


def _create_auto_video_assets(parameters: dict, speak) -> dict:
    platform = parameters.get("platform", "youtube").lower().strip()
    niche = parameters.get("niche", "AI faceless content").strip()
    title = parameters.get("title") or _generate_video_title(platform, niche)
    script = parameters.get("script") or _generate_video_script(platform, title, niche)
    thumbnail_prompt = parameters.get("thumbnail_prompt") or title

    safe_name = "_".join([p for p in title.lower().split() if p.isalnum()])[:36] or "video"
    base_path = OUTPUT_DIR / safe_name
    base_path.parent.mkdir(parents=True, exist_ok=True)

    script_path = OUTPUT_DIR / f"{safe_name}_script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    script_path.write_text(script, encoding="utf-8")

    thumbnail_path = _make_thumbnail(thumbnail_prompt)
    audio_path = OUTPUT_DIR / f"{safe_name}_audio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
    audio_file = _synthesize_audio(script, Path(audio_path))
    if not audio_file:
        raise RuntimeError("Audio synthesis failed. Ensure pyttsx3 is installed and working.")

    video_path = OUTPUT_DIR / f"{safe_name}_video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
    final_video = _make_video_from_image_and_audio(thumbnail_path, audio_file, video_path)
    if not final_video:
        raise RuntimeError("Video creation failed. Ensure ffmpeg is installed and on PATH.")

    return {
        "title": title,
        "script_path": str(script_path),
        "thumbnail_path": thumbnail_path,
        "audio_path": audio_file,
        "video_path": final_video,
        "script": script
    }


def _create_and_publish_video(parameters: dict, player, speak) -> str:
    try:
        assets = _create_auto_video_assets(parameters, speak)
    except Exception as e:
        return f"Auto video creation failed: {e}"

    if speak:
        speak("I created your video assets and am ready to publish.")

    if not parameters.get("scheduled_run") and (parameters.get("publish_time") or parameters.get("recurrence")):
        publish_params = {
            "platform": parameters.get("platform", "youtube"),
            "publish_time": parameters.get("publish_time"),
            "title": assets["title"],
            "description": parameters.get("description", ""),
            "tags": parameters.get("tags", ""),
            "privacy": parameters.get("privacy", "public"),
            "channel": parameters.get("channel", ""),
            "file_path": assets["video_path"],
            "action": "schedule_publish",
            "recurrence": parameters.get("recurrence"),
            "auto_create": True
        }
        return _schedule_publish(publish_params, player, speak)

    if parameters.get("platform", "youtube").lower() == "tiktok":
        publish_params = {**parameters, "file_path": assets["video_path"]}
        return _publish_tiktok_video(publish_params, player, speak)

    publish_params = {**parameters, "file_path": assets["video_path"], "title": assets["title"]}
    return _upload_youtube_video(publish_params, player, speak)


def _schedule_publish(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower()
    publish_time = parameters.get("publish_time") or parameters.get("publish_datetime")
    if not publish_time:
        return "Provide publish_time in ISO format, e.g. 2026-06-04T15:30 or 2026-06-04 15:30."

    parsed = _parse_publish_time(str(publish_time))
    if not parsed:
        return "Could not parse publish_time. Use ISO format like 2026-06-04T15:30 or 2026-06-04 15:30."

    action = "auto_publish" if parameters.get("auto_create") else "upload"
    file_path = parameters.get("file_path") or parameters.get("path")
    if action == "upload" and platform == "youtube" and not file_path:
        return "You must provide a file_path for scheduled YouTube upload."

    entry = {
        "id": str(uuid.uuid4()),
        "platform": platform,
        "action": action,
        "publish_time": parsed.isoformat(),
        "file_path": file_path,
        "title": parameters.get("title", ""),
        "description": parameters.get("description", ""),
        "tags": parameters.get("tags", ""),
        "privacy": parameters.get("privacy", "public"),
        "status": "pending",
        "recurrence": parameters.get("recurrence", ""),
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    if action == "auto_publish":
        entry["niche"] = parameters.get("niche", "AI faceless content")
        entry["thumbnail_prompt"] = parameters.get("thumbnail_prompt", parameters.get("title", entry["title"]))

    entries = _load_schedule_data()
    entries.append(entry)
    _save_schedule_data(entries)
    if speak:
        speak(f"Scheduled {platform} publish for {parsed.isoformat()}.")
    return f"Scheduled publish created (ID: {entry['id']}) for {parsed.isoformat()}."


def _save_schedule_data(entries: list[dict]) -> None:
    _write_json(SCHEDULE_FILE, entries)


def _load_schedule_data() -> list[dict]:
    return _read_json(SCHEDULE_FILE, [])


def _load_analytics_data() -> dict:
    return _read_json(ANALYTICS_FILE, {"youtube": {}, "tiktok": {}})


def _save_analytics_data(data: dict) -> None:
    _write_json(ANALYTICS_FILE, data)


def _build_client_secrets_from_config() -> bool:
    keys = _get_api_keys()
    client_id = keys.get("youtube_client_id")
    client_secret = keys.get("youtube_client_secret")
    if not client_id or not client_secret:
        return False

    data = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }
    _write_json(YOUTUBE_SECRETS, data)
    return True


def _get_youtube_credentials():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = None
        if YOUTUBE_CREDENTIALS.exists():
            creds = Credentials.from_authorized_user_file(str(YOUTUBE_CREDENTIALS), YOUTUBE_SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_youtube_credentials(creds)
        return creds
    except Exception:
        return None


def _save_youtube_credentials(creds: Any) -> None:
    try:
        _write_json(YOUTUBE_CREDENTIALS, json.loads(creds.to_json()))
    except Exception:
        pass


def _authorize_youtube(parameters: dict, player, speak) -> str:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except Exception:
        return "Google OAuth libraries are not installed. Install google-auth-oauthlib."

    if not YOUTUBE_SECRETS.exists():
        if not _build_client_secrets_from_config():
            return (
                "Missing YouTube OAuth client secrets. Add youtube_client_id and youtube_client_secret "
                "to config/api_keys.json or place a valid youtube_oauth_client_secrets.json in config/."
            )

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(YOUTUBE_SECRETS), YOUTUBE_SCOPES)
        creds = flow.run_local_server(port=0)
        _save_youtube_credentials(creds)
        return "YouTube authorization complete and credentials saved."
    except Exception as e:
        return f"YouTube authorization failed: {e}"


def _get_youtube_client():
    try:
        from googleapiclient.discovery import build
        creds = _get_youtube_credentials()
        if not creds:
            return None, "YouTube credentials are missing or expired. Run action authorize_youtube first."
        youtube = build("youtube", "v3", credentials=creds)
        return youtube, None
    except Exception as e:
        return None, f"Failed to initialize YouTube client: {e}"


def _upload_youtube_video(parameters: dict, player, speak) -> str:
    video_path = parameters.get("file_path") or parameters.get("path")
    if not video_path:
        return "No video file provided. Use file_path to specify the video to upload."

    video_path = Path(video_path).expanduser().resolve()
    if not video_path.exists() or not video_path.is_file():
        return f"Video file not found: {video_path}"

    title = parameters.get("title") or video_path.stem
    description = parameters.get("description", "")
    tags = [tag.strip() for tag in str(parameters.get("tags", "")).split(",") if tag.strip()]
    privacy = parameters.get("privacy", "public").lower()
    if privacy not in {"public", "unlisted", "private"}:
        privacy = "public"

    youtube, error = _get_youtube_client()
    if error:
        return error

    try:
        from googleapiclient.http import MediaFileUpload

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
            },
            "status": {
                "privacyStatus": privacy
            }
        }
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = request.execute()
        video_id = response.get("id")
        if not video_id:
            return "YouTube upload completed but no video ID was returned."

        record = {
            "title": title,
            "description": description,
            "tags": tags,
            "privacy": privacy,
            "channel": parameters.get("channel", ""),
            "uploaded_at": datetime.utcnow().isoformat() + "Z",
            "file_path": str(video_path)
        }
        _record_analytics("youtube", video_id, {"metadata": record})
        url = f"https://youtu.be/{video_id}"
        if speak:
            speak(f"Video uploaded to YouTube. Video ID {video_id}.")
        return f"Uploaded YouTube video: {url}"
    except Exception as e:
        return f"YouTube upload failed: {e}"


def _get_youtube_video_stats(video_id: str) -> dict | None:
    youtube, error = _get_youtube_client()
    if error:
        return None
    try:
        request = youtube.videos().list(part="snippet,statistics", id=video_id)
        response = request.execute()
        items = response.get("items", [])
        if not items:
            return None
        return items[0]
    except Exception:
        return None


def _record_analytics(platform: str, video_id: str, metrics: dict, note: str = "") -> None:
    analytics = _load_analytics_data()
    if platform not in analytics:
        analytics[platform] = {}
    record = analytics[platform].get(video_id, {})
    record["updated_at"] = datetime.utcnow().isoformat() + "Z"
    record["note"] = note or record.get("note", "")
    record["metrics"] = metrics
    analytics[platform][video_id] = record
    _save_analytics_data(analytics)


def _handle_youtube_analytics(parameters: dict, player, speak) -> str:
    video_id = parameters.get("video_id")
    if not video_id:
        return "Provide a video_id to fetch analytics for a YouTube video."

    video_data = _get_youtube_video_stats(video_id)
    if not video_data:
        return f"Could not fetch analytics for YouTube video {video_id}."

    snippet = video_data.get("snippet", {})
    stats = video_data.get("statistics", {})
    record = {
        "title": snippet.get("title"),
        "channel_title": snippet.get("channelTitle"),
        "statistics": stats
    }
    _record_analytics("youtube", video_id, record)

    summary_lines = [
        f"Title: {record['title']}",
        f"Channel: {record['channel_title']}",
        f"Views: {stats.get('viewCount', '0')}",
        f"Likes: {stats.get('likeCount', '0')}",
        f"Comments: {stats.get('commentCount', '0')}",
        f"Favorites: {stats.get('favoriteCount', '0')}",
        f"Shares: {stats.get('shareCount', '0') if stats.get('shareCount') is not None else 'N/A'}"
    ]
    if speak:
        speak("YouTube analytics fetched and saved.")
    return "\n".join(summary_lines)


def _handle_analytics_summary(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower()
    analytics = _load_analytics_data()
    platform_data = analytics.get(platform, {})

    if not platform_data:
        return f"No analytics stored for {platform}."

    lines = [f"{platform.title()} analytics summary:"]
    for video_id, record in list(platform_data.items())[:10]:
        stats = record.get("metrics", {})
        title = stats.get("title") or stats.get("metadata", {}).get("title") or "Unknown"
        view_count = stats.get("statistics", {}).get("viewCount") or stats.get("metadata", {}).get("views") or "N/A"
        lines.append(f"{video_id}: {title} — Views: {view_count}")
    if speak:
        speak("Here is the analytics summary for your channel.")
    return "\n".join(lines)


def _tiktok_open_upload_page(parameters: dict, player, speak) -> str:
    _open_url("https://www.tiktok.com/upload")
    video_path = parameters.get("file_path") or parameters.get("path")
    message = "Opened TikTok upload page. "
    if video_path:
        message += f"Your generated video is ready at {video_path}. "
    message += "Complete the upload manually or configure TikTok API credentials in config/api_keys.json."
    if speak:
        speak(message)
    return message


def _publish_tiktok_video(parameters: dict, player, speak) -> str:
    keys = _get_api_keys()
    access_token = keys.get("tiktok_access_token")
    open_id = keys.get("tiktok_open_id")
    video_path = parameters.get("file_path") or parameters.get("path")
    if access_token and open_id and video_path:
        try:
            import requests
            url = f"https://open-api.tiktok.com/video/create/?open_id={open_id}&access_token={access_token}"
            with open(video_path, "rb") as video_file:
                files = {"video": video_file}
                response = requests.post(url, files=files)
            result = response.json()
            if result.get("data"):
                video_id = result["data"].get("video_id")
                _record_analytics("tiktok", video_id, {"upload_response": result})
                return f"TikTok video uploaded via API. Video ID: {video_id}."
            return f"TikTok upload API response: {result}"
        except Exception as e:
            return f"TikTok API publish failed: {e}"
    if not video_path:
        return "No local video file found for TikTok publish. Please generate assets first."
    return _tiktok_open_upload_page(parameters, player, speak)


def _parse_publish_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        pass
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except Exception:
        pass
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except Exception:
        pass
    return None


def _advance_recurrence(target: datetime, recurrence: str) -> datetime:
    recurrence = str(recurrence).lower().strip()
    if recurrence == "daily":
        return target + timedelta(days=1)
    if recurrence == "weekly":
        return target + timedelta(weeks=1)
    if recurrence == "monthly":
        month = target.month + 1
        year = target.year
        if month > 12:
            month = 1
            year += 1
        day = min(target.day, 28)
        return target.replace(year=year, month=month, day=day)
    return target + timedelta(days=1)


def _run_schedule_loop() -> None:
    while True:
        try:
            now = datetime.now()
            updated = False
            entries = _load_schedule_data()
            for entry in entries:
                if entry.get("status") != "pending":
                    continue
                target = _parse_publish_time(entry.get("publish_time", ""))
                if target and target <= now:
                    entry["status"] = "running"
                    _save_schedule_data(entries)
                    result = _execute_schedule_entry(entry)
                    entry["result"] = result
                    entry["executed_at"] = datetime.utcnow().isoformat() + "Z"
                    recurrence = entry.get("recurrence", "")
                    if recurrence:
                        entry["publish_time"] = _advance_recurrence(target, recurrence).isoformat()
                        entry["status"] = "pending"
                        entry["last_run"] = result
                    else:
                        entry["status"] = "completed" if "failed" not in result.lower() else "failed"
                    updated = True
            if updated:
                _save_schedule_data(entries)
        except Exception:
            pass
        time.sleep(60)

_SCHEDULER_THREAD = threading.Thread(target=_run_schedule_loop, daemon=True)
_SCHEDULER_THREAD.start()


def _execute_schedule_entry(entry: dict) -> str:
    platform = entry.get("platform", "youtube").lower()
    if entry.get("action") == "auto_publish":
        entry["scheduled_run"] = True
        return _create_and_publish_video(entry, None, None)
    if platform == "tiktok":
        return _publish_tiktok_video(entry, None, None)
    return _upload_youtube_video(entry, None, None)


def _schedule_publish(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower()
    publish_time = parameters.get("publish_time") or parameters.get("publish_datetime")
    if not publish_time:
        return "Provide publish_time in ISO format, e.g. 2026-06-04T15:30 or 2026-06-04 15:30."

    parsed = _parse_publish_time(str(publish_time))
    if not parsed:
        return "Could not parse publish_time. Use ISO format like 2026-06-04T15:30 or 2026-06-04 15:30."

    action = "auto_publish" if parameters.get("auto_create") else "upload"
    file_path = parameters.get("file_path") or parameters.get("path")
    if action == "upload" and platform == "youtube" and not file_path:
        return "You must provide a file_path for scheduled YouTube upload."

    entry = {
        "id": str(uuid.uuid4()),
        "platform": platform,
        "action": action,
        "publish_time": parsed.isoformat(),
        "file_path": file_path,
        "title": parameters.get("title", ""),
        "channel": parameters.get("channel", ""),
        "description": parameters.get("description", ""),
        "tags": parameters.get("tags", ""),
        "privacy": parameters.get("privacy", "public"),
        "status": "pending",
        "recurrence": parameters.get("recurrence", ""),
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    if action == "auto_publish":
        entry["niche"] = parameters.get("niche", "AI faceless content")
        entry["thumbnail_prompt"] = parameters.get("thumbnail_prompt", parameters.get("title", entry["title"]))

    entries = _load_schedule_data()
    entries.append(entry)
    _save_schedule_data(entries)
    if speak:
        speak(f"Scheduled {platform} publish for {parsed.isoformat()}.")
    return f"Scheduled publish created (ID: {entry['id']}) for {parsed.isoformat()}."


def _list_schedules(parameters: dict, player, speak) -> str:
    entries = _load_schedule_data()
    if not entries:
        return "No scheduled social media publishes found."

    lines = []
    for entry in entries:
        channel_info = f" | channel: {entry.get('channel')}" if entry.get("channel") else ""
        title_info = f" | title: {entry.get('title')}" if entry.get("title") else ""
        lines.append(
            f"ID: {entry['id']} | platform: {entry['platform']} | publish_time: {entry['publish_time']} | status: {entry['status']}{title_info}{channel_info}"
        )
    return "\n".join(lines)


def _cancel_schedule(parameters: dict, player, speak) -> str:
    entry_id = parameters.get("id") or parameters.get("schedule_id")
    if not entry_id:
        return "Provide the scheduled publish id to cancel."

    entries = _load_schedule_data()
    found = False
    for entry in entries:
        if entry.get("id") == entry_id and entry.get("status") == "pending":
            entry["status"] = "cancelled"
            found = True
            break

    if not found:
        return f"No pending scheduled publish found for id {entry_id}."

    _save_schedule_data(entries)
    return f"Cancelled scheduled publish {entry_id}."


def _handle_strategy(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower().strip()
    niche = parameters.get("niche", "AI faceless content").strip()
    prompt = (
        f"Create a fast-start strategy for building a faceless {platform} channel in the '{niche}' niche. "
        "Include 5 video ideas, a posting cadence, a content format, and growth tactics. "
        "Keep it practical and suitable for automated content generation."
    )
    result = _generate_ai_text(prompt)
    path = _save_text_asset(f"strategy_{platform}_{niche}", result)
    if speak:
        speak("I created a channel strategy and saved it to your content folder.")
    return f"Strategy generated and saved: {path}"


def _handle_idea(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower().strip()
    niche = parameters.get("niche", "AI faceless content").strip()
    count = int(parameters.get("count", 5))
    prompt = (
        f"Generate {count} faceless {platform} video ideas for a channel in the '{niche}' niche. "
        "Each idea should include a clickable title and a short hook."
    )
    result = _generate_ai_text(prompt)
    path = _save_text_asset(f"ideas_{platform}_{niche}", result)
    if speak:
        speak("I generated your video ideas and saved them to the content folder.")
    return f"Ideas generated and saved: {path}"


def _handle_script(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower().strip()
    title = parameters.get("title", "Faceless AI video").strip()
    length = parameters.get("length", "short").strip()
    instruction = (
        f"Write a {length} spoken script for a faceless {platform} video titled '{title}'. "
        "Use concise, engaging language and include a clear hook, value sections, and a call to action. "
        "Make it suitable for voiceover only, with no on-camera personality."
    )
    result = _generate_ai_text(instruction)
    path = _save_text_asset(f"script_{platform}_{title}", result)
    if speak:
        speak("I generated the video script and saved it for you.")
    return f"Script generated and saved: {path}"


def _handle_thumbnail(parameters: dict, player, speak) -> str:
    prompt = parameters.get("prompt", "Faceless AI channel thumbnail").strip()
    if not prompt:
        prompt = "Faceless AI video thumbnail with strong contrast, bold text and iconography"
    image_path = _make_thumbnail(prompt)
    if speak:
        speak("I created a thumbnail mockup for your faceless video.")
    return f"Thumbnail generated: {image_path}"


def _handle_open_upload(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower().strip()
    if platform == "tiktok":
        return _tiktok_open_upload_page(parameters, player, speak)

    _open_url("https://studio.youtube.com")
    message = "Opened YouTube Studio upload page. Please upload your content there."
    if speak:
        speak(message)
    return message


def _handle_action(parameters: dict, player, speak) -> str:
    platform = parameters.get("platform", "youtube").lower().strip()
    if platform == "tiktok" and parameters.get("action") == "publish":
        return _publish_tiktok_video(parameters, player, speak)
    if platform == "youtube" and parameters.get("action") == "upload":
        return _upload_youtube_video(parameters, player, speak)
    return _handle_open_upload(parameters, player, speak)


_ACTION_MAP = {
    "strategy": _handle_strategy,
    "idea": _handle_idea,
    "script": _handle_script,
    "thumbnail": _handle_thumbnail,
    "open_upload": _handle_open_upload,
    "authorize_youtube": _authorize_youtube,
    "upload_video": _upload_youtube_video,
    "publish_tiktok": _publish_tiktok_video,
    "auto_publish": _create_and_publish_video,
    "schedule_publish": _schedule_publish,
    "list_schedules": _list_schedules,
    "cancel_schedule": _cancel_schedule,
    "youtube_analytics": _handle_youtube_analytics,
    "analytics_summary": _handle_analytics_summary,
}


def social_media_creator(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = params.get("action", "strategy").lower().strip()
    handler = _ACTION_MAP.get(action)
    if handler is None:
        return (
            f"Unknown social media creator action: '{action}'. "
            "Available: strategy, idea, script, thumbnail, open_upload, authorize_youtube, upload_video, publish_tiktok, "
            "schedule_publish, list_schedules, cancel_schedule, youtube_analytics, analytics_summary."
        )
    return handler(params, player, speak)


def social_media_manager(parameters: dict, response=None, player=None, session_memory=None, speak=None) -> str:
    params = parameters or {}
    action = params.get("action", "overview").lower().strip()
    if action == "overview":
        return (
            "Social media manager supports: idea, script, auto_publish, schedule_publish, "
            "list_schedules, cancel_schedule, analytics_summary, authorize_youtube. "
            "Use 'platform', 'niche', 'title', 'publish_time', and 'auto_create' as needed."
        )
    if action == "idea":
        return _handle_idea(params, player, speak)
    if action == "script":
        return _handle_script(params, player, speak)
    if action == "auto_publish":
        return _create_and_publish_video(params, player, speak)
    if action == "schedule_publish":
        return _schedule_publish(params, player, speak)
    if action == "list_schedules":
        return _list_schedules(params, player, speak)
    if action == "cancel_schedule":
        return _cancel_schedule(params, player, speak)
    if action == "analytics_summary":
        return _handle_analytics_summary(params, player, speak)
    if action == "authorize_youtube":
        return _authorize_youtube(params, player, speak)
    return (
        f"Unknown social_media_manager action '{action}'. "
        "Supported: overview, idea, script, auto_publish, schedule_publish, list_schedules, cancel_schedule, analytics_summary, authorize_youtube."
    )
