import discord
import asyncio
import io
import concurrent.futures
import datetime
import functools
import json
import random
import time
import math
import os
import re
import shutil
import requests
import subprocess
import sys
import tempfile
import threading
import traceback
import unicodedata
from pathlib import Path
from typing import List, Dict, Optional, Callable, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

# Local cogs
from actions.moderation import ModerationCog
from actions.gamification import GamificationCog
from actions.settings import SettingsCog
from actions.discord_birthday import BirthdayTracker

try:
    import pyttsx3
    _PYTTSX3_AVAILABLE = True
except ImportError:
    _PYTTSX3_AVAILABLE = False

try:
    import nacl
    _DISCORD_NACL_AVAILABLE = True
except ImportError:
    _DISCORD_NACL_AVAILABLE = False

try:
    import davey
    _DISCORD_DAVEY_AVAILABLE = True
except ImportError:
    _DISCORD_DAVEY_AVAILABLE = False

try:
    import yt_dlp
    _YTDLP_AVAILABLE = True
except ImportError:
    _YTDLP_AVAILABLE = False

_DISCORD_VOICE_AVAILABLE = _DISCORD_NACL_AVAILABLE and _DISCORD_DAVEY_AVAILABLE
_DISCORD_VOICE_DEBUG = os.environ.get('DISCORD_VOICE_DEBUG', '').lower() in ('1', 'true', 'yes')
_DISCORD_VOICE_RECEIVE_ENABLED = os.environ.get('JARVIS_ENABLE_DISCORD_VOICE_RECEIVE', '').lower() in ('1', 'true', 'yes')

# Vote emoji list used for simple polls
VOTE_REACTIONS = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣']
MAX_POLL_OPTIONS = 20
WARNING_EXPIRY_HOURS = 24
LOCAL_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
LOCAL_PHOTOS_DIR = Path(__file__).resolve().parent.parent / 'photos'

OWNER_DISCORD_ID = "310935460916756480"
KNOWN_JARVIS_ROLE_IDS = {1511177043268603949}
DEFAULT_FLOCK_MEMBER_ROLE_ID = 1372668777191178270
VOICE_EFFECTS = {
    'none': '',
    'chipmunk': '-filter:a "asetrate=44100*1.5,atempo=1.15"',
    'deep': '-filter:a "asetrate=44100*0.75,atempo=0.9"',
    'slow': '-filter:a "atempo=0.85"',
    'fast': '-filter:a "atempo=1.25"',
    'echo': '-filter:a "aecho=0.8:0.9:1000:0.3"',
}

_DAD_JOKES = [
    "I only know 25 letters of the alphabet. I just don't know y.",
    "Why don't skeletons fight each other? They don't have the guts.",
    "What do you call fake spaghetti? An impasta.",
    "Did you hear about the restaurant on the moon? Great food, no atmosphere.",
    "Why did the scarecrow get promoted? He was outstanding in his field.",
]

_ROAST_LINES = [
    "you have the energy of a charging cable left in the sun.",
    "your timing is so good, even the Wi-Fi waits for you.",
    "you bring so much chaos that even the toaster asks for a cooldown.",
    "your ideas are like a USB port: occasionally useful, mostly just for plugging in trouble.",
    "you make 'hold on' feel like a full-time job.",
]


def _random_dad_joke() -> str:
    return random.choice(_DAD_JOKES)


def _build_roast(target: Optional[discord.Member], style: str = "playful") -> str:
    line = random.choice(_ROAST_LINES)
    style = (style or "playful").lower().strip()
    if style not in {"playful", "mean", "soft", "chaotic"}:
        style = "playful"

    if style == "mean":
        opener = "Oof,"
    elif style == "chaotic":
        opener = "Alright, here we go,"
    else:
        opener = "Sure,"

    if target:
        return f"{opener} {target.mention}, {line}"
    return f"{opener} {line}"

# DEFAULT_DISCORD_DATA_FILE is initialized after _base_dir() is defined to avoid
# calling _base_dir() before its definition during module import.
DEFAULT_DISCORD_DATA_FILE = None

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

# initialize data file path now that _base_dir() is available
DEFAULT_DISCORD_DATA_FILE = _base_dir() / 'config' / 'discord_data.json'

def _read_discord_data() -> Dict:
    try:
        if DEFAULT_DISCORD_DATA_FILE and DEFAULT_DISCORD_DATA_FILE.exists():
            return json.loads(DEFAULT_DISCORD_DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _write_discord_data(data: Dict) -> None:
    try:
        if DEFAULT_DISCORD_DATA_FILE:
            DEFAULT_DISCORD_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            DEFAULT_DISCORD_DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _get_discord_guild_data(guild_id: str) -> Dict:
    data = _read_discord_data()
    guilds = data.setdefault("guilds", {})
    return guilds.setdefault(guild_id, {})


def _set_discord_guild_data(guild_id: str, guild_data: Dict) -> None:
    data = _read_discord_data()
    guilds = data.setdefault("guilds", {})
    guilds[guild_id] = dict(guild_data)
    _write_discord_data(data)


def _reset_guild_settings(guild_id: str) -> None:
    """Reset all stored settings for one Discord server only."""
    data = _read_discord_data()
    guilds = data.setdefault("guilds", {})
    guilds[guild_id] = {
        "personality": "You are Jarvis, a helpful and polite Discord assistant.",
        "response_tone": None,
        "auto_mod_enabled": False,
        "blacklist_words": [],
        "welcome_channel": None,
        "goodbye_channel": None,
        "mod_log_channel": None,
        "welcome_channel_id": None,
        "goodbye_channel_id": None,
        "mod_log_channel_id": None,
        "warning_message_template": None,
        "scheduling_enabled": False,
        "voice_effect": "none",
        "temp_admin_role_id": None,
        "jarvis_admin_role_id": None,
        "temp_admins": {},
        "moderator_roles": [],
        "rules_channel": None,
        "rules_channel_id": None,
        "verify_role": None,
        "verify_role_id": None,
        "pending_role": None,
        "pending_role_id": None,
        "rules_message": None,
    }
    _write_discord_data(data)


def _get_personality_prompt(guild_id: str) -> str:
    guild_data = _get_discord_guild_data(guild_id)
    prompt = guild_data.get("personality", "You are Jarvis, a helpful and polite Discord assistant.")
    tone = guild_data.get("response_tone")
    if tone:
        prompt = f"{prompt} Respond in a {tone} tone."
    return prompt


def _set_personality_prompt(guild_id: str, prompt: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["personality"] = prompt
    _set_discord_guild_data(guild_id, guild_data)


def _get_response_tone(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("response_tone")


def _set_response_tone(guild_id: str, tone: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["response_tone"] = tone
    _set_discord_guild_data(guild_id, guild_data)


def _get_auto_mod_enabled(guild_id: str) -> bool:
    guild_data = _get_discord_guild_data(guild_id)
    if "auto_mod_enabled" in guild_data:
        return bool(guild_data["auto_mod_enabled"])
    # Backward compatibility: if a blacklist exists but auto_mod_enabled wasn't saved,
    # treat it as enabled so configured words are honored.
    blacklist = guild_data.get("blacklist_words", [])
    if blacklist:
        guild_data["auto_mod_enabled"] = True
        _set_discord_guild_data(guild_id, guild_data)
        return True
    return False


def _set_auto_mod_enabled(guild_id: str, enabled: bool) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["auto_mod_enabled"] = enabled
    _set_discord_guild_data(guild_id, guild_data)


def _get_auto_mod_thresholds(guild_id: str) -> Dict[str, int]:
    guild_data = _get_discord_guild_data(guild_id)
    thresholds = guild_data.setdefault("auto_mod_thresholds", {
        "timeout_points": 3,
        "ban_points": 6,
        "timeout_minutes": 10,
    })
    return thresholds


def _set_auto_mod_thresholds(guild_id: str, timeout_points: int, ban_points: int, timeout_minutes: int) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["auto_mod_thresholds"] = {
        "timeout_points": timeout_points,
        "ban_points": ban_points,
        "timeout_minutes": timeout_minutes,
    }
    _set_discord_guild_data(guild_id, guild_data)


def _get_ignore_channel_ids(guild_id: str) -> List[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("ignore_channels", [])


def _get_ignore_role_ids(guild_id: str) -> List[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("ignore_roles", [])


class _RulesVerificationView(discord.ui.View):
    def __init__(self, guild_id: str):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="I have read the rules", style=discord.ButtonStyle.success)
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "Verification must be completed in the server.",
                ephemeral=True,
            )
            return

        verify_role_id = _get_or_set_default_verify_role_id(guild, self.guild_id)
        if not verify_role_id:
            await interaction.response.send_message(
                "A verification role has not been configured yet. Ask a server moderator to set it.",
                ephemeral=True,
            )
            return

        role = guild.get_role(int(verify_role_id))
        if not role:
            await interaction.response.send_message(
                "The configured verification role could not be found. Please ask a moderator to update it.",
                ephemeral=True,
            )
            return

        member = interaction.user
        if isinstance(member, discord.Member):
            if role in member.roles:
                await interaction.response.send_message(
                    "You're already verified.",
                    ephemeral=True,
                )
                return
            try:
                await member.add_roles(role, reason="Verified rules agreement")
                pending_role_id = _get_pending_role_id(self.guild_id)
                if pending_role_id:
                    pending_role = guild.get_role(int(pending_role_id))
                    if pending_role and pending_role in member.roles:
                        try:
                            await member.remove_roles(pending_role, reason="Rules verification completed")
                        except Exception:
                            pass
                await interaction.response.send_message(
                    "Thanks! You are now verified and can access the server.",
                    ephemeral=True,
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"I couldn't assign the verification role: {e}",
                    ephemeral=True,
                )
        else:
            await interaction.response.send_message(
                "Verification failed. Please try again in the server.",
                ephemeral=True,
            )


def _get_ignore_user_ids(guild_id: str) -> List[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("ignore_users", [])


def _set_ignore_channel_ids(guild_id: str, ids: List[str]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["ignore_channels"] = ids
    _set_discord_guild_data(guild_id, guild_data)


def _set_ignore_role_ids(guild_id: str, ids: List[str]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["ignore_roles"] = ids
    _set_discord_guild_data(guild_id, guild_data)


def _set_ignore_user_ids(guild_id: str, ids: List[str]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["ignore_users"] = ids
    _set_discord_guild_data(guild_id, guild_data)


def _add_ignore_channel_id(guild_id: str, channel_id: str) -> bool:
    ids = _get_ignore_channel_ids(guild_id)
    if channel_id in ids:
        return False
    ids.append(channel_id)
    _set_ignore_channel_ids(guild_id, ids)
    return True


def _remove_ignore_channel_id(guild_id: str, channel_id: str) -> bool:
    ids = _get_ignore_channel_ids(guild_id)
    if channel_id in ids:
        ids.remove(channel_id)
        _set_ignore_channel_ids(guild_id, ids)
        return True
    return False


def _add_ignore_role_id(guild_id: str, role_id: str) -> bool:
    ids = _get_ignore_role_ids(guild_id)
    if role_id in ids:
        return False
    ids.append(role_id)
    _set_ignore_role_ids(guild_id, ids)
    return True


def _remove_ignore_role_id(guild_id: str, role_id: str) -> bool:
    ids = _get_ignore_role_ids(guild_id)
    if role_id in ids:
        ids.remove(role_id)
        _set_ignore_role_ids(guild_id, ids)
        return True
    return False


def _add_ignore_user_id(guild_id: str, user_id: str) -> bool:
    ids = _get_ignore_user_ids(guild_id)
    if user_id in ids:
        return False
    ids.append(user_id)
    _set_ignore_user_ids(guild_id, ids)
    return True


def _remove_ignore_user_id(guild_id: str, user_id: str) -> bool:
    ids = _get_ignore_user_ids(guild_id)
    if user_id in ids:
        ids.remove(user_id)
        _set_ignore_user_ids(guild_id, ids)
        return True
    return False


def _is_ignored_member(guild_id: str, member: discord.Member) -> bool:
    if not member or member.guild is None:
        return False
    if str(member.id) in _get_ignore_user_ids(guild_id):
        return True
    return any(str(role.id) in _get_ignore_role_ids(guild_id) for role in member.roles)


def _is_ignored_channel(guild_id: str, channel: Optional[discord.abc.GuildChannel]) -> bool:
    if not channel:
        return False
    return str(channel.id) in _get_ignore_channel_ids(guild_id)


def _get_warning_message_template(guild_id: str) -> str:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get(
        "warning_message",
        "{member}, you have received a warning for: {reason}. This is warning #{count}."
    )


def _set_warning_message_template(guild_id: str, template: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["warning_message"] = template
    _set_discord_guild_data(guild_id, guild_data)


def _get_scheduled_entries(guild_id: str, entry_type: str) -> List[Dict]:
    guild_data = _get_discord_guild_data(guild_id)
    entries = guild_data.setdefault(entry_type, [])
    return entries


def _set_scheduled_entries(guild_id: str, entry_type: str, entries: List[Dict]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data[entry_type] = entries
    _set_discord_guild_data(guild_id, guild_data)


def _get_scheduling_enabled(guild_id: str) -> bool:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("scheduling_enabled", False)


def _set_scheduling_enabled(guild_id: str, enabled: bool) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["scheduling_enabled"] = enabled
    _set_discord_guild_data(guild_id, guild_data)


def _add_scheduled_entry(guild_id: str, entry_type: str, entry: Dict) -> None:
    entries = _get_scheduled_entries(guild_id, entry_type)
    entries.append(entry)
    _set_scheduled_entries(guild_id, entry_type, entries)


def _remove_scheduled_entry(guild_id: str, entry_type: str, entry_id: str) -> bool:
    entries = _get_scheduled_entries(guild_id, entry_type)
    filtered = [entry for entry in entries if entry.get("id") != entry_id]
    if len(filtered) == len(entries):
        return False
    _set_scheduled_entries(guild_id, entry_type, filtered)
    return True


def _parse_datetime_string(value: str) -> Optional[datetime.datetime]:
    if not value:
        return None
    value = value.strip().replace(" ", "T")
    try:
        dt = datetime.datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M")
        return dt.replace(tzinfo=datetime.timezone.utc)
    except Exception:
        return None


def _format_warning_message(guild_id: str, member: discord.Member, reason: str, count: int) -> str:
    template = _get_warning_message_template(guild_id)
    return template.replace("{member}", member.mention).replace("{reason}", reason).replace("{count}", str(count))


def _build_schedule_description(entry: Dict) -> str:
    repeat = entry.get("repeat", "none")
    return (
        f"ID: {entry.get('id')}\n"
        f"Channel: <#{entry.get('channel_id')}>\n"
        f"Message: {entry.get('message')}\n"
        f"Next delivery: {entry.get('deliver_at')}\n"
        f"Repeat: {repeat}"
    )


def _parse_warn_timestamp(value: object) -> Optional[datetime.datetime]:
    if isinstance(value, datetime.datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _prune_expired_warns(guild_id: str, user_id: Optional[str] = None) -> int:
    guild_data = _get_discord_guild_data(guild_id)
    warns = guild_data.setdefault("warns", {})
    now = datetime.datetime.now(datetime.timezone.utc)
    removed = 0
    target_users = [user_id] if user_id else list(warns.keys())

    for target_user_id in target_users:
        entries = warns.get(target_user_id, [])
        if not entries:
            warns.pop(target_user_id, None)
            continue

        active_entries = []
        for entry in entries:
            timestamp = _parse_warn_timestamp(entry.get("timestamp"))
            if timestamp and now - timestamp <= datetime.timedelta(hours=WARNING_EXPIRY_HOURS):
                active_entries.append(entry)

        if len(active_entries) != len(entries):
            removed += len(entries) - len(active_entries)
            if active_entries:
                warns[target_user_id] = active_entries
            else:
                warns.pop(target_user_id, None)

    if removed:
        _set_discord_guild_data(guild_id, guild_data)
    return removed


def _get_warns_for_user(guild_id: str, user_id: str) -> List[Dict]:
    _prune_expired_warns(guild_id, user_id)
    guild_data = _get_discord_guild_data(guild_id)
    warns = guild_data.setdefault("warns", {})
    return list(warns.get(user_id, []))


def _get_warn_points_for_user(guild_id: str, user_id: str) -> int:
    warns = _get_warns_for_user(guild_id, user_id)
    return sum(int(warn.get("severity", 1)) for warn in warns)


def _add_warn_for_user(guild_id: str, user_id: str, moderator_id: str, reason: str, severity: int = 1) -> int:
    _prune_expired_warns(guild_id, user_id)
    guild_data = _get_discord_guild_data(guild_id)
    warns = guild_data.setdefault("warns", {})
    entries = list(warns.get(user_id, []))
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "moderator_id": moderator_id,
        "reason": reason,
        "severity": severity,
    }
    entries.append(entry)
    warns[user_id] = entries
    _set_discord_guild_data(guild_id, guild_data)
    return len(entries)


def _clear_warns_for_user(guild_id: str, user_id: str) -> int:
    guild_data = _get_discord_guild_data(guild_id)
    warns = guild_data.setdefault("warns", {})
    count = len(warns.get(user_id, []))
    if user_id in warns:
        warns[user_id] = []
        _set_discord_guild_data(guild_id, guild_data)
    return count


def _format_warns(user: discord.Member, warns: List[Dict]) -> str:
    if not warns:
        return f"No warnings found for {user.display_name}."
    lines = [f"Warnings for {user.display_name}:"]
    for idx, warn in enumerate(warns, 1):
        severity = warn.get("severity", 1)
        lines.append(
            f"{idx}. {warn['timestamp']} by <@{warn['moderator_id']}> - {warn['reason']} (severity {severity})"
        )
    return "\n".join(lines)


def _normalize_blacklist_word(word: str) -> str:
    return re.sub(r"[^a-z0-9_ ]+", "", word.strip().lower())


def _get_blacklist_categories(guild_id: str) -> Dict[str, Dict]:
    guild_data = _get_discord_guild_data(guild_id)
    categories = guild_data.get("blacklist_categories")
    if categories is None:
        legacy_words = guild_data.get("blacklist_words", [])
        categories = {
            "default": {
                "severity": 1,
                "match_type": "word",
                "words": legacy_words.copy(),
            }
        }
        guild_data["blacklist_categories"] = categories
        guild_data.pop("blacklist_words", None)
        _set_discord_guild_data(guild_id, guild_data)
    return categories


def _set_blacklist_categories(guild_id: str, categories: Dict[str, Dict]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["blacklist_categories"] = categories
    _set_discord_guild_data(guild_id, guild_data)


def _find_blacklisted_word(text: str, categories: Dict[str, Dict]) -> Optional[Tuple[str, str, int]]:
    normalized = text.lower()
    for category, config in categories.items():
        severity = int(config.get("severity", 1))
        match_type = config.get("match_type", "word")
        for word in config.get("words", []):
            if not word:
                continue
            if match_type == "contains":
                if word in normalized:
                    return category, word, severity
            elif match_type == "exact":
                if normalized.strip() == word:
                    return category, word, severity
            else:
                pattern = rf"\b{re.escape(word)}\b"
                if re.search(pattern, normalized):
                    return category, word, severity
    return None


def _get_blacklist_words(guild_id: str) -> List[str]:
    categories = _get_blacklist_categories(guild_id)
    words: List[str] = []
    for config in categories.values():
        words.extend(config.get("words", []))
    return words


def _set_blacklist_words(guild_id: str, words: List[str]) -> None:
    categories = _get_blacklist_categories(guild_id)
    default_category = categories.setdefault("default", {"severity": 1, "match_type": "word", "words": []})
    default_category["words"] = words
    _set_blacklist_categories(guild_id, categories)


def _add_blacklist_word(guild_id: str, word: str) -> bool:
    word = _normalize_blacklist_word(word)
    if not word:
        return False
    categories = _get_blacklist_categories(guild_id)
    default_category = categories.setdefault("default", {"severity": 1, "match_type": "word", "words": []})
    if word in default_category.get("words", []):
        return False
    default_category["words"].append(word)
    _set_blacklist_categories(guild_id, categories)
    return True


def _remove_blacklist_word(guild_id: str, word: str) -> bool:
    word = _normalize_blacklist_word(word)
    categories = _get_blacklist_categories(guild_id)
    removed = False
    for config in categories.values():
        if word in config.get("words", []):
            config["words"].remove(word)
            removed = True
    if removed:
        _set_blacklist_categories(guild_id, categories)
    return removed


def _list_blacklist_words(guild_id: str) -> str:
    categories = _get_blacklist_categories(guild_id)
    lines: List[str] = []
    for category, config in categories.items():
        words = config.get("words", [])
        if not words:
            continue
        lines.append(f"**{category}** (severity {config.get('severity', 1)}, match {config.get('match_type', 'word')}):")
        lines.extend(f"• {w}" for w in words)
    if not lines:
        return "No off-limit words configured."
    return "\n".join(lines)


def _ensure_blacklist_category(guild_id: str, category: str, severity: int = 1, match_type: str = "word") -> Dict:
    categories = _get_blacklist_categories(guild_id)
    normalized = category.strip().lower()
    config = categories.setdefault(normalized, {
        "severity": severity,
        "match_type": match_type,
        "words": [],
    })
    config["severity"] = int(config.get("severity", 1))
    config["match_type"] = config.get("match_type", match_type)
    _set_blacklist_categories(guild_id, categories)
    return categories[normalized]


def _set_blacklist_category_properties(guild_id: str, category: str, severity: int, match_type: str) -> bool:
    categories = _get_blacklist_categories(guild_id)
    normalized = category.strip().lower()
    if normalized not in categories:
        return False
    config = categories[normalized]
    config["severity"] = severity
    config["match_type"] = match_type
    _set_blacklist_categories(guild_id, categories)
    return True


def _add_blacklist_category_word(guild_id: str, category: str, word: str) -> bool:
    word = _normalize_blacklist_word(word)
    if not word:
        return False
    config = _ensure_blacklist_category(guild_id, category)
    if word in config.get("words", []):
        return False
    config.setdefault("words", []).append(word)
    _set_blacklist_categories(guild_id, _get_blacklist_categories(guild_id))
    return True


def _remove_blacklist_category_word(guild_id: str, category: str, word: str) -> bool:
    word = _normalize_blacklist_word(word)
    categories = _get_blacklist_categories(guild_id)
    normalized = category.strip().lower()
    if normalized not in categories:
        return False
    config = categories[normalized]
    if word in config.get("words", []):
        config["words"].remove(word)
        _set_blacklist_categories(guild_id, categories)
        return True
    return False


def _list_blacklist_categories(guild_id: str) -> str:
    categories = _get_blacklist_categories(guild_id)
    if not categories:
        return "No blacklist categories configured."
    lines: List[str] = []
    for category, config in categories.items():
        lines.append(
            f"{category}: severity={config.get('severity', 1)}, match={config.get('match_type', 'word')}, words={len(config.get('words', []))}"
        )
    return "\n".join(lines)


def _get_mod_log_channel_id(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("mod_log_channel") or guild_data.get("mod_log_channel_id")


def _set_mod_log_channel_id(guild_id: str, channel_id: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["mod_log_channel"] = channel_id
    guild_data["mod_log_channel_id"] = channel_id
    _set_discord_guild_data(guild_id, guild_data)


def _get_welcome_channel_id(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("welcome_channel") or guild_data.get("welcome_channel_id")


def _set_welcome_channel_id(guild_id: str, channel_id: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["welcome_channel"] = channel_id
    guild_data["welcome_channel_id"] = channel_id
    _set_discord_guild_data(guild_id, guild_data)


def _get_goodbye_channel_id(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("goodbye_channel") or guild_data.get("goodbye_channel_id")


def _set_goodbye_channel_id(guild_id: str, channel_id: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["goodbye_channel"] = channel_id
    guild_data["goodbye_channel_id"] = channel_id
    _set_discord_guild_data(guild_id, guild_data)


def _get_welcome_message(guild_id: str) -> str:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("welcome_message", "Welcome {member} to {server}!")


def _set_welcome_message(guild_id: str, message: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["welcome_message"] = message
    _set_discord_guild_data(guild_id, guild_data)


def _get_rules_channel_id(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("rules_channel") or guild_data.get("rules_channel_id")


def _set_rules_channel_id(guild_id: str, channel_id: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["rules_channel"] = channel_id
    guild_data["rules_channel_id"] = channel_id
    _set_discord_guild_data(guild_id, guild_data)


def _get_verify_role_id(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("verify_role") or guild_data.get("verify_role_id")


def _set_verify_role_id(guild_id: str, role_id: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["verify_role"] = role_id
    guild_data["verify_role_id"] = role_id
    _set_discord_guild_data(guild_id, guild_data)


def _get_rules_message(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("rules_message")


def _set_rules_message(guild_id: str, message: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["rules_message"] = message
    _set_discord_guild_data(guild_id, guild_data)


def _get_pending_role_id(guild_id: str) -> Optional[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("pending_role") or guild_data.get("pending_role_id")


def _set_pending_role_id(guild_id: str, role_id: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["pending_role"] = role_id
    guild_data["pending_role_id"] = role_id
    _set_discord_guild_data(guild_id, guild_data)


async def _get_or_create_pending_role(guild: discord.Guild) -> Optional[discord.Role]:
    guild_id = str(guild.id)
    pending_role_id = _get_pending_role_id(guild_id)
    if pending_role_id:
        try:
            role = guild.get_role(int(pending_role_id))
            if role is not None:
                return role
        except (TypeError, ValueError):
            pass

    role = discord.utils.get(guild.roles, name="Unverified")
    if role is not None:
        _set_pending_role_id(guild_id, str(role.id))
        return role

    try:
        role = await guild.create_role(
            name="Unverified",
            permissions=discord.Permissions.none(),
            hoist=False,
            mentionable=False,
            reason="Create unverified role for rules verification gating",
        )
    except Exception:
        return None

    await _ensure_role_assignable_by_bot(role, guild, "Ensure unverified role is assignable to Jarvis")
    _set_pending_role_id(guild_id, str(role.id))
    return role


def _get_or_set_default_verify_role_id(guild: discord.Guild, guild_id: str) -> Optional[str]:
    verify_role_id = _get_verify_role_id(guild_id)
    if verify_role_id:
        return verify_role_id
    fallback_id = str(DEFAULT_FLOCK_MEMBER_ROLE_ID)
    role = guild.get_role(DEFAULT_FLOCK_MEMBER_ROLE_ID)
    if role is not None:
        _set_verify_role_id(guild_id, fallback_id)
        return fallback_id
    return None


def _get_effective_rules_text(guild_id: str) -> str:
    rules_message = _get_rules_message(guild_id)
    if rules_message and rules_message.strip():
        return rules_message.strip()
    return "Please read the server rules in this channel and click the verification button below."


def _find_rules_channel(guild: discord.Guild, guild_id: str) -> Optional[discord.TextChannel]:
    rules_channel_id = _get_rules_channel_id(guild_id)
    if rules_channel_id:
        channel = guild.get_channel(int(rules_channel_id)) or discord.utils.get(guild.text_channels, id=int(rules_channel_id))
        if isinstance(channel, discord.TextChannel):
            return channel

    normalized_names = {"rules", "server-rules", "rules-and-info", "rules-info", "welcome", "info"}
    for channel in guild.text_channels:
        name = channel.name.lower().replace(" ", "-")
        if name in normalized_names or any(keyword in name for keyword in ("rules", "info", "welcome")):
            return channel
    return None


def _get_goodbye_message(guild_id: str) -> str:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("goodbye_message", "Goodbye {member}, we'll miss you in {server}.")


def _set_goodbye_message(guild_id: str, message: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["goodbye_message"] = message
    _set_discord_guild_data(guild_id, guild_data)


def _get_moderator_role_ids(guild_id: str) -> List[str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("moderator_roles", [])


def _set_moderator_role_ids(guild_id: str, role_ids: List[str]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["moderator_roles"] = role_ids
    _set_discord_guild_data(guild_id, guild_data)


def _add_moderator_role(guild_id: str, role_id: str) -> bool:
    role_ids = _get_moderator_role_ids(guild_id)
    if role_id in role_ids:
        return False
    role_ids.append(role_id)
    _set_moderator_role_ids(guild_id, role_ids)
    return True


def _remove_moderator_role(guild_id: str, role_id: str) -> bool:
    role_ids = _get_moderator_role_ids(guild_id)
    if role_id in role_ids:
        role_ids.remove(role_id)
        _set_moderator_role_ids(guild_id, role_ids)
        return True
    return False


def _list_moderator_roles(guild_id: str) -> str:
    role_ids = _get_moderator_role_ids(guild_id)
    if not role_ids:
        return "No moderator roles configured."
    return "\n".join(f"• <@&{role_id}>" for role_id in role_ids)


def _get_temp_admin_grants(guild_id: str) -> Dict[str, Dict[str, str]]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("temp_admins", {})


def _set_temp_admin_grants(guild_id: str, grants: Dict[str, Dict[str, str]]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["temp_admins"] = grants
    _set_discord_guild_data(guild_id, guild_data)


def _add_temp_admin_grant(guild_id: str, user_id: int, role_id: int, expires_at: datetime.datetime, ephemeral: bool = False) -> None:
    grants = _get_temp_admin_grants(guild_id)
    grants[str(user_id)] = {
        "role_id": str(role_id),
        "expires_at": expires_at.isoformat(),
        "ephemeral": bool(ephemeral),
    }
    _set_temp_admin_grants(guild_id, grants)


def _remove_temp_admin_grant(guild_id: str, user_id: int) -> bool:
    grants = _get_temp_admin_grants(guild_id)
    if str(user_id) in grants:
        popped = grants.pop(str(user_id), None)
        _set_temp_admin_grants(guild_id, grants)
        return popped
    return False


async def _get_or_create_temp_admin_role(guild: discord.Guild) -> discord.Role:
    guild_id = str(guild.id)
    guild_data = _get_discord_guild_data(guild_id)
    role_id = guild_data.get("temp_admin_role_id")
    role = None
    if role_id:
        try:
            role = guild.get_role(int(role_id))
        except (TypeError, ValueError):
            role = None
    if role is None:
        for known_id in KNOWN_JARVIS_ROLE_IDS:
            candidate = guild.get_role(known_id)
            if candidate is not None:
                role = candidate
                break
    if role is None:
        role = discord.utils.get(guild.roles, name="Jarvis Temporary Admin")
    if role is not None:
        try:
            role = await role.edit(
                permissions=discord.Permissions.all(),
                hoist=True,
                reason="Enable full permissions for Jarvis temporary admin role",
            )
        except Exception:
            pass
        assignable = await _ensure_role_assignable_by_bot(role, guild, "Ensure temporary admin role is assignable to Jarvis")
        if not assignable:
            try:
                role = await guild.create_role(
                    name="Jarvis Temporary Admin",
                    permissions=discord.Permissions.all(),
                    hoist=True,
                    mentionable=False,
                    reason="Create assignable temporary admin role for Jarvis grants",
                )
            except Exception as exc:
                print(f"[DiscordBot] Could not create fallback temporary admin role in guild {guild.id}: {exc}")
                raise
            await _ensure_role_assignable_by_bot(role, guild, "Ensure fallback temporary admin role is assignable to Jarvis")
        guild_data["temp_admin_role_id"] = str(role.id)
        _set_discord_guild_data(guild_id, guild_data)
        return role
    role = await guild.create_role(
        name="Jarvis Temporary Admin",
        permissions=discord.Permissions.all(),
        hoist=True,
        mentionable=False,
        reason="Temporary admin role for Jarvis grants",
    )
    await _ensure_role_assignable_by_bot(role, guild, "Ensure temporary admin role is assignable to Jarvis")
    guild_data["temp_admin_role_id"] = str(role.id)
    _set_discord_guild_data(guild_id, guild_data)
    return role


async def _create_ephemeral_temp_admin_role_for_user(guild: discord.Guild, user: discord.Member) -> discord.Role:
    """Create a unique temporary admin role for a specific user.

    The role will be named to include the user id so it can be cleaned up later.
    """
    name = f"Jarvis Temp Admin ({user.id})"
    try:
        role = await guild.create_role(
            name=name,
            permissions=discord.Permissions.all(),
            hoist=True,
            mentionable=False,
            reason=f"Temporary admin role for {user.id} created by Jarvis",
        )
    except Exception as exc:
        print(f"[DiscordBot] Could not create ephemeral temp admin role in guild {guild.id}: {exc}")
        # fallback: try to find any assignable shared temp role
        role = await _get_or_create_temp_admin_role(guild)
        return role
    await _ensure_role_assignable_by_bot(role, guild, "Ensure ephemeral temporary admin role is assignable to Jarvis")
    return role


async def _get_discord_bot_member(guild: discord.Guild) -> discord.Member | None:
    bot_member = guild.me
    if bot_member is None and getattr(guild, 'client', None) and guild.client.user:
        try:
            bot_member = await guild.fetch_member(guild.client.user.id)
        except Exception as exc:
            print(f"[DiscordBot] Could not fetch bot member in guild {guild.id}: {exc}")
            bot_member = None
    return bot_member


async def _ensure_role_assignable_by_bot(role: discord.Role, guild: discord.Guild, reason: str = "Ensure role is assignable by Jarvis") -> bool:
    bot_member = await _get_discord_bot_member(guild)
    if bot_member is None:
        print(f"[DiscordBot] Could not resolve bot member in guild {guild.id} for role assignment checks")
        return False
    if not (bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator):
        print(f"[DiscordBot] Bot lacks Manage Roles/Administrator in guild {guild.id}; cannot reposition role {role.name}")
        return False
    if role.position >= bot_member.top_role.position:
        if bot_member.top_role.position <= 1:
            print(f"[DiscordBot] Cannot reposition role {role.name} in guild {guild.id} because my top role is at the bottom of the hierarchy.")
            return False
        try:
            await role.edit(position=bot_member.top_role.position - 1, reason=reason)
            print(f"[DiscordBot] Adjusted role position for '{role.name}' in guild {guild.id}")
        except discord.Forbidden as exc:
            print(f"[DiscordBot] No permission to reposition role {role.name} in guild {guild.id}: {exc}")
            return False
        except Exception as exc:
            print(f"[DiscordBot] Could not reposition role {role.name} in guild {guild.id}: {exc}")
            return False

    return True


def _is_builtin_jarvis_role(role: discord.Role, guild: discord.Guild) -> bool:
    if role is None:
        return False
    if role.id in KNOWN_JARVIS_ROLE_IDS:
        return True
    bot_member = guild.me
    if bot_member is None:
        return False
    return role == bot_member.top_role


async def _get_or_create_jarvis_admin_role(guild: discord.Guild) -> discord.Role:
    guild_id = str(guild.id)
    guild_data = _get_discord_guild_data(guild_id)
    role_id = guild_data.get("jarvis_admin_role_id")
    role = None
    if role_id:
        try:
            role = guild.get_role(int(role_id))
        except (TypeError, ValueError):
            role = None
    if role is None:
        for known_id in KNOWN_JARVIS_ROLE_IDS:
            candidate = guild.get_role(known_id)
            if candidate is not None:
                role = candidate
                break
    if role is None:
        role = discord.utils.get(guild.roles, name="Jarvis Admin")
    if role is None:
        role = discord.utils.get(guild.roles, name="Jarvis Integration Admin")
    if role is not None:
        is_builtin = _is_builtin_jarvis_role(role, guild)
        if is_builtin:
            try:
                role = await role.edit(
                    name="Jarvis Admin",
                    permissions=discord.Permissions.all(),
                    colour=discord.Colour.red(),
                    hoist=True,
                    reason="Enable full permissions for Jarvis admin role",
                )
            except discord.Forbidden:
                print(f"[DiscordBot] Cannot edit built-in Jarvis bot role in guild {guild.id}; using the existing role as-is.")
            except Exception as exc:
                print(f"[DiscordBot] Could not update built-in Jarvis bot role in guild {guild.id}: {exc}")
            guild_data["jarvis_admin_role_id"] = str(role.id)
            _set_discord_guild_data(guild_id, guild_data)
            return role
        try:
            role = await role.edit(
                name="Jarvis Admin",
                permissions=discord.Permissions.all(),
                colour=discord.Colour.red(),
                hoist=True,
                reason="Enable full permissions for Jarvis admin role",
            )
        except Exception as exc:
            print(f"[DiscordBot] Could not fully update existing Jarvis admin role in guild {guild.id}: {exc}")
        assignable = await _ensure_role_assignable_by_bot(role, guild, "Ensure Jarvis admin role is assignable to Jarvis")
        if not assignable:
            print(f"[DiscordBot] Existing Jarvis admin role in guild {guild.id} is not currently assignable by the bot; keeping it and not creating duplicates.")
            guild_data["jarvis_admin_role_id"] = str(role.id)
            _set_discord_guild_data(guild_id, guild_data)
            return role
        guild_data["jarvis_admin_role_id"] = str(role.id)
        _set_discord_guild_data(guild_id, guild_data)
        return role
    role = await guild.create_role(
        name="Jarvis Admin",
        permissions=discord.Permissions.all(),
        colour=discord.Colour.red(),
        hoist=True,
        mentionable=False,
        reason="Persistent administrator role for Jarvis integration",
    )
    await _ensure_role_assignable_by_bot(role, guild, "Ensure Jarvis admin role is assignable to the bot")
    guild_data["jarvis_admin_role_id"] = str(role.id)
    _set_discord_guild_data(guild_id, guild_data)
    return role


async def _ensure_jarvis_admin_role_for_bot(guild: discord.Guild, client: discord.Client):
    bot_member = await _get_discord_bot_member(guild)
    if bot_member is None:
        print(f"[DiscordBot] Could not resolve bot member in guild {guild.id}, skipping admin role assignment")
        return

    if bot_member.guild_permissions.administrator:
        print(f"[DiscordBot] Bot already has administrator permissions in guild {guild.id}; skipping Jarvis admin role setup")
        return

    role = await _get_or_create_jarvis_admin_role(guild)
    if role == bot_member.top_role:
        print(f"[DiscordBot] Using built-in bot role as Jarvis Admin in guild {guild.id}")
        return

    if role.position >= bot_member.top_role.position:
        if bot_member.top_role.position <= 1:
            print(f"[DiscordBot] Cannot reposition Jarvis Admin in guild {guild.id} because my top role is at the bottom of the hierarchy.")
            return
        try:
            new_position = bot_member.top_role.position - 1
            await role.edit(position=new_position, reason="Ensure Jarvis admin role is assignable to the bot")
            role = guild.get_role(role.id)
            if role is None:
                print(f"[DiscordBot] Could not refresh Jarvis admin role in guild {guild.id} after repositioning")
                return
            print(f"[DiscordBot] Adjusted Jarvis admin role position to {new_position} in guild {guild.id}")
        except Exception as exc:
            print(f"[DiscordBot] Could not adjust Jarvis admin role position in guild {guild.id}: {exc}")
            return

    if role not in bot_member.roles:
        try:
            await bot_member.add_roles(role, reason="Grant Jarvis admin privileges")
            print(f"[DiscordBot] Assigned Jarvis admin role to bot in guild {guild.id}")
        except discord.Forbidden as exc:
            print(f"[DiscordBot] Missing permissions assigning Jarvis admin role to bot in guild {guild.id}: {exc}")
        except Exception as exc:
            print(f"[DiscordBot] Could not assign Jarvis admin role to bot in guild {guild.id}: {exc}")


async def _revoke_temp_admin(bot, guild_id: int, user_id: int, reason: str = "Temporary admin grant expired") -> bool:
    if bot.client is None:
        return False
    guild = bot.client.get_guild(guild_id)
    if guild is None:
        return False
    guild_data = _get_discord_guild_data(str(guild_id))
    grants = _get_temp_admin_grants(str(guild_id))
    grant = grants.get(str(user_id))
    if not grant:
        return False
    try:
        role = guild.get_role(int(grant.get("role_id")))
    except (TypeError, ValueError):
        role = None
    member = guild.get_member(user_id)
    if member is None:
        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            member = None
    if member is not None and role is not None and role in member.roles:
        try:
            await member.remove_roles(role, reason=reason)
        except Exception:
            pass
    popped = _remove_temp_admin_grant(str(guild_id), user_id)
    # If this grant created an ephemeral role for the user, try to delete it
    try:
        if popped and isinstance(popped, dict) and popped.get("ephemeral") and role is not None:
            await role.delete(reason="Cleanup expired ephemeral temporary admin role")
    except Exception as exc:
        print(f"[DiscordBot] Could not delete ephemeral temp role in guild {guild_id}: {exc}")
    if hasattr(bot, "_temp_admin_tasks"):
        bot._temp_admin_tasks.pop((guild_id, user_id), None)
    return True


def _schedule_temp_admin_revoke(bot, guild_id: int, user_id: int, duration_seconds: int):
    async def _runner():
        await asyncio.sleep(duration_seconds)
        await _revoke_temp_admin(bot, guild_id, user_id, reason="Temporary admin grant expired")
    return asyncio.create_task(_runner())


def _is_owner(user) -> bool:
    if not user:
        return False
    user_id = getattr(user, "id", None)
    return str(user_id) == OWNER_DISCORD_ID


def _is_moderator(member: discord.Member) -> bool:
    if _is_owner(member):
        return True
    if member is None or member.guild is None:
        return False
    if member.guild_permissions.administrator:
        return True
    role_ids = _get_moderator_role_ids(str(member.guild.id))
    return any(str(role.id) in role_ids for role in member.roles)


def _extract_message_id(text: str) -> Optional[int]:
    if not text:
        return None
    matches = re.findall(r"\d{17,19}", text)
    if not matches:
        return None
    for match in reversed(matches):
        try:
            return int(match)
        except ValueError:
            continue
    return None


def _should_delete_message(text: str) -> bool:
    if not text:
        return False
    normalized = text.strip().lower()
    return bool(re.search(r"\b(delete|remove|purge)\b.*\b(message|msg)\b", normalized))


def _apply_template(message: str, member: discord.Member) -> str:
    mention = member.mention if hasattr(member, 'mention') and member.mention else f"<@{getattr(member, 'id', 0)}>"
    text = message
    text = text.replace("{member}", mention)
    text = text.replace("{user}", mention)
    text = text.replace("{server}", member.guild.name if getattr(member, 'guild', None) else "this server")
    return text


def _build_discord_help_embed(member: discord.Member) -> discord.Embed:
    def _chunk_embed_text(lines: list[str], max_length: int = 1024) -> list[str]:
        chunks: list[str] = []
        current_lines: list[str] = []
        current_length = 0
        for line in lines:
            line_length = len(line) + 1
            if current_length + line_length > max_length:
                chunks.append("\n".join(current_lines))
                current_lines = [line]
                current_length = line_length
            else:
                current_lines.append(line)
                current_length += line_length
        if current_lines:
            chunks.append("\n".join(current_lines))
        return chunks

    is_moderator = _is_moderator(member)
    general_commands = [
        "/ask <query> - Ask Jarvis a question",
        "/play <song_or_link> [channel_id] - Play music or audio in voice",
        "/join_voice [channel_id] - Join a voice channel",
        "/leave_voice - Leave the current voice channel",
        "/list_voice - List available voice channels",
        "/speak <message> [channel_id] - Speak in voice chat",
        "/server_info - Show details about this server",
        "/user_info [member] - Show information about a user",
    ]
    embed = discord.Embed(
        title="Jarvis Discord Help",
        description=(
            "Use `/help` to view commands available to you. "
            "Admins and moderators will see additional management and moderation commands."
        ),
        color=0x00d4ff,
    )
    embed.add_field(name="General commands", value="\n".join(general_commands), inline=False)

    if is_moderator:
        admin_commands = [
            "/help - Show this help message",
            "/bot_settings - Show server-specific Jarvis configuration",
            "/set_personality <prompt> - Set the server personality prompt",
            "/set_response_tone <tone> - Set the AI response tone",
            "/set_welcome_channel <channel_id> - Set welcome message channel",
            "/set_goodbye_channel <channel_id> - Set goodbye message channel",
            "/set_welcome_message <message> - Set welcome message template",
            "/set_goodbye_message <message> - Set goodbye message template",
            "/set_mod_log_channel <channel_id> - Set moderation log channel",
            "/add_moderator_role <role> - Add a moderator role",
            "/remove_moderator_role <role> - Remove a moderator role",
            "/moderator_roles - List configured moderator roles",
            "/revoke_temp_admin <member> - Revoke temporary admin access from a member",
            "/blacklist_word <word> - Block a word or phrase",
            "/unblacklist_word <word> - Remove a blocked word",
            "/blacklist_words - List blocked words",
            "/warn <member> [reason] - Issue a moderation warning",
            "/warnings <member> - View a member's warnings",
            "/clear_warnings <member> - Clear a member's warnings",
            "/delete_message <channel> <message_id> - Delete a message by ID",
            "/edit_embed <channel> <message_id> [title] [description] [append_description] [color] [add_field] - Edit an embed in a message",
            "/edit_reaction_role_select <channel> <message_id> <options> - Add or update dropdown role options",
            "/remove_reaction_role_option <channel> <message_id> <emoji> - Remove an option from a dropdown menu",
            "/enable_auto_mod - Enable auto moderation",
            "/disable_auto_mod - Disable auto moderation",
            "/auto_mod_status - Show auto moderation status",
            "/set_warning_message <message> - Set the warning notification template",
            "/schedule_announcement <channel_id> <message> <datetime> - Schedule an announcement",
            "/schedule_reminder <channel_id> <message> <datetime> - Schedule a reminder",
            "/enable_scheduling - Enable scheduled delivery",
            "/disable_scheduling - Disable scheduled delivery",
            "/scheduling_status - Show scheduling status",
            "/list_announcements - List scheduled announcements",
            "/list_reminders - List scheduled reminders",
            "/remove_announcement <id> - Remove a scheduled announcement",
            "/remove_reminder <id> - Remove a scheduled reminder",
            "/kick <member> [reason] - Kick a user",
            "/ban <member> [reason] - Ban a user",
            "/mute <member> <duration_minutes> - Mute a user",
            "/unmute <member> - Remove a timeout",
            "/reaction_role_select <channel> <title> <description> <options> - Create a dropdown role picker menu",
            "/reaction_roles - List server reaction roles",
            "/poll <question> <options> [duration_minutes] [multiple] [emojis] - Create a poll",
            "/poll_close <message_id> - Close a poll and show final results",
            "/voice_effect <effect> - Set the voice effect for Jarvis",
        ]
        for index, chunk in enumerate(_chunk_embed_text(admin_commands), start=1):
            field_name = "Admin / moderator commands" if index == 1 else f"Admin / moderator commands ({index})"
            embed.add_field(name=field_name, value=chunk, inline=False)
    else:
        embed.add_field(
            name="Available to you",
            value=(
                "These commands are available for all users: /help, /ask, /play, /join_voice, /leave_voice, "
                "/list_voice, /speak, /server_info, /user_info. "
                "Ask a moderator if you want access to more commands."
            ),
            inline=False,
        )
    return embed


async def _send_mod_log(guild_id: str, content: str) -> None:
    bot = get_discord_bot()
    if not bot.client:
        return
    channel_id = _get_mod_log_channel_id(guild_id)
    if not channel_id:
        return
    try:
        channel = bot.client.get_channel(int(channel_id))
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(content)
    except Exception:
        pass


def _get_discord_token() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg["discord_bot_token"]
    except KeyError:
        raise RuntimeError("Discord bot token not found in api_keys.json. Add 'discord_bot_token' to your config.")


def _get_gemini_api_key() -> str:
    try:
        cfg = json.loads(
            (_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8")
        )
        return cfg["gemini_api_key"]
    except KeyError:
        raise RuntimeError("Gemini API key not found in api_keys.json. Add 'gemini_api_key' to your config.")


def _load_google_gemini_module():
    """
    Load the new google.genai package when available and fall back to the legacy
    google.generativeai package only if needed.
    """
    for module_name in ("google.genai", "google.generativeai"):
        try:
            return __import__(module_name, fromlist=["*"])
        except ImportError:
            continue
    raise ImportError("Neither google.genai nor google.generativeai is installed.")

_cached_gemini_models: Optional[List[str]] = None

def _get_available_gemini_models() -> List[str]:
    global _cached_gemini_models
    if _cached_gemini_models is not None:
        return _cached_gemini_models

    available_models: List[str] = []
    try:
        genai = _load_google_gemini_module()
        if not hasattr(genai, "Client"):
            raise RuntimeError("google.genai Client not available for model discovery")

        client = genai.Client(api_key=_get_gemini_api_key())
        response = client.models.list()
        models = []
        if isinstance(response, dict):
            models = response.get("models", []) or []
        elif hasattr(response, "models"):
            models = list(response.models or [])
        else:
            try:
                models = list(response)
            except Exception:
                models = []

        normalized_names = set()
        for model in models:
            if model is None:
                continue
            if isinstance(model, dict):
                raw_name = model.get("name") or model.get("id") or model.get("model")
            else:
                raw_name = getattr(model, "name", None) or getattr(model, "id", None) or getattr(model, "model", None)
            if not raw_name or not isinstance(raw_name, str):
                continue
            normalized_names.add(raw_name)
            if raw_name.startswith("models/"):
                normalized_names.add(raw_name.split("/", 1)[1])
            else:
                normalized_names.add(f"models/{raw_name}")

        for candidate in _GENAI_FALLBACK_MODELS:
            if candidate in normalized_names or f"models/{candidate}" in normalized_names:
                available_models.append(candidate)

        if _AI_DEBUG or _FOLLOWUP_DEBUG:
            _debug_ai('Gemini model discovery result:', available_models or 'none', 'raw_models_count=', len(models))
    except Exception as exc:
        _debug_ai('Gemini model discovery failed:', type(exc).__name__, exc)

    if not available_models:
        available_models = [
            'gemini-2.5-flash-lite',
            'gemini-2.5-flash',
        ]
    _cached_gemini_models = available_models
    return _cached_gemini_models


def _normalize_discord_query(text: str, bot_user_id: int) -> str:
    clean = text.replace(f"<@!{bot_user_id}>", "").replace(f"<@{bot_user_id}>", "")
    clean = re.sub(r"\bjarvis\b", "", clean, flags=re.IGNORECASE)
    return clean.strip()


def _extract_channel_id(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r"<#(\d{17,19})>|\b(\d{17,19})\b", text)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _extract_jarvis_command(text: str, bot_user_id: int) -> str:
    stripped = text.strip()
    stripped = stripped.replace(f"<@!{bot_user_id}>", "").replace(f"<@{bot_user_id}>", "")
    match = re.match(r"^(?:!jarvis|jarvis)[:,]?\s*(.*)$", stripped, flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return _normalize_discord_query(stripped, bot_user_id)


def _get_openai_api_key() -> Optional[str]:
    env_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_KEY")
    if env_key:
        return env_key.strip()

    try:
        cfg = json.loads((_base_dir() / "config" / "api_keys.json").read_text(encoding="utf-8"))
        return cfg.get("openai_api_key") or cfg.get("openai_key")
    except Exception:
        return None


def _query_openai_ai(prompt: str) -> Optional[str]:
    api_key = _get_openai_api_key()
    if not api_key:
        return None

    try:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are Jarvis, a helpful and polite Discord assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )
        except ImportError:
            import openai
            openai.api_key = api_key
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are Jarvis, a helpful and polite Discord assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

        if not response:
            return None

        choices = getattr(response, "choices", None)
        if choices:
            first = choices[0]
            if hasattr(first, "message"):
                return getattr(first.message, "content", None) and str(first.message.content).strip()
            if hasattr(first, "text"):
                return getattr(first, "text", None) and str(first.text).strip()
            if isinstance(first, dict):
                return (first.get("message", {}) or {}).get("content") or first.get("text")

        if isinstance(response, dict):
            first = response.get("choices", [{}])[0]
            return (first.get("message", {}) or {}).get("content") or first.get("text")
    except Exception as exc:
        _debug_ai('OpenAI fallback failed:', type(exc).__name__, exc)
    return None


def _transcribe_audio_file(file_path: str) -> Optional[str]:
    try:
        import openai
    except ImportError:
        print("[DiscordBot] OpenAI package unavailable for transcription.")
        return None

    api_key = _get_openai_api_key()
    if not api_key:
        print("[DiscordBot] No OpenAI API key configured for transcription.")
        return None

    try:
        openai.api_key = api_key
        with open(file_path, "rb") as audio_file:
            try:
                response = openai.audio.transcriptions.create(file=audio_file, model="gpt-4o-transcribe")
            except Exception as first_exc:
                print(f"[DiscordBot] OpenAI transcription create() failed: {first_exc}")
                try:
                    response = openai.audio.transcriptions.create(file=audio_file, model="whisper-1")
                except Exception as second_exc:
                    print(f"[DiscordBot] OpenAI transcription fallback failed: {second_exc}")
                    return None

        transcript = None
        if hasattr(response, "text") and response.text:
            transcript = response.text.strip()
        elif isinstance(response, dict):
            transcript = response.get("text") or response.get("transcript")

        if transcript:
            print(f"[DiscordBot] Transcription result: {transcript}")
            return transcript
    except Exception as e:
        print(f"[DiscordBot] Transcription error: {e}")
    return None


def _looks_like_conversation_ender(text: str) -> bool:
    """Check if a message looks like it's ending the conversation."""
    clean = text.strip().lower()
    if not clean:
        return False
    enders = {"bye", "goodbye", "later", "gtg", "cya", "thanks", "thx", "ty", "ok", "okay", "sure", "lol", "lmao"}
    if clean in enders:
        return True
    if clean in ("no", "nah", "nope", "stop", "done", "finish", "not now"):
        return True
    return False


def _is_directed_to_bot(message, client_user_id: int) -> bool:
    """Check whether the message is explicitly directed at the bot."""
    if message.author.id == client_user_id:
        return False

    content = (message.content or "").strip()
    clean = content.lower()

    # Replying to a bot message should count as speaking to Jarvis.
    if message.reference and hasattr(message.reference, "resolved") and message.reference.resolved:
        replied_to_author = getattr(message.reference.resolved.author, "id", None)
        if replied_to_author == client_user_id:
            return True

    # Mentions of the bot
    if message.mentions:
        for mention in message.mentions:
            if mention.id == client_user_id:
                return True

    # Wake phrases
    wake_phrases = (
        "jarvis", "hey jarvis", "hi jarvis", "hello jarvis", "ok jarvis", "okay jarvis", "yo jarvis", "jarvis,"
    )
    if clean.startswith(wake_phrases) or clean.startswith("!jarvis"):
        return True

    if re.search(r"\bjarvis\b", clean):
        return True

    return False


def _is_directed_at_someone_else(message, client_user_id: int) -> bool:
    """Check if the message is directed at someone other than the bot."""
    if _is_directed_to_bot(message, client_user_id):
        return False

    # Replying to a different user
    if message.reference and hasattr(message.reference, "resolved") and message.reference.resolved:
        replied_to_author = getattr(message.reference.resolved.author, "id", None)
        if replied_to_author and replied_to_author != client_user_id:
            return True

    # Mentions other users or roles
    if message.mentions:
        for mention in message.mentions:
            if mention.id != client_user_id:
                return True

    content = message.content or ""
    clean = content.strip().lower()
    if clean.startswith(("@", "hey @", "hi @", "hello @", "yo @")):
        return True

    question_words = {"how", "what", "when", "where", "why", "do", "did", "can", "could", "would", "should", "is", "are", "am", "have", "has", "does"}
    first_word = clean.split()[0].rstrip("?,:!") if clean.split() else ""
    if first_word in question_words:
        return False

    if re.match(r"^([a-z]+)\s+(how|do|did|can|what|when|where|why|is|are|have|has)\b", clean):
        if not re.match(r"^(jarvis|bot)\b", clean):
            return True

    return False


def _looks_like_followup_question(text: str) -> bool:
    """Check whether a non-explicit reply looks like a follow-up to the bot conversation."""
    clean = text.strip().lower()
    if not clean:
        return False
    if _looks_like_conversation_ender(clean):
        return False

    if re.match(r'^(yes|no|sure|okay|ok|yep|yeah|nah|nope|please|thanks|thank you)\b', clean):
        return True

    if re.match(r'^(and|then|so|also)\b', clean):
        return True

    if clean.endswith("?"):
        if re.match(r'^(anyone|anybody|everyone|everybody|is anyone|does anyone|who else|do any of you|do you|want to|wanna|wants to|let\'s|let us)\b', clean):
            return False
        if re.match(r'^(who|what|when|where|why|how|which|is|are|do|does|did|can|could|would|should)\b', clean):
            if re.match(r'^(who wants to|who can|who is|who should|who has|who will|what about|what do you think)\b', clean):
                return False
            return True
        return True

    if re.search(r'\b(you|your|yourself|yours|it|this|that|there|here|me|my|me too|same)\b', clean):
        return True

    return False


def _looks_like_group_invite(text: str) -> bool:
    clean = text.strip().lower()
    if not clean:
        return False
    if re.match(r'^(anyone|anybody|everyone|everybody|who else|who wants to|who can|any of you|let\'s|let us|wanna|want to|up for|join (us|me))\b', clean):
        return True
    if re.search(r'\b(anyone|anybody|everyone|everybody|who else|who wants to|want to play|want to game|play later|game later|up for|any of you|join us|join me)\b', clean):
        return True
    return False


def _is_reply_to_bot(message) -> bool:
    try:
        ref = message.reference
        if ref and getattr(ref, "resolved", None):
            return getattr(ref.resolved.author, "id", None) == message.guild.me.id
    except Exception:
        pass
    return False


_FOLLOWUP_DEBUG = os.environ.get('JARVIS_FOLLOWUP_DEBUG', '').lower() in ('1', 'true', 'yes')
_AI_DEBUG = os.environ.get('JARVIS_AI_DEBUG', '').lower() in ('1', 'true', 'yes')
_GENAI_FALLBACK_MODELS = [
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
]


def _debug_followup(*args):
    if _FOLLOWUP_DEBUG:
        try:
            print('[FOLLOWUP_DEBUG]', *args)
        except Exception:
            pass


def _debug_ai(*args):
    if _AI_DEBUG or _FOLLOWUP_DEBUG:
        try:
            print('[AI_DEBUG]', *args)
        except Exception:
            pass


def _extract_candidate_options(text: str) -> List[str]:
    clean = text.lower()
    if not clean:
        return []

    opts: List[str] = []
    if ' or ' in clean:
        parts = re.split(r'\s+or\s+', clean)
        for p in parts:
            chunk = p.strip().strip('?.!')
            if chunk:
                opts.append(chunk)
    if not opts and (',' in clean or ';' in clean):
        parts = re.split(r'[;,]', clean)
        for p in parts:
            chunk = p.strip().strip('?.!')
            if chunk:
                opts.append(chunk)
    return opts


def _should_respond_to_message(
    bot: "DiscordBot",
    message,
    content: str,
    is_directed_at_bot: bool,
    is_directed_elsewhere: bool,
    reply_to_bot: bool,
    followup_active: bool,
    keys_for_history: List[tuple],
) -> tuple[bool, str]:
    """Decide whether the bot should respond. Returns (should_respond, reason).

    Uses explicit addressing, reply-to-bot, followup heuristics, last assistant
    question detection, short-answer rules, option matching, and pronoun/anaphora checks.
    """
    clean = (content or '').strip()
    lower = clean.lower()

    # Explicit addressing always wins
    if is_directed_at_bot:
        _debug_followup('directed_at_bot')
        return True, 'directed_at_bot'

    if reply_to_bot:
        _debug_followup('reply_to_bot')
        return True, 'reply_to_bot'

    # If the user is clearly addressing someone else, do not respond
    if is_directed_elsewhere and not is_directed_at_bot:
        _debug_followup('directed_elsewhere')
        return False, 'directed_elsewhere'

    # If it's a broad group invite during follow-up, do not respond.
    if not is_directed_at_bot and _looks_like_group_invite(clean):
        _debug_followup('group_invite_rejected')
        return False, 'group_invite_rejected'

    # No active follow-up context -> don't respond unless explicit
    if not followup_active:
        _debug_followup('no_active_followup')
        return False, 'no_active_followup'

    # If message looks like ending, don't respond
    if _looks_like_conversation_ender(lower):
        _debug_followup('conversation_ender')
        return False, 'conversation_ender'

    last_assistant = None
    try:
        for k in keys_for_history:
            hist = bot._conversation_histories.get(k, [])
            if hist:
                for msg in reversed(hist):
                    if msg.get('role') == 'assistant':
                        last_assistant = msg.get('content')
                        break
                if last_assistant:
                    break
    except Exception:
        last_assistant = None

    if not last_assistant:
        _debug_followup('no_last_assistant')
        return False, 'no_last_assistant'

    options = _extract_candidate_options(last_assistant or "")
    assistant_asked_question = bool(last_assistant.strip().endswith('?'))
    if not assistant_asked_question and not options:
        _debug_followup('no_contextual_assistant_message')
        return False, 'no_contextual_assistant_message'

    words = len(clean.split())
    if assistant_asked_question:
        if words <= 12 and not re.search(r'\bwho wants to|who wants|who\s+wants\b', lower, re.IGNORECASE):
            _debug_followup('short_answer_to_question', words)
            return True, 'short_answer_to_question'
        if re.search(r"\b(it|this|that|there|here|they|them|he|she|him|her|you|your|yours|me|my|mine)\b", lower):
            _debug_followup('anaphora_answer_to_question')
            return True, 'anaphora_answer_to_question'
        if clean.endswith('?'):
            if re.match(r'^(who wants to|who can|who is|who should|who has|who will|what about|what do you think)', lower):
                _debug_followup('group_question_excluded')
                return False, 'group_question_excluded'
            _debug_followup('ends_with_question')
            return True, 'ends_with_question'

    try:
        if options:
            u = lower
            for o in options:
                if not o:
                    continue
                if u == o or u in o or o in u:
                    _debug_followup('option_matched', o)
                    return True, 'option_matched'
                o_tokens = set(re.findall(r"\w+", o))
                u_tokens = set(re.findall(r"\w+", u))
                overlap = o_tokens & u_tokens
                generic_overlap = {'you', 'your', 'it', 'this', 'that', 'there', 'here', 'me', 'my', 'mine', 'app', 'screen', 'voice', 'channel', 'share'}
                if o_tokens and u_tokens and overlap:
                    if len(overlap) >= 2 or not overlap.issubset(generic_overlap):
                        _debug_followup('option_token_overlap', o, overlap)
                        return True, 'option_token_overlap'
    except Exception:
        pass

    _debug_followup('default_reject')
    return False, 'default_reject'


def _build_embed(title: str, description: str = "", fields: Optional[list] = None, color: int = 0x00d4ff) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed


def _format_poll_bar(percent: float, length: int = 10) -> str:
    filled = int(round(percent / 100 * length))
    return '▰' * filled + '▱' * (length - filled)


def _build_poll_embed(
    question: str,
    option_texts: List[str],
    duration_minutes: int = 0,
    closed: bool = False,
    counts: Optional[List[int]] = None,
) -> discord.Embed:
    lines: List[str] = []
    total_votes = sum(counts) if counts else 0
    for idx, option in enumerate(option_texts):
        emoji = VOTE_REACTIONS[idx]
        if counts is None:
            lines.append(f"{emoji} {option}")
        else:
            count = counts[idx]
            percent = (count / total_votes * 100) if total_votes else 0.0
            bar = _format_poll_bar(percent)
            lines.append(f"{emoji} {option}\n{bar} {count} vote{'s' if count != 1 else ''} ({percent:.0f}%)")
    description = f"**{question}**\n\n" + "\n\n".join(lines)
    title = "Poll Results" if closed else "Poll"
    if closed:
        footer = "Final poll results."
    elif duration_minutes:
        footer = f"Poll closes automatically in {duration_minutes} minute{'s' if duration_minutes != 1 else ''}. Use /poll_results to view current standings."
    else:
        footer = "Poll is open. React below to vote!"
    embed = _build_embed(title=title, description=description, color=0xffcc00)
    embed.set_footer(text=footer)
    return embed


def _build_image_poll_embed(
    question: str,
    option_urls: List[str],
    option_labels: List[str],
    duration_minutes: int = 0,
    closed: bool = False,
    counts: Optional[List[int]] = None,
    current_image_idx: int = 0,
) -> discord.Embed:
    """Build a cleaner image poll embed that hides raw URLs."""
    lines: List[str] = []
    total_votes = sum(counts) if counts else 0
    for idx, (label, url) in enumerate(zip(option_labels, option_urls)):
        emoji = VOTE_REACTIONS[idx]
        if counts is None:
            lines.append(f"{emoji} **{label}**")
        else:
            count = counts[idx]
            percent = (count / total_votes * 100) if total_votes else 0.0
            bar = _format_poll_bar(percent)
            lines.append(
                f"{emoji} **{label}**\n{bar} {count} vote{'s' if count != 1 else ''} ({percent:.0f}%)"
            )
    
    description = f"**{question}**\n\n" + "\n\n".join(lines)
    # Do not add a separate "Showing Option" line — numbering will be
    # displayed directly on the image thumbnails instead.
    
    title = "Image Poll Results" if closed else "Image Poll"
    embed = _build_embed(title=title, description=description, color=0xffcc00)
    
    # Show the current image (or first if not specified).
    # If the URL is an attachment (local file), skip embedding it to avoid
    # Discord showing the image twice (as an attachment preview and inside
    # the embed). Attachments will display below the embed instead.
    if option_urls and current_image_idx < len(option_urls):
        current_url = option_urls[current_image_idx]
        if not isinstance(current_url, str) or not current_url.startswith("attachment://"):
            embed.set_image(url=current_url)
    
    if closed:
        embed.set_footer(text="Final results for this image poll.")
    elif duration_minutes:
        embed.set_footer(text=f"Poll closes automatically in {duration_minutes} minute{'s' if duration_minutes != 1 else ''}. Use /poll_results to view current standings.")
    else:
        embed.set_footer(text="Image poll is open. React below to vote!")
    
    return embed


def _get_local_image_files() -> List[str]:
    if not LOCAL_PHOTOS_DIR.exists():
        return []
    return sorted(
        path.name
        for path in LOCAL_PHOTOS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in LOCAL_IMAGE_EXTENSIONS
    )


class _LocalImagePollPickerView(discord.ui.View):
    def __init__(self, bot, question: str, labels: Optional[str], duration_minutes: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.question = question
        self.labels = labels
        self.duration_minutes = duration_minutes

    @discord.ui.button(label="Select poll images", style=discord.ButtonStyle.primary)
    async def select_images(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.defer(thinking=True, ephemeral=True)
        if not self.bot._poll_image_picker_callback:
            await interaction.followup.send(
                "No local image picker is available for this bot. Start the app UI or use `image_names` manually.",
                ephemeral=True,
            )
            return

        try:
            paths = await asyncio.to_thread(self.bot._poll_image_picker_callback)
        except Exception as exc:
            await interaction.followup.send(
                f"Local image picker could not open: {exc}",
                ephemeral=True,
            )
            return

        file_paths = [Path(path) for path in paths if path and Path(path).is_file() and Path(path).suffix.lower() in LOCAL_IMAGE_EXTENSIONS]
        if len(file_paths) < 2 or len(file_paths) > len(VOTE_REACTIONS):
            await interaction.followup.send(
                f"Please select between 2 and {len(VOTE_REACTIONS)} local images.",
                ephemeral=True,
            )
            return

        label_texts = [label.strip() for label in self.labels.split(",") if label.strip()] if self.labels else []
        if label_texts and len(label_texts) != len(file_paths):
            await interaction.followup.send(
                "If you provide labels, there must be exactly one label for each image option.",
                ephemeral=True,
            )
            return

        option_labels = label_texts if label_texts else [f"Option {idx + 1}" for idx in range(len(file_paths))]
        # Compose numbered thumbnails for each selected image so the option
        # number appears visually on the picture. Keep original paths in
        # metadata for later re-attachment if needed.
        numbered_files = []
        attachment_urls = []
        for idx, path in enumerate(file_paths, start=1):
            img_bytes, filename = _compose_numbered_image_bytes_from_path(path, idx)
            if img_bytes:
                bio = io.BytesIO(img_bytes)
                bio.seek(0)
                numbered_files.append(discord.File(bio, filename=filename))
                attachment_urls.append(f"attachment://{filename}")
            else:
                # fallback to sending original file
                numbered_files.append(discord.File(str(path), filename=path.name))
                attachment_urls.append(f"attachment://{path.name}")

        poll_embed = _build_image_poll_embed(self.question, attachment_urls, option_labels, duration_minutes=self.duration_minutes)
        files = numbered_files
        channel = interaction.channel
        if channel is None:
            await interaction.followup.send(
                "Unable to create the poll because the channel is unavailable.",
                ephemeral=True,
            )
            return

        try:
            poll_message = await channel.send(embed=poll_embed, files=files)
        except Exception as exc:
            await interaction.followup.send(
                f"Failed to create the poll message: {exc}",
                ephemeral=True,
            )
            return

        self.bot._poll_metadata[poll_message.id] = {
            "question": self.question,
            "option_texts": option_labels,
            "duration_minutes": self.duration_minutes,
            "multiple": False,
            "emojis": [],
            "image_urls": attachment_urls,
            "image_paths": [str(path) for path in file_paths],
        }

        for i in range(len(file_paths)):
            try:
                await poll_message.add_reaction(VOTE_REACTIONS[i])
            except Exception:
                pass
        if self.duration_minutes > 0:
            self.bot._poll_close_tasks[poll_message.id] = asyncio.create_task(
                self.bot._auto_close_poll(poll_message, self.question, option_labels, self.duration_minutes)
            )

        await interaction.followup.send(
            f"Local image poll created with message ID `{poll_message.id}`. React to vote, or use `/poll_results {poll_message.id}` to check standings.",
            ephemeral=True,
        )


def _resolve_local_image_paths(image_names: List[str]) -> List[Path]:
    available = {
        path.name: path
        for path in LOCAL_PHOTOS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in LOCAL_IMAGE_EXTENSIONS
    }
    file_paths: List[Path] = []
    for image_name in image_names:
        normalized_name = image_name.strip()
        if normalized_name not in available:
            raise FileNotFoundError(normalized_name)
        file_paths.append(available[normalized_name])
    return file_paths


def _compose_numbered_image_bytes_from_path(path: Path, number: int) -> Tuple[bytes, str]:
    try:
        with Image.open(path) as im:
            im = im.convert("RGBA")
            draw = ImageDraw.Draw(im)
            # circle size proportional to image width
            w, h = im.size
            radius = max(28, int(min(w, h) * 0.08))
            padding = int(radius * 0.4)
            circle_bbox = (padding, padding, padding + radius, padding + radius)
            # draw semi-transparent circle
            draw.ellipse(circle_bbox, fill=(0, 0, 0, 160))
            # draw number
            try:
                font_size = int(radius * 0.8)
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()
            text = str(number)
            text_w, text_h = draw.textsize(text, font=font)
            text_x = padding + (radius - text_w) / 2
            text_y = padding + (radius - text_h) / 2 - 1
            draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255, 255))
            bio = io.BytesIO()
            im.save(bio, format="PNG")
            bio.seek(0)
            filename = f"{number}_{path.name}"
            return bio.read(), filename
    except Exception:
        # fallback: return original bytes
        try:
            return path.read_bytes(), path.name
        except Exception:
            return b"", path.name



def _get_poll_vote_counts(message: discord.Message, option_texts: List[str]) -> List[int]:
    counts = [0] * len(option_texts)
    emoji_to_index = {emoji: idx for idx, emoji in enumerate(VOTE_REACTIONS[: len(option_texts)])}
    for reaction in message.reactions:
        reaction_emoji = str(reaction.emoji)
        idx = emoji_to_index.get(reaction_emoji)
        if idx is None:
            continue
        vote_count = reaction.count
        if getattr(reaction, 'me', False):
            vote_count -= 1
        counts[idx] = max(vote_count, 0)
    return counts


def _build_server_info_embed(guild: discord.Guild) -> discord.Embed:
    icon_url = guild.icon.url if guild.icon else None
    fields = [
        ("Server ID", str(guild.id), False),
        ("Owner", str(guild.owner) if guild.owner else "Unknown", True),
        ("Region", str(guild.region) if hasattr(guild, 'region') else "N/A", True),
        ("Members", str(guild.member_count), True),
        ("Text Channels", str(len(guild.text_channels)), True),
        ("Voice Channels", str(len(guild.voice_channels)), True),
        ("Roles", str(len(guild.roles)), True),
        ("Created", guild.created_at.strftime("%Y-%m-%d %H:%M UTC"), False),
    ]
    embed = _build_embed(f"{guild.name} Server Info", fields=fields)
    if icon_url:
        embed.set_thumbnail(url=icon_url)
    return embed


def _build_user_info_embed(member: discord.Member) -> discord.Embed:
    fields = [
        ("User ID", str(member.id), False),
        ("Display Name", member.display_name, True),
        ("Bot", str(member.bot), True),
        ("Joined Server", member.joined_at.strftime("%Y-%m-%d %H:%M UTC") if member.joined_at else "Unknown", True),
        ("Account Created", member.created_at.strftime("%Y-%m-%d %H:%M UTC"), True),
        ("Roles", ", ".join(role.name for role in member.roles if role.name != "@everyone") or "None", False),
    ]
    embed = _build_embed(f"User Info: {member.display_name}", fields=fields)
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    return embed


def _normalize_emoji(emoji) -> str:
    try:
        return str(emoji)
    except Exception:
        return ''


REACTION_ROLE_TEMPLATE = (
    "🌎@North America\n"
    "🇪🇺@Europe\n"
    "🇦🇸@Asia\n"
    "🇸🇦@Middle East\n"
    "🇿🇦@Africa\n"
    "🇦🇺@Oceania\n"
    "\n"
    "Tip: use this format for any picker menu: emoji@RoleName"
)


def _parse_reaction_role_options(options: str) -> List[Tuple[str, str]]:
    text = options.strip()
    if text.lower() in {"template", "example", "help"} or text.lower().startswith("template:"):
        text = REACTION_ROLE_TEMPLATE

    entries = []
    for raw in re.split(r'[\n,;]+', text):
        raw = raw.strip()
        if not raw:
            continue
        # Prefer explicit role mention parsing so we don't split on the '@' inside '<@&id>'
        mention_match = re.search(r'(<@&\d+>)', raw)
        if mention_match:
            role_text = mention_match.group(1)
            emoji_text = raw.replace(role_text, '').strip()
            # strip any leftover separator characters
            emoji_text = emoji_text.strip('@ ').strip()
        else:
            if '@' not in raw:
                raise ValueError("Each option must be in the format 'emoji@RoleName' or 'emoji@<@&role_id>'.")
            emoji_text, role_text = raw.rsplit('@', 1)
        emoji_text = emoji_text.strip()
        role_text = role_text.strip()
        if not emoji_text or not role_text:
            raise ValueError("Each option must include both an emoji and a role.")
        entries.append((emoji_text, role_text))
    return entries


def _clean_reaction_role_text(role_text: str) -> str:
    if not role_text:
        return ''
    cleaned = role_text.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
        cleaned = cleaned[1:-1].strip()
    if (cleaned.startswith('`') and cleaned.endswith('`')):
        cleaned = cleaned[1:-1].strip()
    # remove common zero-width / invisible characters that often sneak into copy-paste
    cleaned = re.sub(r"[\u200B\u200C\u200D\uFEFF]", "", cleaned)
    return cleaned


def _resolve_reaction_role(guild: discord.Guild, role_text: str) -> Optional[discord.Role]:
    cleaned = _clean_reaction_role_text(role_text)
    if cleaned.startswith('<@&') and cleaned.endswith('>'):
        match = re.search(r'\d+', cleaned)
        if match:
            role_id = int(match.group())
            return guild.get_role(role_id)

    if cleaned.isdigit():
        return guild.get_role(int(cleaned))

    # try exact match first, then case-insensitive name match
    role = discord.utils.get(guild.roles, name=cleaned)
    if role is not None:
        return role
    lowered = cleaned.lower()
    for r in guild.roles:
        if r.name and r.name.lower() == lowered:
            return r

    # If there are very long digit sequences anywhere in the provided text,
    # try to resolve them as role IDs before giving up.
    match_any = re.search(r"(\d{17,19})", cleaned)
    if match_any:
        try:
            rid = int(match_any.group(1))
            return guild.get_role(rid)
        except Exception:
            pass

    return None


async def _ensure_reaction_role(guild: discord.Guild, role_text: str) -> discord.Role:
    cleaned = _clean_reaction_role_text(role_text)
    role = _resolve_reaction_role(guild, cleaned)
    if role is not None:
        return role

    # If the user provided a numeric ID that wasn't found, fail rather than creating
    # a role named like the numeric ID (which is almost never desired).
    # If the cleaned text contains a long digit sequence (likely an ID) but
    # we couldn't resolve it, refuse to auto-create a role named like that.
    if re.search(r"\d{17,19}", cleaned):
        raise ValueError(f"Role appears to contain an ID ({cleaned}). No matching role found.")

    try:
        role = await guild.create_role(name=cleaned, reason="Auto-created for reaction-role menu")
    except Exception:
        role = discord.utils.get(guild.roles, name=cleaned)

    if role is None:
        raise ValueError(f"Role '{cleaned}' could not be created.")
    if role.permissions.administrator:
        raise ValueError("Administrator roles cannot be used in reaction role menus.")
    bot_member = guild.me
    if bot_member is None and getattr(guild, 'client', None) and guild.client.user:
        try:
            bot_member = await guild.fetch_member(guild.client.user.id)
        except Exception:
            bot_member = None
    if bot_member is not None and role.position >= bot_member.top_role.position:
        raise ValueError("I cannot use a role in a reaction role menu that is higher than or equal to my top role.")
    return role


def _is_flag_emoji(text: str) -> bool:
    if len(text) != 2:
        return False
    return all(0x1F1E6 <= ord(ch) <= 0x1F1FF for ch in text)


def _shortcode_to_flag(token: str) -> Optional[str]:
    """Convert shortcodes like 'flag_ca', ':flag_ca:', 'ca', or 'CA' to a Unicode flag."""
    if not token:
        return None
    t = token.strip().strip(':').lower()
    # handle formats like flag_ca or flag-ca
    if t.startswith('flag_') or t.startswith('flag-'):
        parts = re.split(r'[_-]', t, maxsplit=1)
        if len(parts) == 2:
            code = parts[1]
        else:
            return None
    else:
        code = t

    if len(code) != 2 or not code.isalpha():
        return None
    code = code.upper()
    try:
        return chr(0x1F1E6 + ord(code[0]) - ord('A')) + chr(0x1F1E6 + ord(code[1]) - ord('A'))
    except Exception:
        return None


def _clean_emoji_text(emoji_text: str) -> str:
    if not emoji_text:
        return ''
    cleaned = emoji_text.strip()
    cleaned = re.sub(r"[\u200B\u200C\u200D\uFEFF\u2060\u200E\u200F]", "", cleaned)
    return cleaned


def _parse_select_emoji(emoji_text: str) -> Optional[object]:
    text = _clean_emoji_text(emoji_text)
    if not text:
        return None
    # Custom server emoji like <a:name:123> -> PartialEmoji
    if re.match(r'^<a?:\w+:\d+>$', text):
        try:
            return discord.PartialEmoji.from_str(text)
        except Exception:
            return None

    # Accept common shortcodes and 2-letter codes for flags
    flag = _shortcode_to_flag(text)
    if flag:
        try:
            return discord.PartialEmoji(name=flag)
        except Exception:
            return flag

    # If the input is exactly two regional indicator characters, return as PartialEmoji first
    if _is_flag_emoji(text):
        try:
            return discord.PartialEmoji(name=text)
        except Exception:
            return text

    # For any other Unicode emoji, return the raw string (Discord accepts it)
    return text


class _RoleDropdown(discord.ui.Select):
    def __init__(self, entries: List[Tuple[str, discord.Role]] = None, single_choice: bool = False, remove_on_unselect: bool = True):
        # If entries is None or empty, create a dummy dropdown for view registration after bot restart
        if not entries:
            entries = []
            options = [discord.SelectOption(label="Loading...", value="0")]
        else:
            if len(entries) > 25:
                raise ValueError("A select menu can have at most 25 role options.")
            
            options = []
            for emoji_text, role in entries:
                try:
                    emoji = _parse_select_emoji(emoji_text)
                    # Prefer an explicit shortcode->flag conversion using the original token
                    display_flag = _shortcode_to_flag(emoji_text) or (emoji if isinstance(emoji, str) and _is_flag_emoji(emoji) else None)
                    label_text = role.name or ''
                    # Only use the `emoji` field for PartialEmoji (custom/server emoji).
                    if isinstance(emoji, discord.PartialEmoji):
                        options.append(discord.SelectOption(label=label_text[:100], value=str(role.id), emoji=emoji))
                    elif isinstance(emoji, str) and emoji:
                        used = display_flag or emoji
                        used = unicodedata.normalize('NFC', used)
                        if len(used) == 2 and used.isalpha():
                            used = _shortcode_to_flag(used) or used
                        max_role_len = max(0, 100 - len(used) - 1)
                        combined = f"{used} {label_text[:max_role_len]}"
                        options.append(discord.SelectOption(label=combined, value=str(role.id)))
                    else:
                        options.append(discord.SelectOption(label=label_text[:100], value=str(role.id)))
                except Exception as option_exc:
                    print(f"[Discord] Failed to create SelectOption for role {role.name}: {option_exc}")
                    raise
        
        # Use a fixed custom_id so the view persists across bot restarts
        super().__init__(placeholder="Choose your role...", min_values=0, max_values=1 if (single_choice and entries) else (len(entries) if entries else 1), options=options, custom_id="role_select_dropdown")
        self.role_ids = [role.id for _, role in entries] if entries else []
        self.single_choice = single_choice
        self.remove_on_unselect = remove_on_unselect

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception:
            try:
                await interaction.response.send_message("Processing...", ephemeral=True)
            except Exception:
                return

        await _process_role_dropdown_interaction(
            interaction,
            selected_values=self.values,
            role_ids=self.role_ids,
            single_choice=self.single_choice,
            remove_on_unselect=self.remove_on_unselect,
        )


async def _process_role_dropdown_interaction(
    interaction: discord.Interaction,
    selected_values: list[str],
    role_ids: list[int],
    single_choice: bool,
    remove_on_unselect: bool,
) -> None:
    guild = interaction.guild
    if guild is None:
        try:
            await interaction.followup.send("❌ This interaction must be used in a server.", ephemeral=True)
        except Exception:
            pass
        return

    member = guild.get_member(interaction.user.id)
    if member is None:
        try:
            member = await guild.fetch_member(interaction.user.id)
        except Exception:
            member = None

    if member is None:
        try:
            await interaction.followup.send("❌ Could not resolve your server membership.", ephemeral=True)
        except Exception:
            pass
        return

    if not role_ids:
        role_ids = _reaction_role_role_ids(str(guild.id), interaction.message.id if interaction.message else 0)

    selected_ids = {int(v) for v in selected_values}
    current_ids = {role.id for role in member.roles}

    to_add = [guild.get_role(rid) for rid in selected_ids if rid not in current_ids]
    to_add = [role for role in to_add if role]

    to_remove = []
    if remove_on_unselect:
        to_remove = [guild.get_role(rid) for rid in role_ids if rid not in selected_ids and rid in current_ids]
        to_remove = [role for role in to_remove if role]

    if single_choice:
        single_choice_remove = [guild.get_role(rid) for rid in role_ids if rid not in selected_ids and rid in current_ids]
        single_choice_remove = [role for role in single_choice_remove if role]
        for role in single_choice_remove:
            if role not in to_remove:
                to_remove.append(role)

    try:
        if to_add:
            await member.add_roles(*to_add, reason="Dropdown role assignment by Jarvis")
        if to_remove:
            await member.remove_roles(*to_remove, reason="Dropdown role assignment by Jarvis")

        if to_add or to_remove:
            await interaction.followup.send("✅ Your role selections have been updated.", ephemeral=True)
        else:
            await interaction.followup.send("ℹ️ No role changes were needed.", ephemeral=True)
    except discord.Forbidden:
        try:
            await interaction.followup.send("❌ I don't have permission to assign those roles.", ephemeral=True)
        except Exception:
            pass
    except discord.HTTPException as http_exc:
        try:
            await interaction.followup.send(f"❌ Discord API error: {http_exc.status}", ephemeral=True)
        except Exception:
            pass
    except Exception:
        try:
            await interaction.followup.send("❌ Failed to update roles.", ephemeral=True)
        except Exception:
            pass


class _RoleSelectView(discord.ui.View):
    def __init__(self, entries: List[Tuple[str, discord.Role]], single_choice: bool, remove_on_unselect: bool):
        super().__init__(timeout=None)
        self.add_item(_RoleDropdown(entries, single_choice=single_choice, remove_on_unselect=remove_on_unselect))


class _DeleteConfirmationView(discord.ui.View):
    def __init__(self, author_id: int, channel_id: int, message_id: int):
        super().__init__(timeout=120)
        self.author_id = author_id
        self.channel_id = channel_id
        self.message_id = message_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the user who requested this deletion may confirm it.",
                ephemeral=True,
            )
            return False
        return True

    async def _finish(self, interaction: discord.Interaction, content: str) -> None:
        for item in self.children:
            item.disabled = True
        try:
            await interaction.response.edit_message(content=content, view=self)
        except Exception:
            try:
                await interaction.followup.send(content=content, ephemeral=True)
            except Exception:
                pass
        self.stop()

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.client.get_channel(self.channel_id)
        if channel is None or not hasattr(channel, "fetch_message"):
            await interaction.response.send_message(
                "Unable to resolve the target channel for deletion.",
                ephemeral=True,
            )
            return
        try:
            target_message = await channel.fetch_message(self.message_id)
            await target_message.delete()
            await self._finish(
                interaction,
                f"Deleted message {self.message_id} in {channel.mention}",
            )
        except Exception as exc:
            await self._finish(
                interaction,
                f"Could not delete message {self.message_id}: {exc}",
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish(interaction, "Message deletion canceled.")


def _reaction_role_mappings(guild_id: str) -> Dict[str, str]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("reaction_roles", {})


def _reaction_role_settings(guild_id: str) -> Dict[str, Dict[str, bool]]:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.setdefault("reaction_role_settings", {})


def _set_reaction_role_mappings(guild_id: str, mappings: Dict[str, str]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["reaction_roles"] = mappings
    _set_discord_guild_data(guild_id, guild_data)


def _set_reaction_role_settings(guild_id: str, settings: Dict[str, Dict[str, bool]]) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["reaction_role_settings"] = settings
    _set_discord_guild_data(guild_id, guild_data)


def _reaction_role_key(message_id: int, emoji: str) -> str:
    return f"{message_id}:{emoji}"


def _get_reaction_role(guild_id: str, message_id: int, emoji: str) -> Optional[int]:
    mappings = _reaction_role_mappings(guild_id)
    role_id = mappings.get(_reaction_role_key(message_id, emoji))
    try:
        return int(role_id) if role_id is not None else None
    except (TypeError, ValueError):
        return None


def _get_reaction_role_menu_settings(guild_id: str, message_id: int) -> Dict[str, bool]:
    settings = _reaction_role_settings(guild_id).get(str(message_id), {})
    return {
        "single_choice": bool(settings.get("single_choice", False)),
        "remove_on_unreact": bool(settings.get("remove_on_unreact", True)),
    }


def _add_reaction_role(
    guild_id: str,
    message_id: int,
    emoji: str,
    role_id: int,
    single_choice: bool = False,
    remove_on_unreact: bool = True,
) -> None:
    mappings = _reaction_role_mappings(guild_id)
    mappings[_reaction_role_key(message_id, emoji)] = str(role_id)
    _set_reaction_role_mappings(guild_id, mappings)

    settings = _reaction_role_settings(guild_id)
    settings[str(message_id)] = {
        "single_choice": bool(single_choice),
        "remove_on_unreact": bool(remove_on_unreact),
    }
    _set_reaction_role_settings(guild_id, settings)


def _reaction_role_entries(guild: discord.Guild, message_id: int) -> List[Tuple[str, discord.Role]]:
    entries: List[Tuple[str, discord.Role]] = []
    guild_id = str(guild.id)
    mappings = _reaction_role_mappings(guild_id)
    prefix = f"{message_id}:"
    for key, role_id in mappings.items():
        if not key.startswith(prefix):
            continue
        emoji = key[len(prefix):]
        try:
            role = guild.get_role(int(role_id)) if role_id is not None else None
        except (TypeError, ValueError):
            role = None
        if role is not None:
            entries.append((emoji, role))
    return entries


def _extract_select_entries_from_message(message: discord.Message, guild: discord.Guild) -> List[Tuple[str, discord.Role]]:
    entries: List[Tuple[str, discord.Role]] = []
    for row in getattr(message, "components", []):
        for child in getattr(row, "children", []) or getattr(row, "components", []):
            options = getattr(child, "options", None)
            if not options:
                continue
            for opt in options:
                if not getattr(opt, "value", None):
                    continue
                try:
                    role = guild.get_role(int(opt.value))
                except (TypeError, ValueError):
                    role = None
                if role is None:
                    continue
                emoji_obj = getattr(opt, "emoji", None)
                if emoji_obj is not None:
                    emoji = str(emoji_obj)
                else:
                    emoji = opt.label.strip().split(" ", 1)[0]
                entries.append((emoji, role))
    return entries


def _register_reaction_role_menu(
    guild_id: str,
    message_id: int,
    entries: List[Tuple[str, discord.Role]],
    single_choice: bool = False,
    remove_on_unselect: bool = True,
) -> None:
    for emoji_text, role in entries:
        emoji = _parse_select_emoji(emoji_text)
        _add_reaction_role(
            guild_id,
            message_id,
            _normalize_emoji(emoji),
            role.id,
            single_choice=single_choice,
            remove_on_unreact=remove_on_unselect,
        )


def _remove_reaction_role(guild_id: str, message_id: int, emoji: str) -> bool:
    mappings = _reaction_role_mappings(guild_id)
    key = _reaction_role_key(message_id, emoji)
    if key in mappings:
        mappings.pop(key)
        _set_reaction_role_mappings(guild_id, mappings)
        return True
    return False


def _list_reaction_roles(guild_id: str) -> str:
    mappings = _reaction_role_mappings(guild_id)
    if not mappings:
        return "No reaction role mappings configured."
    lines = []
    for key, role_id in mappings.items():
        message_id, emoji = key.split(":", 1)
        settings = _get_reaction_role_menu_settings(guild_id, int(message_id))
        flags = []
        if settings.get("single_choice"):
            flags.append("single")
        if settings.get("remove_on_unreact"):
            flags.append("remove_on_unreact")
        suffix = f" ({', '.join(flags)})" if flags else ""
        lines.append(f"Message {message_id} → {emoji} → <@&{role_id}>{suffix}")
    return "\n".join(lines)


def _reaction_role_role_ids(guild_id: str, message_id: int) -> List[int]:
    mappings = _reaction_role_mappings(guild_id)
    role_ids = []
    prefix = f"{message_id}:"
    for key, role_id in mappings.items():
        if key.startswith(prefix):
            try:
                role_ids.append(int(role_id))
            except (TypeError, ValueError):
                continue
    return role_ids


def _get_voice_effect_for_guild(guild_id: str) -> str:
    guild_data = _get_discord_guild_data(guild_id)
    return guild_data.get("voice_effect", "none")


def _set_voice_effect_for_guild(guild_id: str, effect: str) -> None:
    guild_data = _get_discord_guild_data(guild_id)
    guild_data["voice_effect"] = effect
    _set_discord_guild_data(guild_id, guild_data)


def _format_effect_list() -> str:
    return ", ".join(VOICE_EFFECTS.keys())


def _conversation_history_key(guild_id: Optional[str], user_id: int, thread_id: Optional[int]) -> tuple[str, int, Optional[int]]:
    return (guild_id or "dm", user_id, thread_id)


def _append_conversation_history(bot: "DiscordBot", guild_id: Optional[str], user_id: int, thread_id: Optional[int], role: str, content: str) -> None:
    key = _conversation_history_key(guild_id, user_id, thread_id)
    history = bot._conversation_histories.setdefault(key, [])
    history.append({"role": role, "content": content})
    if len(history) > 6:
        history.pop(0)


def _build_conversation_prompt(bot: Optional["DiscordBot"], guild_id: Optional[str], user_id: int, thread_id: Optional[int], question: str) -> str:
    personality = _get_personality_prompt(guild_id or "")
    history = []
    if bot is not None:
        history = bot._conversation_histories.get(_conversation_history_key(guild_id, user_id, thread_id), [])

    conversation_instruction = (
        "This is an ongoing conversation. Keep your responses natural and conversational. "
        "Stay engaged while the user is talking directly to you, and keep the dialogue moving in a friendly way. "
        "If the user switches to someone else or clearly ends the conversation, stop responding. "
        "Do not interrupt other conversations or answer when the user is addressing another person."
    )

    prompt_parts = [personality, "", conversation_instruction, ""]
    prompt_parts.append(
        "If the user continues the same thread or replies to your message, answer as if the conversation is ongoing even if they do not say 'Jarvis' again. "
        "Only stop responding when the user clearly switches to someone else or ends the conversation."
    )
    prompt_parts.append("")
    for message in history:
        prompt_parts.append(f"{message['role'].capitalize()}: {message['content']}")
    prompt_parts.append(f"User: {question}")
    prompt_parts.append("Assistant:")
    return "\n".join(prompt_parts)


async def _query_discord_ai(
    question: str,
    guild_id: Optional[str] = None,
    user_id: Optional[int] = None,
    bot: Optional["DiscordBot"] = None,
    thread_id: Optional[int] = None,
) -> str:
    try:
        genai = _load_google_gemini_module()
    except ImportError:
        return "Sorry, I cannot answer right now because the AI package is not installed."

    try:
        if hasattr(genai, "Client"):
            client = genai.Client(api_key=_get_gemini_api_key())
            use_google_genai = True
        else:
            genai.configure(api_key=_get_gemini_api_key())
            model = genai.GenerativeModel("gemini-2.5-flash-lite")
            use_google_genai = False

        if guild_id and user_id and bot is not None:
            prompt = _build_conversation_prompt(bot, guild_id, user_id, thread_id, question)
        else:
            prompt = (
                "You are Jarvis, a helpful and polite Discord assistant. "
                "Only respond when the user is speaking to you. If the user appears to be talking to someone else, do not answer. "
                "Keep your tone friendly, conversational, and curious. If the conversation continues, feel free to ask follow-up questions that help keep the dialog going.\n\n"
                f"Message: {question.strip()}\n\nResponse:"
            )

        def extract_text_from_response(response):
            # google.genai response uses candidates -> content -> parts -> text
            if response is None:
                return ""
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
            if hasattr(response, 'candidates') and response.candidates:
                texts = []
                for candidate in response.candidates:
                    content = getattr(candidate, 'content', None)
                    if content is None:
                        continue
                    if hasattr(content, 'text') and content.text:
                        texts.append(str(content.text).strip())
                        continue
                    parts = getattr(content, 'parts', None)
                    if parts:
                        for part in parts:
                            part_text = getattr(part, 'text', None)
                            if part_text:
                                texts.append(str(part_text).strip())
                if texts:
                    return '\n'.join(t for t in texts if t)
            if hasattr(response, '__str__'):
                return str(response).strip()
            return ""

        def generate():
            last_error = None
            if use_google_genai:
                models_to_try = _get_available_gemini_models()
                for model_name in models_to_try:
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                        )
                        text = extract_text_from_response(response)
                        if text:
                            return text
                        _debug_ai('Gemini response empty for model', model_name, 'response=', response)
                    except Exception as exc:
                        last_error = exc
                        status_code = getattr(exc, 'status_code', None)
                        message = str(exc)
                        if status_code == 429 or 'RESOURCE_EXHAUSTED' in message:
                            _debug_ai('Gemini rate limit hit:', model_name, type(exc).__name__, exc)
                            if _get_openai_api_key():
                                _debug_ai('Attempting OpenAI fallback due to Gemini rate limit.')
                                openai_answer = _query_openai_ai(prompt)
                                if openai_answer:
                                    return openai_answer
                            retry_delay = None
                            try:
                                details = exc.args[1] if len(exc.args) > 1 else None
                                if isinstance(details, dict):
                                    retry_info = details.get('error', {}).get('details', [])
                                    for item in retry_info:
                                        if item.get('@type', '').endswith('RetryInfo'):
                                            retry_delay = item.get('retryDelay')
                                            break
                            except Exception:
                                retry_delay = None
                            if retry_delay:
                                return f"Sorry, Gemini is temporarily rate-limited. Please retry after {retry_delay}."
                            return "Sorry, Gemini is temporarily rate-limited. Please try again in a little while."
                        if status_code == 404 or 'NOT_FOUND' in message:
                            _debug_ai('Gemini unsupported model skipped:', model_name, type(exc).__name__, exc)
                            continue
                        _debug_ai('Gemini model failed:', model_name, type(exc).__name__, exc)
                        continue
                if last_error:
                    _debug_ai('Gemini all models failed, trying OpenAI fallback.', last_error)
                    if _get_openai_api_key():
                        openai_answer = _query_openai_ai(prompt)
                        if openai_answer:
                            return openai_answer
                    return ""
                return ""
            else:
                try:
                    response = model.generate_content(prompt)
                    text = extract_text_from_response(response)
                    if text:
                        return text
                    _debug_ai('Legacy Gemini response empty', response)
                except Exception as exc:
                    _debug_ai('Legacy Gemini model failed:', type(exc).__name__, exc)
                    if _get_openai_api_key():
                        openai_answer = _query_openai_ai(prompt)
                        if openai_answer:
                            return openai_answer
                    raise
                return ""

        answer = await asyncio.to_thread(generate)
        if not answer:
            return "Sorry, I couldn't come up with an answer right now."

        if guild_id and user_id and bot is not None:
            _append_conversation_history(bot, guild_id, user_id, thread_id, "user", question.strip())
            _append_conversation_history(bot, guild_id, user_id, thread_id, "assistant", answer)
        return answer
    except KeyError as exc:
        _debug_ai('Gemini API key error:', exc)
        return "Sorry, I couldn't answer that because Gemini API key is missing or invalid."
    except Exception as exc:
        _debug_ai('Gemini exception:', type(exc).__name__, exc)
        if _AI_DEBUG or _FOLLOWUP_DEBUG:
            traceback.print_exc()
        return "Sorry, I couldn't answer that right now."


def _resolve_youtube_audio_source(query: str) -> dict | None:
    if not _YTDLP_AVAILABLE:
        return None

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'prefer_free_formats': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
    except Exception:
        # Some videos (age-restricted, premium) may fail without JavaScript runtime.
        # Fallback gracefully instead of crashing.
        return None

    if info is None:
        return None
    if isinstance(info, dict) and info.get('entries'):
        info = info['entries'][0]

    return info if isinstance(info, dict) else None


def _get_music_cache_dir() -> Path:
    cache_dir = Path(tempfile.gettempdir()) / 'jarvis_discord_music_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _clean_old_cached_audio(retention_days: int = 7) -> None:
    cache_dir = _get_music_cache_dir()
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=retention_days)
    for path in cache_dir.iterdir():
        try:
            if not path.is_file():
                continue
            modified = datetime.datetime.utcfromtimestamp(path.stat().st_mtime)
            if modified < cutoff:
                path.unlink()
        except Exception:
            continue


def _get_temporary_delete_seconds() -> int:
    return 30


def _is_playback_response(text: str) -> bool:
    normalized = text.lower()
    playback_indicators = [
        'now playing',
        'queued track',
        'added to the queue',
        'queued track:',
        'music playback paused',
        'music playback resumed',
        'stopped playback',
        'skipped the current track',
        'upcoming queue',
        'no music is currently queued or playing',
    ]
    return any(indicator in normalized for indicator in playback_indicators)


async def _reply_interaction(
    interaction: discord.Interaction,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    delete_after: Optional[int] = None,
    ephemeral: bool = False,
    **kwargs,
):
    async def _send_channel_fallback() -> Optional[discord.Message]:
        if 'poll' in kwargs:
            return None
        try:
            chan = interaction.channel
            if chan:
                msg = await chan.send(content or '', embed=embed, delete_after=delete_after, **kwargs)
                return msg
        except Exception as e:
            print(f"[DiscordBot] channel.send fallback failed: {e}")
        return None

    async def _schedule_delete(msg: discord.Message) -> None:
        if not msg:
            return
        try:
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                return
            loop.create_task(_delete_message_later(msg, delete_after))
        except Exception:
            pass

    try:
        if interaction.response.is_done():
            try:
                msg = await interaction.followup.send(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral,
                    **kwargs,
                )
                if delete_after and msg is not None:
                    await _schedule_delete(msg)
                return msg
            except Exception as e:
                print(f"[DiscordBot] followup.send failed: {e}")
                return await _send_channel_fallback()

        try:
            msg = await interaction.response.send_message(
                content=content,
                embed=embed,
                delete_after=delete_after,
                ephemeral=ephemeral,
                **kwargs,
            )
            if delete_after and msg is not None:
                await _schedule_delete(msg)
            return msg
        except Exception as e:
            print(f"[DiscordBot] response.send_message failed: {e}")
            if interaction.response.is_done():
                return await _send_channel_fallback()
            try:
                msg = await interaction.followup.send(
                    content=content,
                    embed=embed,
                    ephemeral=ephemeral,
                    **kwargs,
                )
                if delete_after and msg is not None:
                    await _schedule_delete(msg)
                return msg
            except Exception as e2:
                print(f"[DiscordBot] followup fallback failed: {e2}")
                return await _send_channel_fallback()
    except Exception as exc:
        print(f"[DiscordBot] Unexpected reply failure: {exc}")
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    'Unable to deliver the response. Check the bot permissions and channel settings.',
                    ephemeral=True,
                )
        except Exception as final_exc:
            print(f"[DiscordBot] Could not notify user about reply failure: {final_exc}")


async def _delete_message_later(message: discord.Message, delay_seconds: int) -> None:
    try:
        await asyncio.sleep(delay_seconds)
        try:
            await message.delete()
        except Exception:
            pass
    except Exception:
        pass


DEFAULT_ELEVENLABS_VOICE_ID = "DYkrAHD8iwork3YSUBbs"
GEMINI_TTS_MODEL = "models/gemini-2.5-flash-preview-tts"
GEMINI_TTS_VOICE = "Charon"


def _parse_pcm_rate_from_mime(mime_type: str) -> int:
    for part in mime_type.split(';'):
        part = part.strip()
        if part.startswith('rate='):
            try:
                return int(part.split('=', 1)[1])
            except Exception:
                pass
    return 24000


def _write_pcm16_wav(file_path: Path, pcm_bytes: bytes, sample_rate: int = 24000, channels: int = 1) -> None:
    import wave

    with wave.open(str(file_path), 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)


def _extract_audio_bytes_from_genai_response(resp):
    if resp is None:
        return None, None

    if hasattr(resp, 'parts') and resp.parts:
        for part in resp.parts:
            inline = getattr(part, 'inline_data', None)
            if inline is not None:
                if hasattr(inline, 'data') and isinstance(inline.data, (bytes, bytearray)):
                    return bytes(inline.data), getattr(inline, 'mime_type', '')
                if isinstance(inline, (bytes, bytearray)):
                    return bytes(inline), getattr(inline, 'mime_type', '')

            file_data = getattr(part, 'file_data', None)
            if file_data is not None:
                if hasattr(file_data, 'data') and isinstance(file_data.data, (bytes, bytearray)):
                    return bytes(file_data.data), getattr(file_data, 'mime_type', '')
                if isinstance(file_data, (bytes, bytearray)):
                    return bytes(file_data), getattr(file_data, 'mime_type', '')

    if hasattr(resp, 'audio') and isinstance(resp.audio, (bytes, bytearray)):
        return bytes(resp.audio), ''
    if hasattr(resp, 'content') and isinstance(resp.content, (bytes, bytearray)):
        return bytes(resp.content), ''
    if hasattr(resp, 'binary') and isinstance(resp.binary, (bytes, bytearray)):
        return bytes(resp.binary), ''

    return None, None


def _synthesize_high_quality_tts(text: str) -> Optional[str]:
    """
    Synthesize `text` to a WAV file.
    Priority: Gemini (Google genai) -> ElevenLabs -> Coqui TTS.
    Returns path to WAV file or None on failure.
    """
    tmp_path = Path(tempfile.gettempdir()) / f"jarvis_discord_tts_{int(datetime.datetime.utcnow().timestamp())}.wav"

    def _save_audio_bytes(audio_bytes: bytes, mime_type: str | None) -> bool:
        try:
            if mime_type and 'audio/l16' in mime_type.lower():
                sample_rate = _parse_pcm_rate_from_mime(mime_type)
                _write_pcm16_wav(tmp_path, audio_bytes, sample_rate=sample_rate, channels=1)
            else:
                tmp_path.write_bytes(audio_bytes)
            return True
        except Exception as e:
            print(f"[TTS] Error saving audio bytes: {e}")
            return False

    # 1) Try Gemini / Google GenAI TTS if configured
    try:
        print("[TTS] Attempting Gemini TTS...")
        genai = None
        for module_name in ('google.genai', 'google.generativeai'):
            try:
                genai = __import__(module_name, fromlist=['*'])
                print(f"[TTS] Loaded {module_name}")
                break
            except Exception as e:
                print(f"[TTS] Failed to load {module_name}: {e}")
                genai = None

        if genai is not None:
            try:
                client_cls = getattr(genai, 'Client', None)
                types_module = getattr(genai, 'types', None)

                if client_cls is not None:
                    print("[TTS] Creating Gemini client...")
                    client = client_cls(api_key=_get_gemini_api_key())
                    config = None
                    if types_module is not None:
                        config = types_module.GenerateContentConfig(
                            responseModalities=['AUDIO'],
                            speechConfig=types_module.SpeechConfig(
                                voiceConfig=types_module.VoiceConfig(
                                    prebuiltVoiceConfig=types_module.PrebuiltVoiceConfig(
                                        voiceName=GEMINI_TTS_VOICE
                                    )
                                )
                            )
                        )

                    contents = text
                    if types_module is not None and hasattr(types_module, 'TextContent'):
                        contents = [types_module.TextContent(text=text)]

                    kwargs = {'model': GEMINI_TTS_MODEL, 'contents': contents}
                    if config is not None:
                        kwargs['config'] = config

                    print(f"[TTS] Calling Gemini generate_content with model {GEMINI_TTS_MODEL}...")
                    resp = client.models.generate_content(**kwargs)
                    print(f"[TTS] Got response: {type(resp)}")
                    audio_bytes, mime_type = _extract_audio_bytes_from_genai_response(resp)
                    print(f"[TTS] Extracted audio: {len(audio_bytes) if audio_bytes else 0} bytes, mime={mime_type}")
                    if audio_bytes and _save_audio_bytes(audio_bytes, mime_type):
                        print("[TTS] Successfully saved Gemini TTS audio")
                        return str(tmp_path)
                    else:
                        print("[TTS] Failed to extract or save audio bytes from Gemini response")
            except Exception as e:
                print(f"[TTS] Gemini first attempt failed: {e}")
                pass

            try:
                print("[TTS] Attempting Gemini via GenerativeModel...")
                if hasattr(genai, 'configure'):
                    genai.configure(api_key=_get_gemini_api_key())
                generative_model_cls = getattr(genai, 'GenerativeModel', None)
                if generative_model_cls is not None:
                    model = generative_model_cls(GEMINI_TTS_MODEL)
                    gen = getattr(model, 'generate_audio', None) or getattr(model, 'generate_content', None)
                    if gen is not None:
                        print("[TTS] Calling GenerativeModel...")
                        resp = gen(text)
                        print(f"[TTS] Got response: {type(resp)}")
                        audio_bytes, mime_type = _extract_audio_bytes_from_genai_response(resp)
                        print(f"[TTS] Extracted audio: {len(audio_bytes) if audio_bytes else 0} bytes, mime={mime_type}")
                        if audio_bytes and _save_audio_bytes(audio_bytes, mime_type):
                            print("[TTS] Successfully saved GenerativeModel TTS audio")
                            return str(tmp_path)
                        else:
                            print("[TTS] Failed to extract or save audio from GenerativeModel")
            except Exception as e:
                print(f"[TTS] Gemini second attempt failed: {e}")
                pass
    except Exception as e:
        print(f"[TTS] Gemini TTS completely failed: {e}")
        pass

    # 2) Try ElevenLabs if configured
    print("[TTS] Attempting ElevenLabs TTS...")
    try:
        cfg_path = _base_dir() / "config" / "api_keys.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            eleven_key = cfg.get("elevenlabs_api_key") or cfg.get("elevenlabs_key")
            voice_id = cfg.get("elevenlabs_voice") or cfg.get("eleven_voice") or DEFAULT_ELEVENLABS_VOICE_ID
            if eleven_key:
                print(f"[TTS] ElevenLabs key found, using voice {voice_id}")
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "xi-api-key": eleven_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/wav",
                }
                payload = {
                    "text": text,
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
                }
                try:
                    print("[TTS] Calling ElevenLabs API...")
                    resp = requests.post(url, headers=headers, json=payload, timeout=30)
                    print(f"[TTS] ElevenLabs response: {resp.status_code}")
                    if resp.status_code >= 200 and resp.status_code < 300 and resp.content:
                        tmp_path.write_bytes(resp.content)
                        print("[TTS] Successfully saved ElevenLabs TTS audio")
                        return str(tmp_path)
                    else:
                        print(f"[TTS] ElevenLabs failed with status {resp.status_code}")
                except Exception as e:
                    print(f"[TTS] ElevenLabs call failed: {e}")
                    pass
            else:
                print("[TTS] No ElevenLabs API key found")
        else:
            print("[TTS] No API keys config file found")
    except Exception as e:
        print(f"[TTS] ElevenLabs attempt failed: {e}")
        pass

    # 3) Try Coqui TTS (TTS package)
    print("[TTS] Attempting Coqui TTS...")
    try:
        from TTS.api import TTS
        try:
            print("[TTS] Loading default Coqui model...")
            tts = TTS()
            tts.tts_to_file(text=text, file_path=str(tmp_path))
            print("[TTS] Successfully saved Coqui TTS audio (default)")
            return str(tmp_path)
        except Exception as e:
            print(f"[TTS] Default Coqui model failed: {e}")
            try:
                print("[TTS] Trying Tacotron2 Coqui model...")
                tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC")
                tts.tts_to_file(text=text, file_path=str(tmp_path))
                print("[TTS] Successfully saved Coqui TTS audio (tacotron2)")
                return str(tmp_path)
            except Exception as e2:
                print(f"[TTS] Tacotron2 model failed: {e2}")
                pass
    except Exception as e:
        print(f"[TTS] Coqui TTS import/attempt failed: {e}")
        pass

    print("[TTS] All TTS methods failed, returning None")
    return None


def _get_yt_dlp_js_runtime_status() -> Optional[str]:
    if not _YTDLP_AVAILABLE:
        return None

    try:
        from yt_dlp.utils import _jsruntime

        runtime_classes = [
            _jsruntime.DenoJsRuntime,
            _jsruntime.BunJsRuntime,
            _jsruntime.NodeJsRuntime,
            _jsruntime.QuickJsRuntime,
        ]

        supported = []
        available = []
        for runtime_cls in runtime_classes:
            info = runtime_cls().info
            if info is None:
                continue
            available.append(f'{info.name} {info.version}')
            if info.supported:
                supported.append(f'{info.name} {info.version}')

        if supported:
            return f'Supported JS runtime detected: {", ".join(supported)}.'
        if available:
            return (
                'No supported JS runtime detected. ' 
                f'Detected runtimes: {", ".join(available)}. ' 
                'Install a supported runtime such as deno or node.'
            )
        return (
            'No JavaScript runtime detected for yt-dlp. ' 
            'Install deno, node, bun, or quickjs and restart Jarvis.'
        )
    except Exception:
        return None


def _is_ffmpeg_available() -> bool:
    return shutil.which('ffmpeg') is not None or shutil.which('ffmpeg.exe') is not None


def _make_ffmpeg_opus_source(file_path: str, extra_options: str = ''):
    """Return a discord audio source preferring Opus (FFmpegOpusAudio) with fallback to PCM."""
    try:
        # Try Opus source first
        opus_cls = getattr(discord, 'FFmpegOpusAudio', None)
        if opus_cls is not None:
            opts = f"-vn -ac 2 -ar 48000 {extra_options}".strip()
            return opus_cls(file_path, executable='ffmpeg', options=opts)
    except Exception:
        pass

    # Fallback to PCM audio source
    try:
        pcm = discord.FFmpegPCMAudio(file_path, executable='ffmpeg', options=f"-vn -ac 2 -ar 48000 {extra_options}".strip())
        return pcm
    except Exception:
        # Last resort: raise to caller
        raise


def _download_youtube_audio_to_file(query: str) -> tuple[Path, str] | None:
    if not _YTDLP_AVAILABLE:
        return None

    _clean_old_cached_audio(retention_days=7)
    cache_dir = _get_music_cache_dir()
    out_template = str(cache_dir / '%(id)s.%(ext)s')

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'outtmpl': out_template,
        'noplaylist': True,
        'default_search': 'ytsearch',
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'prefer_free_formats': True,
        'nooverwrites': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
    except Exception as e:
        print(f"[DiscordBot] yt-dlp download error for query '{query}': {e}")
        return None

    if info is None:
        return None
    if isinstance(info, dict) and info.get('entries'):
        info = info['entries'][0]

    filename = None
    if isinstance(info, dict):
        if info.get('requested_downloads'):
            filename = info['requested_downloads'][0].get('filepath')
        filename = filename or info.get('filepath') or info.get('_filename')

    if not filename:
        return None

    audio_path = Path(filename)
    if not audio_path.exists():
        alternate = cache_dir / f"{info.get('id')}.m4a"
        if alternate.exists():
            audio_path = alternate
        else:
            return None

    title = info.get('title') or audio_path.stem.replace('_', ' ')
    return audio_path, title


async def _play_music_in_voice_channel(query: str, notify_channel_id: Optional[int] = None) -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    if not _DISCORD_VOICE_AVAILABLE:
        missing = []
        if not _DISCORD_NACL_AVAILABLE:
            missing.append('PyNaCl')
        if not _DISCORD_DAVEY_AVAILABLE:
            missing.append('davey')
        return (
            'Discord voice support requires the following packages: ' \
            f"{', '.join(missing)}. Install them with `pip install {' '.join(name.lower() for name in missing)}` and restart Jarvis."
        )

    if not _YTDLP_AVAILABLE:
        return (
            'Music playback requires yt-dlp. Install it with `pip install yt-dlp` '
            'and restart Jarvis.'
        )

    if not _is_ffmpeg_available():
        return (
            'ffmpeg is not available on your system PATH. Install ffmpeg and restart Jarvis. '
            'On Windows, add ffmpeg to PATH or place ffmpeg.exe in the same directory as Jarvis.'
        )

    if not query or not query.strip():
        return 'Please provide a song name or YouTube link to play.'

    voice_client = bot._get_any_connected_voice_client()
    if voice_client is None or not voice_client.is_connected():
        return 'I am not connected to a Discord voice channel. Ask me to join your voice channel first.'

    runtime_status = _get_yt_dlp_js_runtime_status()
    if runtime_status and 'No supported' in runtime_status:
        runtime_status = runtime_status + ' You may still be able to play content, but installation of a supported runtime is recommended.'

    result = await bot.enqueue_music(query, notify_channel_id=notify_channel_id)
    if runtime_status:
        return f"{result} {runtime_status}"
    return result





class DiscordBot:
    def __init__(self):
        self.token = _get_discord_token()
        self.client = None
        self.is_running = False
        self._is_ready = False
        self.last_messages = {}
        self._active_conversations: Dict[tuple[str, int, Optional[int]], datetime.datetime] = {}
        self._conversation_histories: Dict[tuple[str, int, Optional[int]], List[Dict[str, str]]] = {}
        # Track last bot message (message_id, timestamp) per conversation key
        self._last_bot_messages: Dict[tuple[str, int, Optional[int]], tuple[int, datetime.datetime]] = {}
        self._guild_data_lock = threading.Lock()
        self._loop = None
        self._thread = None
        self._ready_event = threading.Event()
        self._startup_lock = threading.Lock()
        self._status_callback: Optional[Callable[[str], None]] = None
        self.music_queue: List[Dict] = []
        self._poll_metadata: Dict[int, Dict[str, object]] = {}
        self._poll_close_tasks: Dict[int, asyncio.Task] = {}
        self._temp_admin_tasks: Dict[tuple[int, int], asyncio.Task] = {}
        self._poll_image_picker_callback: Optional[Callable[[], List[str]]] = None
        self.music_task = None
        self.music_current: Optional[str] = None
        self.music_current_path: Optional[Path] = None
        self.music_started_at: Optional[datetime.datetime] = None
        self._tts_speaking = False
        self._voice_receive_callbacks: Dict[int, callable] = {}
        self._voice_receive_buffers: Dict[int, List[bytes]] = {}
        self._voice_buffer_timers: Dict[int, asyncio.TimerHandle] = {}
        self._scheduler_task: Optional[asyncio.Task] = None
        self._watcher_thread: Optional[threading.Thread] = None
        self._watcher_stop = threading.Event()
        self._auto_restart_enabled = False
        self._intentional_stop = False
        self._status = "OFFLINE"
        self._restart_backoff = 1.0
        self._restart_attempts = 0
        self._extensions_initialized = False
        self._birthday_tracker: Optional[BirthdayTracker] = None

    def _initialize_discord_extensions(self):
        if self._extensions_initialized:
            return

        try:
            self._birthday_tracker = BirthdayTracker(self.client)
        except Exception as exc:
            print(f"[DiscordBot] Failed to initialize BirthdayTracker: {exc}")

        self._extensions_initialized = True

    def _create_client(self):
        intents = discord.Intents.all()
        if hasattr(intents, "message_content"):
            intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.tree = discord.app_commands.CommandTree(self.client)

        original_command = self.tree.command
        def safe_command(*args, **kwargs):
            def decorator(func):
                @functools.wraps(func)
                async def wrapped(*func_args, **func_kwargs):
                    try:
                        return await func(*func_args, **func_kwargs)
                    except Exception as exc:
                        print(f"[DiscordBot] Command {func.__name__} failed: {exc}")
                        traceback.print_exc()
                        if func_args:
                            interaction = func_args[0]
                            try:
                                await _reply_interaction(
                                    interaction,
                                    'An internal error occurred while processing this command. Please try again later.',
                                    ephemeral=True,
                                )
                            except Exception as fallback_exc:
                                print(f"[DiscordBot] Command error fallback failed: {fallback_exc}")
                return original_command(*args, **kwargs)(wrapped)
            return decorator
        self.tree.command = safe_command

        # Register built-in cogs for moderation and gamification
        try:
            self._moderation = ModerationCog(self.tree)
            self._gamification = GamificationCog(self.tree, self.client)
            self._settings_cog = SettingsCog(self.tree)
            print(f"[DiscordBot] Registered commands: {[cmd.name for cmd in self.tree.walk_commands()]}")
        except Exception as e:
            print(f"[DiscordBot] Failed to initialize cogs: {e}")

        @self.client.event
        async def on_ready():
            self._is_ready = True
            print(f"Discord bot logged in as {self.client.user}")
            print(f"[DiscordBot] Connected guilds: {[(g.id, g.name) for g in self.client.guilds]}")
            
            # Register persistent view for role dropdowns
            # This allows dropdowns to work after bot restarts
            try:
                temp_view = _RoleSelectView([], single_choice=False, remove_on_unselect=True)
                self.client.add_view(temp_view)
                print("[DiscordBot] ✅ Registered persistent role dropdown view")
            except Exception as view_err:
                print(f"[DiscordBot] Could not register view: {view_err}")
            
            self._ready_event.set()
            self._update_status("ONLINE")
            try:
                await self.client.change_presence(
                    activity=discord.Game("Jarvis is listening"),
                    status=discord.Status.online
                )
            except Exception:
                pass
            try:
                self._initialize_discord_extensions()
            except Exception:
                pass
            try:
                print("[DiscordBot] on_ready: starting command sync...")
                await self.tree.sync()
                print("[DiscordBot] ✅ Discord slash commands synced.")
                print(f"[DiscordBot] Synced commands: {[cmd.name for cmd in self.tree.walk_commands()]}")
            except Exception as e:
                print(f"[DiscordBot] ❌ Slash command sync failed: {type(e).__name__}: {e}")
                traceback.print_exc()

            try:
                for guild in self.client.guilds:
                    await self.tree.sync(guild=guild)
                    print(f"[DiscordBot] ✅ Synced commands for guild {guild.id}: {[cmd.name for cmd in self.tree.walk_commands()]}")
            except Exception as e:
                print(f"[DiscordBot] ❌ Guild sync failed: {type(e).__name__}: {e}")
                traceback.print_exc()

            try:
                for guild in self.client.guilds:
                    await _ensure_jarvis_admin_role_for_bot(guild, self.client)
                    print(f"[DiscordBot] ✅ Ensured Jarvis admin role in guild {guild.id}")
            except Exception as e:
                print(f"[DiscordBot] ❌ Could not ensure Jarvis admin role for a guild: {type(e).__name__}: {e}")
                traceback.print_exc()

            if self._scheduler_task is None or self._scheduler_task.done():
                self._scheduler_task = asyncio.create_task(self._run_scheduler())

        @self.client.event
        async def on_disconnect():
            if self._intentional_stop or not self._auto_restart_enabled:
                self._update_status("OFFLINE")
            else:
                self._update_status("RECONNECTING")

        @self.client.event
        async def on_interaction(interaction: discord.Interaction):
            if interaction.type != discord.InteractionType.component:
                return
            if interaction.guild is None or interaction.message is None:
                return

            guild_id = str(interaction.guild.id)
            message_id = interaction.message.id
            menu_settings = _get_reaction_role_menu_settings(guild_id, message_id)
            if not menu_settings:
                return

            values = interaction.data.get("values") if isinstance(interaction.data, dict) else None
            if not values:
                return

            try:
                await interaction.response.defer(ephemeral=True)
            except Exception:
                try:
                    await interaction.response.send_message("Processing...", ephemeral=True)
                except Exception:
                    return

            role_ids = _reaction_role_role_ids(guild_id, message_id)
            await _process_role_dropdown_interaction(
                interaction,
                selected_values=values,
                role_ids=role_ids,
                single_choice=menu_settings.get("single_choice", False),
                remove_on_unselect=menu_settings.get("remove_on_unreact", True),
            )

        @self.tree.command(name="join_voice", description="Join a Discord voice channel.")
        @discord.app_commands.describe(channel_id="Optional voice channel ID to join.")
        async def join_voice(interaction: discord.Interaction, channel_id: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            target_channel = None
            if channel_id:
                target_channel = await self._fetch_channel_by_id(channel_id)
            elif interaction.user.voice and interaction.user.voice.channel:
                target_channel = interaction.user.voice.channel

            if isinstance(target_channel, discord.VoiceChannel):
                connected = await self._ensure_voice_connection(target_channel)
                if connected:
                    await _reply_interaction(interaction, f"Joined voice channel {target_channel.name}.", delete_after=30)
                else:
                    await _reply_interaction(interaction, "I couldn't join that voice channel. Please check my permissions.", delete_after=30)
            else:
                await _reply_interaction(interaction, 
                    "I couldn't find a voice channel to join. Use /join_voice or provide a valid voice channel ID."
                , delete_after=30)

        @self.tree.command(name="leave_voice", description="Leave the current Discord voice channel.")
        async def leave_voice(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            voice_client = self.client.voice_clients[0] if self.client.voice_clients else None
            if voice_client and voice_client.is_connected():
                channel_name = voice_client.channel.name if voice_client.channel else "unknown"
                await voice_client.disconnect()
                await _reply_interaction(interaction, f"Left voice channel {channel_name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, "I'm not currently connected to a voice channel.", delete_after=30)

        @self.tree.command(name="list_voice", description="List available Discord voice channels.")
        async def list_voice(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            voice_channels = await self.get_voice_channels()
            if voice_channels:
                lines = [f"**{vc['guild']}** - {vc['name']} (ID: {vc['id']})" for vc in voice_channels]
                await _reply_interaction(interaction, "Available voice channels:\n" + "\n".join(lines), delete_after=30)
            else:
                await _reply_interaction(interaction, "I couldn't find any voice channels.", delete_after=30)

        @self.tree.command(name="speak", description="Speak a message in Discord voice.")
        @discord.app_commands.describe(message="What Jarvis should say in voice.", channel_id="Optional voice channel ID to join before speaking.")
        async def speak(interaction: discord.Interaction, message: str, channel_id: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            target_channel = None
            if channel_id:
                target_channel = await self._fetch_channel_by_id(channel_id)
            elif interaction.user.voice and interaction.user.voice.channel:
                target_channel = interaction.user.voice.channel

            if target_channel and isinstance(target_channel, discord.VoiceChannel):
                connected = await self._ensure_voice_connection(target_channel)
                if not connected:
                    await _reply_interaction(interaction, "I couldn't join that voice channel. Please check my permissions.", delete_after=30)
                    return
            voice_client = self.client.voice_clients[0] if self.client.voice_clients else None
            if voice_client and voice_client.is_connected():
                await _speak_in_voice_channel(message)
                await _reply_interaction(interaction, "Spoken in voice channel.", delete_after=30)
            else:
                await _reply_interaction(interaction, "I need to be connected to a voice channel to speak.", delete_after=30)

        @self.tree.command(name="help", description="Show available Jarvis commands.")
        async def help_command(interaction: discord.Interaction):
            await interaction.response.send_message(embed=_build_discord_help_embed(interaction.user), ephemeral=True)

        @self.tree.command(name="jarvis_help", description="Show Jarvis Discord help.")
        async def jarvis_help(interaction: discord.Interaction):
            await interaction.response.send_message(embed=_build_discord_help_embed(interaction.user), ephemeral=True)

        @self.tree.command(name="set_personality", description="Set the server-specific Jarvis personality prompt.")
        @discord.app_commands.describe(prompt="The personality prompt to use for this server.")
        async def set_personality(interaction: discord.Interaction, prompt: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change the personality prompt.", delete_after=30)
                return
            _set_personality_prompt(str(interaction.guild.id), prompt)
            await _reply_interaction(interaction, "Server personality prompt updated.", delete_after=30)

        @self.tree.command(name="set_response_tone", description="Set Jarvis' response tone for this server.")
        @discord.app_commands.describe(tone="A short tone description, like polite, direct, or playful.")
        async def set_response_tone(interaction: discord.Interaction, tone: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change the response tone.", delete_after=30)
                return
            _set_response_tone(str(interaction.guild.id), tone)
            await _reply_interaction(interaction, f"Response tone set to `{tone}`.", delete_after=30)

        @self.tree.command(name="set_welcome_channel", description="Set the channel for welcome messages.")
        @discord.app_commands.describe(channel_id="Channel ID to send welcome messages.")
        async def set_welcome_channel(interaction: discord.Interaction, channel_id: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the welcome channel.", delete_after=30)
                return
            _set_welcome_channel_id(str(interaction.guild.id), channel_id)
            await _reply_interaction(interaction, "Welcome channel configured.", delete_after=30)

        @self.tree.command(name="set_goodbye_channel", description="Set the channel for goodbye messages.")
        @discord.app_commands.describe(channel_id="Channel ID to send goodbye messages.")
        async def set_goodbye_channel(interaction: discord.Interaction, channel_id: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the goodbye channel.", delete_after=30)
                return
            _set_goodbye_channel_id(str(interaction.guild.id), channel_id)
            await _reply_interaction(interaction, "Goodbye channel configured.", delete_after=30)

        @self.tree.command(name="set_welcome_message", description="Set the welcome message template.")
        @discord.app_commands.describe(message="Template text, use {member} and {server}.")
        async def set_welcome_message(interaction: discord.Interaction, message: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change the welcome message.", delete_after=30)
                return
            _set_welcome_message(str(interaction.guild.id), message)
            await _reply_interaction(interaction, "Welcome message template updated.", delete_after=30)

        @self.tree.command(name="set_rules_channel", description="Set the channel where rules and verification are posted.")
        @discord.app_commands.describe(channel_id="Channel ID for posting rules.")
        async def set_rules_channel(interaction: discord.Interaction, channel_id: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the rules channel.", delete_after=30)
                return
            _set_rules_channel_id(str(interaction.guild.id), channel_id)
            await _reply_interaction(interaction, "Rules channel configured.", delete_after=30)

        @self.tree.command(name="set_verify_role", description="Configure the role that users receive after verifying rules.")
        @discord.app_commands.describe(role="The role to assign after rules verification.")
        async def set_verify_role(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the verify role.", delete_after=30)
                return
            _set_verify_role_id(str(interaction.guild.id), str(role.id))
            await _reply_interaction(interaction, f"Verification role set to {role.name}.", delete_after=30)

        @self.tree.command(name="set_pending_role", description="Configure the role assigned to new members until they verify the rules.")
        @discord.app_commands.describe(role="The role to assign while waiting for verification.")
        async def set_pending_role(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the pending role.", delete_after=30)
                return
            _set_pending_role_id(str(interaction.guild.id), str(role.id))
            await _reply_interaction(interaction, f"Pending role set to {role.name}.", delete_after=30)

        @self.tree.command(name="set_rules_message", description="Set the rules message displayed to new members.")
        @discord.app_commands.describe(message="The rules text to display.")
        async def set_rules_message(interaction: discord.Interaction, message: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the rules message.", delete_after=30)
                return
            _set_rules_message(str(interaction.guild.id), message)
            await _reply_interaction(interaction, "Rules message updated.", delete_after=30)

        @self.tree.command(name="set_goodbye_message", description="Set the goodbye message template.")
        @discord.app_commands.describe(message="Template text, use {member} and {server}.")
        async def set_goodbye_message(interaction: discord.Interaction, message: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change the goodbye message.", delete_after=30)
                return
            _set_goodbye_message(str(interaction.guild.id), message)
            await _reply_interaction(interaction, "Goodbye message template updated.", delete_after=30)

        @self.tree.command(name="set_mod_log_channel", description="Set the moderation log channel.")
        @discord.app_commands.describe(channel_id="Channel ID to send moderation logs.")
        async def set_mod_log_channel(interaction: discord.Interaction, channel_id: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to set the mod log channel.", delete_after=30)
                return
            _set_mod_log_channel_id(str(interaction.guild.id), channel_id)
            await _reply_interaction(interaction, "Moderation log channel configured.", delete_after=30)

        @self.tree.command(name="add_moderator_role", description="Add a role that can manage Jarvis commands.")
        @discord.app_commands.describe(role="The role to grant moderator access.")
        async def add_moderator_role(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to add moderator roles.", delete_after=30)
                return
            added = _add_moderator_role(str(interaction.guild.id), str(role.id))
            if added:
                await _reply_interaction(interaction, f"Added moderator role {role.name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"The role {role.name} is already a moderator role.", delete_after=30)

        @self.tree.command(name="remove_moderator_role", description="Remove a Jarvis moderator role.")
        @discord.app_commands.describe(role="The role to remove from moderator access.")
        async def remove_moderator_role(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to remove moderator roles.", delete_after=30)
                return
            removed = _remove_moderator_role(str(interaction.guild.id), str(role.id))
            if removed:
                await _reply_interaction(interaction, f"Removed moderator role {role.name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"The role {role.name} was not configured as a moderator role.", delete_after=30)

        @self.tree.command(name="moderator_roles", description="List configured moderator roles.")
        async def moderator_roles(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view moderator roles.", delete_after=30)
                return
            await _reply_interaction(interaction, _list_moderator_roles(str(interaction.guild.id)), delete_after=30)

        @self.tree.command(name="revoke_temp_admin", description="Revoke temporary administrator access from a member.")
        @discord.app_commands.describe(member="The guild member whose temporary access should be removed.")
        async def revoke_temp_admin(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to revoke temporary admin access.", delete_after=30)
                return
            guild = interaction.guild
            if guild is None:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            removed = await _revoke_temp_admin(self, guild.id, member.id, reason="Temporary admin access revoked by Jarvis")
            if removed:
                await _reply_interaction(interaction, f"Temporarily revoked admin access from {member.display_name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"No temporary admin access found for {member.display_name}.", delete_after=30)

        @self.tree.command(name="blacklist_word", description="Add an off-limit word to the server blacklist.")
        @discord.app_commands.describe(word="The word or phrase to block.")
        async def blacklist_word(interaction: discord.Interaction, word: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to add blacklist words.", delete_after=30)
                return
            guild_id = str(interaction.guild.id)
            if _add_blacklist_word(guild_id, word):
                if not _get_auto_mod_enabled(guild_id):
                    _set_auto_mod_enabled(guild_id, True)
                    await _reply_interaction(interaction, 
                        f"Added `{word}` to the blacklist and enabled auto moderation for this server."
                    , delete_after=30)
                else:
                    await _reply_interaction(interaction, f"Added `{word}` to the blacklist.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"`{word}` is already blocked or invalid.", delete_after=30)

        @self.tree.command(name="unblacklist_word", description="Remove an off-limit word from the server blacklist.")
        @discord.app_commands.describe(word="The word or phrase to remove.")
        async def unblacklist_word(interaction: discord.Interaction, word: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to remove blacklist words.", delete_after=30)
                return
            if _remove_blacklist_word(str(interaction.guild.id), word):
                await _reply_interaction(interaction, f"Removed `{word}` from the blacklist.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"`{word}` was not in the blacklist.", delete_after=30)

        @self.tree.command(name="blacklist_words", description="List off-limit words for this server.")
        async def blacklist_words(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view the blacklist.", delete_after=30)
                return
            await _reply_interaction(interaction, _list_blacklist_words(str(interaction.guild.id)), delete_after=30)

        @self.tree.command(name="set_blacklist_category", description="Create or update a blacklist category.")
        @discord.app_commands.describe(category="The blacklist category name.", severity="Severity points for this category.", match_type="Match type: word, contains, or exact.")
        async def set_blacklist_category(interaction: discord.Interaction, category: str, severity: int = 1, match_type: str = "word"):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to manage blacklist categories.", delete_after=30)
                return
            match_type = match_type.strip().lower()
            if match_type not in ("word", "contains", "exact"):
                await _reply_interaction(interaction, "Match type must be one of: word, contains, exact.", delete_after=30)
                return
            _ensure_blacklist_category(str(interaction.guild.id), category, severity=severity, match_type=match_type)
            await _reply_interaction(interaction, 
                f"Set blacklist category `{category}` with severity {severity} and match type `{match_type}`.",
                delete_after=30,
            )

        @self.tree.command(name="add_blacklist_category_word", description="Add a word to a blacklist category.")
        @discord.app_commands.describe(category="The blacklist category name.", word="The word or phrase to block.")
        async def add_blacklist_category_word(interaction: discord.Interaction, category: str, word: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to add blacklist words.", delete_after=30)
                return
            if _add_blacklist_category_word(str(interaction.guild.id), category, word):
                if not _get_auto_mod_enabled(str(interaction.guild.id)):
                    _set_auto_mod_enabled(str(interaction.guild.id), True)
                    await _reply_interaction(interaction, 
                        f"Added `{word}` to category `{category}` and enabled auto moderation for this server.",
                        delete_after=30,
                    )
                else:
                    await _reply_interaction(interaction, f"Added `{word}` to category `{category}`.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"`{word}` is already in category `{category}` or invalid.", delete_after=30)

        @self.tree.command(name="remove_blacklist_category_word", description="Remove a word from a blacklist category.")
        @discord.app_commands.describe(category="The blacklist category name.", word="The word or phrase to remove.")
        async def remove_blacklist_category_word(interaction: discord.Interaction, category: str, word: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to remove blacklist words.", delete_after=30)
                return
            if _remove_blacklist_category_word(str(interaction.guild.id), category, word):
                await _reply_interaction(interaction, f"Removed `{word}` from category `{category}`.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"`{word}` was not found in category `{category}`.", delete_after=30)

        @self.tree.command(name="blacklist_categories", description="List blacklist categories and severities.")
        async def blacklist_categories(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view blacklist categories.", delete_after=30)
                return
            await _reply_interaction(interaction, _list_blacklist_categories(str(interaction.guild.id)), delete_after=30)

        @self.tree.command(name="ignore_channel", description="Ignore auto moderation in a channel.")
        @discord.app_commands.describe(channel="The channel to ignore.")
        async def ignore_channel(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change ignore settings.", delete_after=30)
                return
            if _add_ignore_channel_id(str(interaction.guild.id), str(channel.id)):
                await _reply_interaction(interaction, f"Auto moderation will ignore {channel.mention}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"{channel.mention} is already ignored.", delete_after=30)

        @self.tree.command(name="unignore_channel", description="Stop ignoring a channel for auto moderation.")
        @discord.app_commands.describe(channel="The channel to stop ignoring.")
        async def unignore_channel(interaction: discord.Interaction, channel: discord.TextChannel):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change ignore settings.", delete_after=30)
                return
            if _remove_ignore_channel_id(str(interaction.guild.id), str(channel.id)):
                await _reply_interaction(interaction, f"Auto moderation will no longer ignore {channel.mention}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"{channel.mention} was not ignored.", delete_after=30)

        @self.tree.command(name="ignore_role", description="Ignore auto moderation for a role.")
        @discord.app_commands.describe(role="The role to ignore.")
        async def ignore_role(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change ignore settings.", delete_after=30)
                return
            if _add_ignore_role_id(str(interaction.guild.id), str(role.id)):
                await _reply_interaction(interaction, f"Auto moderation will ignore members with the {role.name} role.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"{role.name} is already ignored.", delete_after=30)

        @self.tree.command(name="unignore_role", description="Stop ignoring a role for auto moderation.")
        @discord.app_commands.describe(role="The role to stop ignoring.")
        async def unignore_role(interaction: discord.Interaction, role: discord.Role):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change ignore settings.", delete_after=30)
                return
            if _remove_ignore_role_id(str(interaction.guild.id), str(role.id)):
                await _reply_interaction(interaction, f"Auto moderation will no longer ignore {role.name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"{role.name} was not ignored.", delete_after=30)

        @self.tree.command(name="ignore_user", description="Ignore a specific user for auto moderation.")
        @discord.app_commands.describe(member="The user to ignore.")
        async def ignore_user(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change ignore settings.", delete_after=30)
                return
            if _add_ignore_user_id(str(interaction.guild.id), str(member.id)):
                await _reply_interaction(interaction, f"Auto moderation will ignore {member.display_name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"{member.display_name} is already ignored.", delete_after=30)

        @self.tree.command(name="unignore_user", description="Stop ignoring a user for auto moderation.")
        @discord.app_commands.describe(member="The user to stop ignoring.")
        async def unignore_user(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change ignore settings.", delete_after=30)
                return
            if _remove_ignore_user_id(str(interaction.guild.id), str(member.id)):
                await _reply_interaction(interaction, f"Auto moderation will no longer ignore {member.display_name}.", delete_after=30)
            else:
                await _reply_interaction(interaction, f"{member.display_name} was not ignored.", delete_after=30)

        @self.tree.command(name="set_auto_mod_thresholds", description="Set auto moderation escalation thresholds.")
        @discord.app_commands.describe(timeout_points="Points before a timeout is applied.", ban_points="Points before a ban is applied.", timeout_minutes="Timeout duration in minutes.")
        async def set_auto_mod_thresholds(interaction: discord.Interaction, timeout_points: int = 3, ban_points: int = 6, timeout_minutes: int = 10):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to configure auto moderation.", delete_after=30)
                return
            _set_auto_mod_thresholds(str(interaction.guild.id), timeout_points, ban_points, timeout_minutes)
            await _reply_interaction(interaction, 
                f"Auto moderation thresholds updated: timeout at {timeout_points} points, ban at {ban_points} points, timeout duration {timeout_minutes}m.",
                delete_after=30,
            )

        @self.tree.command(name="auto_mod_config", description="Show current auto moderation settings.")
        async def auto_mod_config(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view auto moderation settings.", delete_after=30)
                return
            guild_id = str(interaction.guild.id)
            thresholds = _get_auto_mod_thresholds(guild_id)
            ignore_channels = _get_ignore_channel_ids(guild_id)
            ignore_roles = _get_ignore_role_ids(guild_id)
            ignore_users = _get_ignore_user_ids(guild_id)
            categories = _get_blacklist_categories(guild_id)
            lines = [
                f"Auto moderation enabled: {'yes' if _get_auto_mod_enabled(guild_id) else 'no'}",
                f"Timeout points: {thresholds.get('timeout_points', 3)}",
                f"Ban points: {thresholds.get('ban_points', 6)}",
                f"Timeout duration: {thresholds.get('timeout_minutes', 10)} minutes",
                f"Ignored channels: {', '.join(ignore_channels) if ignore_channels else 'none'}",
                f"Ignored roles: {', '.join(ignore_roles) if ignore_roles else 'none'}",
                f"Ignored users: {', '.join(ignore_users) if ignore_users else 'none'}",
                "Blacklist categories:",
            ]
            for category, config in categories.items():
                lines.append(
                    f"  - {category}: severity={config.get('severity', 1)}, match={config.get('match_type', 'word')}, words={len(config.get('words', []))}"
                )
            await _reply_interaction(interaction, "\n".join(lines), delete_after=60)

        @self.tree.command(name="warn", description="Warn a user for moderation reasons.")
        @discord.app_commands.describe(member="The user to warn.", reason="Reason for warning.")
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to issue warnings.", delete_after=30)
                return
            count = _add_warn_for_user(str(interaction.guild.id), str(member.id), str(interaction.user.id), reason or "No reason provided.")
            await _reply_interaction(interaction, f"Warned {member.display_name}. This is warning #{count}.", delete_after=30)
            await _send_mod_log(str(interaction.guild.id), f"{interaction.user.mention} warned {member.mention}: {reason or 'No reason provided.'}")

        @self.tree.command(name="warnings", description="View warnings for a server member.")
        @discord.app_commands.describe(member="The user to inspect.")
        async def warnings(interaction: discord.Interaction, member: Optional[discord.Member] = None):
            await interaction.response.defer(thinking=True)
            member = member or interaction.user
            warns = _get_warns_for_user(str(interaction.guild.id), str(member.id))
            await _reply_interaction(interaction, _format_warns(member, warns), delete_after=30)

        @self.tree.command(name="clear_warnings", description="Clear warnings for a member.")
        @discord.app_commands.describe(member="The user whose warnings should be cleared.")
        async def clear_warnings(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer(thinking=True)
            try:
                if not _is_moderator(interaction.user):
                    await _reply_interaction(interaction, "You do not have permission to clear warnings.", delete_after=30)
                    return
                if not interaction.guild:
                    await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                    return
                count = _clear_warns_for_user(str(interaction.guild.id), str(member.id))
                await _reply_interaction(
                    interaction,
                    f"Cleared {count} warnings for {member.display_name}.",
                    delete_after=30,
                )
                await _send_mod_log(
                    str(interaction.guild.id),
                    f"{interaction.user.mention} cleared warnings for {member.mention}."
                )
            except Exception as exc:
                print(f"[DiscordBot] clear_warnings failed: {exc}")
                await _reply_interaction(
                    interaction,
                    "An error occurred while clearing warnings. Please try again or check the bot logs.",
                    delete_after=30,
                )

        @self.tree.command(name="server_info", description="Show Discord server information.")
        async def server_info(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not interaction.guild:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            await _reply_interaction(interaction, embed=_build_server_info_embed(interaction.guild), delete_after=30)

        @self.tree.command(name="user_info", description="Show information about a user.")
        @discord.app_commands.describe(member="The user to inspect.")
        async def user_info(interaction: discord.Interaction, member: Optional[discord.Member] = None):
            await interaction.response.defer(thinking=True)
            member = member or interaction.user
            await _reply_interaction(interaction, embed=_build_user_info_embed(member), delete_after=30)

        @self.tree.command(name="kick", description="Kick a user from the server.")
        @discord.app_commands.describe(member="The user to kick.", reason="Reason for kicking the user.")
        async def kick(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to kick members.", delete_after=30)
                return
            try:
                await member.kick(reason=reason)
                await _reply_interaction(interaction, f"Kicked {member.display_name}. Reason: {reason or 'No reason provided.'}", delete_after=30)
            except Exception as e:
                await _reply_interaction(interaction, f"Could not kick {member.display_name}: {e}", delete_after=30)

        @self.tree.command(name="ban", description="Ban a user from the server.")
        @discord.app_commands.describe(member="The user to ban.", reason="Reason for banning the user.")
        async def ban(interaction: discord.Interaction, member: discord.Member, reason: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to ban members.", delete_after=30)
                return
            try:
                await member.ban(reason=reason)
                await _reply_interaction(interaction, f"Banned {member.display_name}. Reason: {reason or 'No reason provided.'}", delete_after=30)
            except Exception as e:
                await _reply_interaction(interaction, f"Could not ban {member.display_name}: {e}", delete_after=30)

        @self.tree.command(name="mute", description="Temporarily mute a user.")
        @discord.app_commands.describe(member="The user to mute.", duration_minutes="Duration in minutes.")
        async def mute(interaction: discord.Interaction, member: discord.Member, duration_minutes: Optional[int] = 15):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to mute members.", delete_after=30)
                return
            try:
                until = discord.utils.utcnow() + datetime.timedelta(minutes=duration_minutes)
                try:
                    await member.timeout(until, reason="Muted by Jarvis")
                except TypeError:
                    # Fallback for discord.py variants exposing edit(timed_out_until=...)
                    try:
                        await member.edit(timed_out_until=until, reason="Muted by Jarvis")
                    except Exception:
                        raise
                await _reply_interaction(interaction, f"Muted {member.display_name} for {duration_minutes} minutes.", delete_after=30)
            except Exception as e:
                await _reply_interaction(interaction, f"Could not mute {member.display_name}: {e}", delete_after=30)

        @self.tree.command(name="unmute", description="Remove a timeout from a user.")
        @discord.app_commands.describe(member="The user to unmute.")
        async def unmute(interaction: discord.Interaction, member: discord.Member):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to unmute members.", delete_after=30)
                return
            try:
                try:
                    await member.timeout(None, reason="Unmuted by Jarvis")
                except TypeError:
                    try:
                        await member.edit(timed_out_until=None, reason="Unmuted by Jarvis")
                    except Exception:
                        raise
                await _reply_interaction(interaction, f"Unmuted {member.display_name}.", delete_after=30)
            except Exception as e:
                await _reply_interaction(interaction, f"Could not unmute {member.display_name}: {e}", delete_after=30)

        @self.tree.command(name="reaction_role_select", description="Create a dropdown role picker menu.")
        @discord.app_commands.describe(
            channel="Channel to post the menu in.",
            title="Embed title.",
            description="Embed description.",
            options="Use commas, semicolons, or new lines. Type 'template' for the built-in example format.",
            color="Embed border color: red, blue, green, purple, orange, gold, pink, or blurple (default).",
            single_choice="If enabled, this menu will only keep one role at a time.",
            remove_on_unselect="Remove roles when a user deselects them.",
        )
        @discord.app_commands.choices(color=[
            discord.app_commands.Choice(name="Red", value="red"),
            discord.app_commands.Choice(name="Blue", value="blue"),
            discord.app_commands.Choice(name="Green", value="green"),
            discord.app_commands.Choice(name="Purple", value="purple"),
            discord.app_commands.Choice(name="Orange", value="orange"),
            discord.app_commands.Choice(name="Gold", value="gold"),
            discord.app_commands.Choice(name="Pink", value="pink"),
            discord.app_commands.Choice(name="Blurple", value="blurple"),
        ])
        async def reaction_role_select(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            title: str,
            description: str,
            options: str,
            single_choice: bool = False,
            remove_on_unselect: bool = True,
            color: str = "blurple",
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to create dropdown role menus.", delete_after=30)
                return
            guild_id = str(interaction.guild.id) if interaction.guild else None
            if not guild_id:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            try:
                entries = []
                for emoji_text, role_text in _parse_reaction_role_options(options):
                    role = await _ensure_reaction_role(interaction.guild, role_text)
                    entries.append((emoji_text, role))
                if not entries:
                    raise ValueError("You must provide at least one emoji@RoleName option.")
                if len(entries) > 25:
                    raise ValueError("Dropdown menus can have at most 25 options.")

                color_map = {
                    "red": discord.Color.red(),
                    "blue": discord.Color.blue(),
                    "green": discord.Color.green(),
                    "purple": discord.Color.purple(),
                    "orange": discord.Color.orange(),
                    "gold": discord.Color.gold(),
                    "pink": discord.Color.magenta(),
                    "blurple": discord.Color.blurple(),
                }
                embed_color = color_map.get(color.lower(), discord.Color.blurple())

                embed = discord.Embed(title=title, description=description, color=embed_color)
                embed.add_field(name="Pick a role", value="Use the menu below to select your role.", inline=False)
                embed.set_footer(text="Select one or more roles from the dropdown menu.")

                view = _RoleSelectView(entries, single_choice=single_choice, remove_on_unselect=remove_on_unselect)
                menu_message = await channel.send(embed=embed, view=view)
                _register_reaction_role_menu(
                    guild_id,
                    menu_message.id,
                    entries,
                    single_choice=single_choice,
                    remove_on_unselect=remove_on_unselect,
                )
                await _reply_interaction(
                    interaction,
                    f"Created a dropdown role picker menu in #{channel.name} with {len(entries)} option(s).",
                    delete_after=30,
                )
            except Exception as exc:
                await _reply_interaction(interaction, f"Failed to create the dropdown role menu: {exc}", delete_after=30)

        @self.tree.command(name="edit_embed", description="Edit an existing embedded message by ID.")
        @discord.app_commands.describe(
            channel="Channel containing the embedded message.",
            message_id="ID of the message to edit.",
            title="New embed title.",
            description="New embed description.",
            append_description="Append the text to the existing description instead of replacing it.",
            color="Embed border color: red, blue, green, purple, orange, gold, pink, or blurple.",
            add_field="Optional field to add in the format name|value|inline (inline true/false).",
        )
        @discord.app_commands.choices(color=[
            discord.app_commands.Choice(name="Red", value="red"),
            discord.app_commands.Choice(name="Blue", value="blue"),
            discord.app_commands.Choice(name="Green", value="green"),
            discord.app_commands.Choice(name="Purple", value="purple"),
            discord.app_commands.Choice(name="Orange", value="orange"),
            discord.app_commands.Choice(name="Gold", value="gold"),
            discord.app_commands.Choice(name="Pink", value="pink"),
            discord.app_commands.Choice(name="Blurple", value="blurple"),
        ])
        async def edit_embed(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            message_id: str,
            title: str = None,
            description: str = None,
            append_description: bool = False,
            color: str = "blurple",
            add_field: str = None,
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to edit embed messages.", delete_after=30)
                return
            try:
                int_message_id = _extract_message_id(message_id)
                if int_message_id is None:
                    int_message_id = int(message_id)
                target_message = await channel.fetch_message(int_message_id)
                if not target_message.embeds:
                    raise ValueError("The specified message does not contain an embed.")
                embed = target_message.embeds[0]
                if title is not None:
                    embed.title = title
                if description is not None:
                    if append_description and embed.description:
                        embed.description = f"{embed.description}\n{description}"
                    else:
                        embed.description = description
                if color:
                    color_map = {
                        "red": discord.Color.red(),
                        "blue": discord.Color.blue(),
                        "green": discord.Color.green(),
                        "purple": discord.Color.purple(),
                        "orange": discord.Color.orange(),
                        "gold": discord.Color.gold(),
                        "pink": discord.Color.magenta(),
                        "blurple": discord.Color.blurple(),
                    }
                    embed.color = color_map.get(color.lower(), discord.Color.blurple())
                if add_field:
                    parts = [part.strip() for part in add_field.split("|")]
                    if len(parts) < 2:
                        raise ValueError("add_field must be in the format name|value|inline.")
                    field_name = parts[0]
                    field_value = parts[1]
                    inline = False
                    if len(parts) >= 3:
                        inline_text = parts[2].lower()
                        inline = inline_text in {"true", "yes", "1"}
                    embed.add_field(name=field_name, value=field_value, inline=inline)
                await target_message.edit(embed=embed)
                await _reply_interaction(
                    interaction,
                    f"Edited embed in message {message_id}.",
                    delete_after=30,
                )
            except Exception as exc:
                await _reply_interaction(interaction, f"Could not edit embed: {exc}", delete_after=30)

        @self.tree.command(name="edit_reaction_role_select", description="Add or update options on an existing dropdown role menu.")
        @discord.app_commands.describe(
            channel="Channel containing the dropdown menu.",
            message_id="Message ID or link for the dropdown.",
            options="Additional emoji@RoleName options to add or update.",
        )
        async def edit_reaction_role_select(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            message_id: str,
            options: str,
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to edit dropdown role menus.", delete_after=30)
                return
            try:
                int_message_id = _extract_message_id(message_id)
                if int_message_id is None:
                    int_message_id = int(message_id)
                target_message = await channel.fetch_message(int_message_id)
                if not target_message.embeds:
                    raise ValueError("The specified message does not contain an embed.")

                guild_id = str(interaction.guild.id) if interaction.guild else None
                if not guild_id:
                    raise ValueError("This command must be used in a server.")

                settings = _get_reaction_role_menu_settings(guild_id, int_message_id)
                existing_entries = _reaction_role_entries(interaction.guild, int_message_id)
                if not existing_entries:
                    existing_entries = _extract_select_entries_from_message(target_message, interaction.guild)
                existing_map = {emoji: role for emoji, role in existing_entries}
                for emoji_text, role_text in _parse_reaction_role_options(options):
                    role = await _ensure_reaction_role(interaction.guild, role_text)
                    emoji = _parse_select_emoji(emoji_text)
                    normalized_emoji = _normalize_emoji(emoji)
                    existing_map[normalized_emoji] = role
                    _add_reaction_role(
                        guild_id,
                        int_message_id,
                        normalized_emoji,
                        role.id,
                        single_choice=settings.get("single_choice", False),
                        remove_on_unreact=settings.get("remove_on_unreact", True),
                    )

                combined_entries = [(emoji, role) for emoji, role in existing_map.items()]
                if len(combined_entries) > 25:
                    raise ValueError("Dropdown menus can have at most 25 options.")

                view = _RoleSelectView(
                    combined_entries,
                    single_choice=settings.get("single_choice", False),
                    remove_on_unselect=settings.get("remove_on_unreact", True),
                )
                await target_message.edit(view=view)
                await _reply_interaction(
                    interaction,
                    f"Updated dropdown menu {int_message_id} with {len(existing_map)} option(s).",
                    delete_after=30,
                )
            except Exception as exc:
                await _reply_interaction(interaction, f"Could not update dropdown menu: {exc}", delete_after=30)

        @self.tree.command(name="remove_reaction_role_option", description="Remove an option from a dropdown role menu.")
        @discord.app_commands.describe(
            channel="Channel containing the dropdown menu.",
            message_id="Message ID or link for the dropdown.",
            emoji="The emoji of the option to remove.",
        )
        async def remove_reaction_role_option(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            message_id: str,
            emoji: str,
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to modify dropdown role menus.", delete_after=30)
                return
            try:
                int_message_id = _extract_message_id(message_id)
                if int_message_id is None:
                    int_message_id = int(message_id)
                target_message = await channel.fetch_message(int_message_id)
                if not target_message.embeds:
                    raise ValueError("The specified message does not contain an embed.")

                guild_id = str(interaction.guild.id) if interaction.guild else None
                if not guild_id:
                    raise ValueError("This command must be used in a server.")

                emoji_obj = _parse_select_emoji(emoji)
                normalized_emoji = _normalize_emoji(emoji_obj)
                
                settings = _get_reaction_role_menu_settings(guild_id, int_message_id)
                existing_entries = _reaction_role_entries(interaction.guild, int_message_id)
                if not existing_entries:
                    existing_entries = _extract_select_entries_from_message(target_message, interaction.guild)
                
                remaining_entries = []
                found = False
                for entry_emoji, role in existing_entries:
                    if entry_emoji == normalized_emoji:
                        _remove_reaction_role(guild_id, int_message_id, entry_emoji)
                        found = True
                    else:
                        remaining_entries.append((entry_emoji, role))
                
                if not found:
                    raise ValueError(f"Option with emoji `{emoji}` not found in this menu.")
                
                if not remaining_entries:
                    raise ValueError("Cannot remove the only option from a dropdown menu.")
                
                view = _RoleSelectView(
                    remaining_entries,
                    single_choice=settings.get("single_choice", False),
                    remove_on_unselect=settings.get("remove_on_unreact", True),
                )
                await target_message.edit(view=view)
                await _reply_interaction(
                    interaction,
                    f"Removed option `{emoji}` from dropdown menu. {len(remaining_entries)} option(s) remain.",
                    delete_after=30,
                )
            except Exception as exc:
                await _reply_interaction(interaction, f"Could not remove option: {exc}", delete_after=30)

        @self.tree.command(name="delete_message", description="Delete a message by ID from a channel.")
        @discord.app_commands.describe(
            channel="Channel containing the message.",
            message_id="ID of the message to delete.",
        )
        async def delete_message(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            message_id: str,
        ):
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to delete messages.", delete_after=30)
                return
            int_message_id = _extract_message_id(message_id)
            if int_message_id is None:
                try:
                    int_message_id = int(message_id)
                except ValueError:
                    await _reply_interaction(interaction, f"`{message_id}` is not a valid message ID.", delete_after=30)
                    return

            confirmation = _DeleteConfirmationView(
                author_id=interaction.user.id,
                channel_id=channel.id,
                message_id=int_message_id,
            )
            await _reply_interaction(
                interaction,
                f"Please confirm deletion of message {message_id} in #{channel.name}.",
                ephemeral=True,
                view=confirmation,
            )

        @self.tree.command(name="reaction_roles", description="List reaction role mappings for this server.")
        async def reaction_roles(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view reaction role mappings.", delete_after=30)
                return
            guild_id = str(interaction.guild.id) if interaction.guild else None
            if not guild_id:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            await _reply_interaction(interaction, _list_reaction_roles(guild_id), delete_after=30)

        @self.tree.command(name="poll", description="Create a quick poll with emoji reactions or native Discord polls.")
        @discord.app_commands.describe(
            question="The poll question.",
            options="Comma-separated poll options.",
            duration_minutes="How long the poll stays open in minutes (0 = open-ended reaction poll).",
            multiple="Allow users to select more than one option (native polls only).",
            emojis="Optional comma-separated custom emojis for each option.",
        )
        async def poll(
            interaction: discord.Interaction,
            question: str,
            options: str,
            duration_minutes: int = 0,
            multiple: bool = False,
            emojis: str = "",
        ):
            await interaction.response.defer(thinking=True)
            option_texts = [opt.strip() for opt in options.split(",") if opt.strip()]
            emoji_texts = [emoji.strip() for emoji in emojis.split(",") if emoji.strip()]
            if len(option_texts) < 2 or len(option_texts) > MAX_POLL_OPTIONS:
                await _reply_interaction(
                    interaction,
                    f"Please provide between 2 and {MAX_POLL_OPTIONS} options separated by commas.",
                    delete_after=30,
                )
                return
            if emoji_texts and len(emoji_texts) != len(option_texts):
                await _reply_interaction(
                    interaction,
                    "If you provide custom emojis, you must supply exactly one emoji per option.",
                    delete_after=30,
                )
                return
            if duration_minutes < 0:
                await _reply_interaction(interaction, "Duration must be 0 or a positive integer.", delete_after=30)
                return
            if duration_minutes > 0:
                if duration_minutes < 60:
                    await _reply_interaction(
                        interaction,
                        "Native Discord polls require a duration of at least 60 minutes. "
                        "Shorter polls will use emoji reactions instead.",
                        delete_after=30,
                    )
                    # Fall back to the reaction poll path below.
                else:
                    poll_hours = math.ceil(duration_minutes / 60)
                    poll_obj = discord.Poll(
                        question,
                        datetime.timedelta(hours=poll_hours),
                        multiple=multiple,
                    )
                    for i, option in enumerate(option_texts):
                        emoji = emoji_texts[i] if emoji_texts else (VOTE_REACTIONS[i] if i < len(VOTE_REACTIONS) else None)
                        poll_obj.add_answer(text=option, emoji=emoji)
                    poll_message = await _reply_interaction(interaction, poll=poll_obj)
                    if not isinstance(poll_message, discord.Message):
                        await _reply_interaction(interaction, "Could not create the poll. Check permissions or try again.", delete_after=30)
                        return
                    self._poll_metadata[poll_message.id] = {
                        "question": question,
                        "option_texts": option_texts,
                        "duration_minutes": duration_minutes,
                        "multiple": multiple,
                        "emojis": emoji_texts,
                        "poll_hours": poll_hours,
                    }
                    await _reply_interaction(
                        interaction,
                        f"Poll created with message ID `{poll_message.id}`. Use `/poll_results {poll_message.id}` to view current standings.",
                        ephemeral=True,
                    )
                    return
            if len(option_texts) > len(VOTE_REACTIONS) and not emoji_texts:
                await _reply_interaction(
                    interaction,
                    f"Open-ended reaction polls support up to {len(VOTE_REACTIONS)} options unless you provide custom emojis.",
                    delete_after=30,
                )
                return
            reaction_emojis = emoji_texts if emoji_texts else VOTE_REACTIONS
            poll_embed = _build_poll_embed(question, option_texts, duration_minutes=duration_minutes)
            poll_message = await _reply_interaction(interaction, embed=poll_embed)
            if not isinstance(poll_message, discord.Message):
                return
            self._poll_metadata[poll_message.id] = {
                "question": question,
                "option_texts": option_texts,
                "duration_minutes": duration_minutes,
                "multiple": multiple,
                "emojis": emoji_texts,
            }
            for i, option in enumerate(option_texts):
                try:
                    await poll_message.add_reaction(reaction_emojis[i])
                except Exception:
                    pass
            if duration_minutes > 0:
                self._poll_close_tasks[poll_message.id] = asyncio.create_task(
                    self._auto_close_poll(poll_message, question, option_texts, duration_minutes)
                )
            await _reply_interaction(
                interaction,
                f"Poll created with message ID `{poll_message.id}`. Use `/poll_results {poll_message.id}` to view current standings.",
                ephemeral=True,
            )

        @self.tree.command(name="image_poll_files", description="Create an image poll using local image files.")
        @discord.app_commands.describe(
            question="The poll question.",
            labels="Optional comma-separated labels for each image option.",
            duration_minutes="How long the poll stays open in minutes (0 = open-ended reaction poll).",
        )
        async def image_poll_files(
            interaction: discord.Interaction,
            question: str,
            labels: Optional[str] = "",
            duration_minutes: int = 0,
        ):
            if duration_minutes < 0:
                await _reply_interaction(interaction, "Duration must be 0 or a positive integer.", delete_after=30, ephemeral=True)
                return

            if not self._poll_image_picker_callback:
                available_files = _get_local_image_files()
                available_text = ", ".join(available_files) if available_files else "no local photos available"
                await _reply_interaction(
                    interaction,
                    f"Local image picker is not available right now. Use the UI app or provide image names manually from the photos folder ({available_text}).",
                    delete_after=60,
                    ephemeral=True,
                )
                return

            view = _LocalImagePollPickerView(self, question, labels, duration_minutes)
            await _reply_interaction(
                interaction,
                "Click the button below to open the local file picker and choose images for the poll.",
                ephemeral=True,
                view=view,
            )

        @self.tree.command(name="image_poll", description="Create an image poll where users vote on image options.")
        @discord.app_commands.describe(
            question="The poll question.",
            image_urls="Comma-separated image URLs to include as options.",
            labels="Optional comma-separated labels for each image option.",
            duration_minutes="How long the poll stays open in minutes (0 = open-ended reaction poll).",
        )
        async def image_poll(
            interaction: discord.Interaction,
            question: str,
            image_urls: str,
            labels: Optional[str] = "",
            duration_minutes: int = 0,
        ):
            await interaction.response.defer(thinking=True)
            urls = [url.strip() for url in image_urls.split(",") if url.strip()]
            if len(urls) < 2 or len(urls) > len(VOTE_REACTIONS):
                await _reply_interaction(
                    interaction,
                    f"Please provide between 2 and {len(VOTE_REACTIONS)} image URLs separated by commas.",
                    delete_after=30,
                )
                return
            label_texts = [label.strip() for label in labels.split(",") if label.strip()] if labels else []
            if label_texts and len(label_texts) != len(urls):
                await _reply_interaction(
                    interaction,
                    "If you provide labels, there must be exactly one label for each image URL.",
                    delete_after=30,
                )
                return
            option_labels = label_texts if label_texts else [f"Option {idx + 1}" for idx in range(len(urls))]
            if duration_minutes < 0:
                await _reply_interaction(interaction, "Duration must be 0 or a positive integer.", delete_after=30)
                return
            poll_embed = _build_image_poll_embed(question, urls, option_labels, duration_minutes=duration_minutes)
            poll_message = await _reply_interaction(interaction, embed=poll_embed)
            if not isinstance(poll_message, discord.Message):
                return
            self._poll_metadata[poll_message.id] = {
                "question": question,
                "option_texts": option_labels,
                "duration_minutes": duration_minutes,
                "multiple": False,
                "emojis": [],
                "image_urls": urls,
            }
            for i in range(len(urls)):
                try:
                    await poll_message.add_reaction(VOTE_REACTIONS[i])
                except Exception:
                    pass
            if duration_minutes > 0:
                self._poll_close_tasks[poll_message.id] = asyncio.create_task(
                    self._auto_close_poll(poll_message, question, option_labels, duration_minutes)
                )
            await _reply_interaction(
                interaction,
                f"Image poll created with message ID `{poll_message.id}`. React to vote, or use `/poll_results {poll_message.id}` to check standings.",
                ephemeral=True,
            )

        @self.tree.command(name="poll_close", description="Close a poll and show its final results.")
        @discord.app_commands.describe(message_id="The poll message ID.")
        async def poll_close(interaction: discord.Interaction, message_id: int):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to close polls.", delete_after=30)
                return
            channel = interaction.channel
            if not channel:
                await _reply_interaction(interaction, "Unable to access the channel for this poll.", delete_after=30)
                return
            try:
                poll_message = await channel.fetch_message(message_id)
            except Exception:
                await _reply_interaction(interaction, "Unable to fetch that poll message. Make sure the ID is correct.", delete_after=30)
                return
            question = None
            option_texts = []
            counts = []
            if poll_message.poll:
                try:
                    updated_poll = await poll_message.poll.end()
                    question = updated_poll.question
                    option_texts = [answer.text for answer in updated_poll.answers]
                    counts = [answer.vote_count for answer in updated_poll.answers]
                except Exception:
                    pass
            if not option_texts:
                if poll_message.embeds:
                    embed = poll_message.embeds[0]
                    if embed.description:
                        lines = [line.strip() for line in embed.description.splitlines() if line.strip()]
                        if lines:
                            question = lines[0].strip("*")
                            for line in lines[1:]:
                                for emoji in VOTE_REACTIONS:
                                    if line.startswith(emoji):
                                        text = line[len(emoji):].strip()
                                        option_texts.append(re.split(r"\s+[-—]\s+|\s+\(", text)[0].strip())
                                        break
                if question and option_texts:
                    counts = _get_poll_vote_counts(poll_message, option_texts)
            if not question or not option_texts:
                await _reply_interaction(
                    interaction,
                    "Unable to determine the poll question and options from that message.",
                    delete_after=30,
                )
                return
            task = self._poll_close_tasks.pop(message_id, None)
            if task is not None:
                task.cancel()
            poll_metadata = self._poll_metadata.get(message_id, {})
            if poll_metadata.get("image_urls"):
                result_embed = _build_image_poll_embed(
                    question,
                    poll_metadata.get("image_urls", []),
                    option_texts,
                    closed=True,
                    counts=counts,
                )
            else:
                result_embed = _build_poll_embed(
                    question,
                    option_texts,
                    closed=True,
                    counts=counts,
                )
            try:
                await poll_message.edit(embed=result_embed)
            except Exception:
                pass
            files = []
            if poll_paths := poll_metadata.get("image_paths"):
                files = [discord.File(path, filename=Path(path).name) for path in poll_paths if Path(path).exists()]
            await _reply_interaction(interaction, "Poll closed. Final results:", embed=result_embed, files=files if files else None)

        @self.tree.command(name="poll_results", description="Show current results for a poll message.")
        @discord.app_commands.describe(message_id="The poll message ID.")
        async def poll_results(interaction: discord.Interaction, message_id: int):
            await interaction.response.defer(thinking=True)
            channel = interaction.channel
            if not channel:
                await _reply_interaction(interaction, "Unable to access the channel for this poll.", delete_after=30)
                return
            try:
                poll_message = await channel.fetch_message(message_id)
            except Exception:
                await _reply_interaction(interaction, "Unable to fetch that poll message. Make sure the ID is correct.", delete_after=30)
                return
            question = None
            option_texts = []
            counts = []
            poll_metadata = self._poll_metadata.get(message_id, {})
            if getattr(poll_message, 'poll', None):
                try:
                    updated_poll = poll_message.poll
                    question = updated_poll.question
                    option_texts = [answer.text for answer in updated_poll.answers]
                    counts = [answer.vote_count for answer in updated_poll.answers]
                except Exception:
                    pass
            if not option_texts:
                if poll_message.embeds:
                    embed = poll_message.embeds[0]
                    if embed.description:
                        lines = [line.strip() for line in embed.description.splitlines() if line.strip()]
                        if lines:
                            question = lines[0].strip("*")
                            for line in lines[1:]:
                                for emoji in VOTE_REACTIONS:
                                    if line.startswith(emoji):
                                        text = line[len(emoji):].strip()
                                        option_texts.append(re.split(r"\s+[-—]\s+|\s+\(", text)[0].strip())
                                        break
                if question and option_texts:
                    counts = _get_poll_vote_counts(poll_message, option_texts)
            if not question or not option_texts:
                await _reply_interaction(
                    interaction,
                    "Unable to determine the poll question and options from that message.",
                    delete_after=30,
                )
                return
            if poll_metadata.get("image_urls"):
                result_embed = _build_image_poll_embed(
                    question,
                    poll_metadata.get("image_urls", []),
                    option_texts,
                    closed=False,
                    counts=counts,
                )
            else:
                result_embed = _build_poll_embed(
                    question,
                    option_texts,
                    closed=False,
                    counts=counts,
                )
            files = []
            if poll_paths := poll_metadata.get("image_paths"):
                files = [discord.File(path, filename=Path(path).name) for path in poll_paths if Path(path).exists()]
            await _reply_interaction(interaction, "Current poll results:", embed=result_embed, files=files if files else None)

        @self.tree.command(name="purge", description="Delete messages in bulk (spam cleanup, etc.).")
        @discord.app_commands.describe(
            count="Number of messages to delete (default 10, max 100).",
            user="Optional: Delete messages only from a specific user.",
            contains="Optional: Delete messages containing this text.",
        )
        async def purge(
            interaction: discord.Interaction,
            count: int = 10,
            user: Optional[discord.User] = None,
            contains: Optional[str] = None,
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to purge messages.", delete_after=30)
                return
            
            if not isinstance(interaction.channel, discord.TextChannel):
                await _reply_interaction(interaction, "This command can only be used in text channels.", delete_after=30)
                return
            
            count = max(1, min(count, 100))
            
            def check(msg):
                if user and msg.author != user:
                    return False
                if contains and contains.lower() not in msg.content.lower():
                    return False
                return True
            
            try:
                deleted = await interaction.channel.purge(limit=count, check=check)
                await _reply_interaction(interaction, f"Deleted {len(deleted)} message(s).", delete_after=30)
            except Exception as e:
                await _reply_interaction(interaction, f"Failed to purge messages: {e}", delete_after=30)

        @self.tree.command(name="voice_effect", description="Set the voice effect Jarvis uses when speaking.")
        @discord.app_commands.describe(effect="Effect name.")
        async def voice_effect(interaction: discord.Interaction, effect: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change the voice effect.", delete_after=30)
                return
            guild_id = str(interaction.guild.id) if interaction.guild else None
            if not guild_id:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            if effect not in VOICE_EFFECTS:
                await _reply_interaction(interaction, f"Invalid effect. Available values: {_format_effect_list()}", delete_after=30)
                return
            _set_voice_effect_for_guild(guild_id, effect)
            await _reply_interaction(interaction, f"Voice effect set to `{effect}`.", delete_after=30)

        @self.tree.command(name="bot_settings", description="Show server-specific Jarvis configuration.")
        async def bot_settings(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view server bot settings.", delete_after=30)
                return
            guild_id = str(interaction.guild.id) if interaction.guild else None
            if not guild_id:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            personality = _get_personality_prompt(guild_id)
            tone = _get_response_tone(guild_id) or "default"
            auto_mod = _get_auto_mod_enabled(guild_id)
            mod_roles = _list_moderator_roles(guild_id)
            blacklist = _list_blacklist_words(guild_id)
            welcome_channel = _get_welcome_channel_id(guild_id) or "Not set"
            goodbye_channel = _get_goodbye_channel_id(guild_id) or "Not set"
            mod_log_channel = _get_mod_log_channel_id(guild_id) or "Not set"
            warning_message = _get_warning_message_template(guild_id)
            enabled_scheduling = _get_scheduling_enabled(guild_id)
            bot_can_moderate = False
            if interaction.guild and interaction.guild.me:
                bot_can_moderate = interaction.guild.me.guild_permissions.moderate_members
            await _reply_interaction(interaction, 
                f"**Jarvis server settings**\n"
                f"• Personality: {personality}\n"
                f"• Response tone: {tone}\n"
                f"• Auto moderation: {'enabled' if auto_mod else 'disabled'}\n"
                f"• Bot can moderate members: {'yes' if bot_can_moderate else 'no'}\n"
                f"• Moderator roles:\n{mod_roles}\n"
                f"• Blacklist words:\n{blacklist}\n"
                f"• Mod log channel: {mod_log_channel}\n"
                f"• Welcome channel: {welcome_channel}\n"
                f"• Goodbye channel: {goodbye_channel}\n"
                f"• Warning message template: {warning_message}\n"
                f"• Scheduling enabled: {'yes' if enabled_scheduling else 'no'}"
            , delete_after=30)

        @self.tree.command(name="reset_server_settings", description="Reset only this server's Jarvis settings.")
        async def reset_server_settings(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to reset server settings.", delete_after=30)
                return
            if not interaction.guild:
                await _reply_interaction(interaction, "This command must be used in a server.", delete_after=30)
                return
            _reset_guild_settings(str(interaction.guild.id))
            await _reply_interaction(interaction, "This server's Jarvis settings have been reset to defaults.", delete_after=30)

        @self.tree.command(name="enable_auto_mod", description="Enable off-limit word filtering and warnings.")
        async def enable_auto_mod(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to enable auto moderation.", delete_after=30)
                return
            _set_auto_mod_enabled(str(interaction.guild.id), True)
            await _reply_interaction(interaction, "Auto moderation is now enabled. Add blacklist words with /blacklist_word.", delete_after=30)

        @self.tree.command(name="disable_auto_mod", description="Disable off-limit word filtering and warnings.")
        async def disable_auto_mod(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to disable auto moderation.", delete_after=30)
                return
            _set_auto_mod_enabled(str(interaction.guild.id), False)
            await _reply_interaction(interaction, "Auto moderation is now disabled.", delete_after=30)

        @self.tree.command(name="auto_mod_status", description="Show whether auto moderation is enabled.")
        async def auto_mod_status(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view auto moderation status.", delete_after=30)
                return
            enabled = _get_auto_mod_enabled(str(interaction.guild.id))
            await _reply_interaction(interaction, f"Auto moderation is {'enabled' if enabled else 'disabled'}.", delete_after=30)

        @self.tree.command(name="set_warning_message", description="Set the message template for auto warning notifications.")
        @discord.app_commands.describe(template="Template text using {member}, {reason}, and {count}.")
        async def set_warning_message(interaction: discord.Interaction, template: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to change warning messages.", delete_after=30)
                return
            _set_warning_message_template(str(interaction.guild.id), template)
            await _reply_interaction(interaction, "Warning message template updated.", delete_after=30)

        @self.tree.command(name="schedule_announcement", description="Schedule a message to post to a channel.")
        @discord.app_commands.describe(
            channel="The channel to post the announcement.",
            message="The announcement message.",
            deliver_at="UTC time in YYYY-MM-DD HH:MM format.",
            repeat="none, daily, or weekly repeat schedule."
        )
        async def schedule_announcement(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            message: str,
            deliver_at: str,
            repeat: Optional[str] = "none"
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to schedule announcements.", delete_after=30)
                return
            repeat = repeat.lower() if repeat else "none"
            if repeat not in ("none", "daily", "weekly"):
                await _reply_interaction(interaction, "Repeat must be one of: none, daily, weekly.", delete_after=30)
                return
            when = _parse_datetime_string(deliver_at)
            if not when:
                await _reply_interaction(interaction, "Invalid date/time format. Use YYYY-MM-DD HH:MM in UTC.", delete_after=30)
                return
            entry = {
                "id": str(uuid.uuid4()),
                "channel_id": str(channel.id),
                "message": message,
                "deliver_at": when.isoformat(),
                "repeat": repeat,
            }
            _add_scheduled_entry(str(interaction.guild.id), "announcements", entry)
            await _reply_interaction(interaction, 
            f"Announcement scheduled for {when.isoformat()} UTC. "
            "Delivery is currently off until /enable_scheduling is used."
        , delete_after=30)

        @self.tree.command(name="schedule_reminder", description="Schedule a reminder message.")
        @discord.app_commands.describe(
            channel="The channel to post the reminder.",
            message="The reminder message.",
            deliver_at="UTC time in YYYY-MM-DD HH:MM format.",
            repeat="none, daily, or weekly repeat schedule."
        )
        async def schedule_reminder(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            message: str,
            deliver_at: str,
            repeat: Optional[str] = "none"
        ):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to schedule reminders.", delete_after=30)
                return
            repeat = repeat.lower() if repeat else "none"
            if repeat not in ("none", "daily", "weekly"):
                await _reply_interaction(interaction, "Repeat must be one of: none, daily, weekly.", delete_after=30)
                return
            when = _parse_datetime_string(deliver_at)
            if not when:
                await _reply_interaction(interaction, "Invalid date/time format. Use YYYY-MM-DD HH:MM in UTC.", delete_after=30)
                return
            entry = {
                "id": str(uuid.uuid4()),
                "channel_id": str(channel.id),
                "message": message,
                "deliver_at": when.isoformat(),
                "repeat": repeat,
            }
            _add_scheduled_entry(str(interaction.guild.id), "reminders", entry)
            await _reply_interaction(interaction, 
                f"Reminder scheduled for {when.isoformat()} UTC. "
                "Delivery is currently off until /enable_scheduling is used."
            , delete_after=30)

        @self.tree.command(name="enable_scheduling", description="Enable delivery of scheduled announcements and reminders.")
        async def enable_scheduling(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to enable scheduling.", delete_after=30)
                return
            _set_scheduling_enabled(str(interaction.guild.id), True)
            await _reply_interaction(interaction, "Scheduled announcement and reminder delivery is now enabled.", delete_after=30)

        @self.tree.command(name="disable_scheduling", description="Disable delivery of scheduled announcements and reminders.")
        async def disable_scheduling(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to disable scheduling.", delete_after=30)
                return
            _set_scheduling_enabled(str(interaction.guild.id), False)
            await _reply_interaction(interaction, "Scheduled announcement and reminder delivery is now disabled.", delete_after=30)

        @self.tree.command(name="scheduling_status", description="Show whether scheduled delivery is enabled.")
        async def scheduling_status(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to view scheduling status.", delete_after=30)
                return
            enabled = _get_scheduling_enabled(str(interaction.guild.id))
            await _reply_interaction(interaction, 
                f"Scheduled delivery is {'enabled' if enabled else 'disabled'}. "
                "Use /enable_scheduling to allow announcements and reminders to post."
            , delete_after=30)

        @self.tree.command(name="list_announcements", description="List scheduled announcements.")
        async def list_announcements(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to list scheduled announcements.", delete_after=30)
                return
            entries = _get_scheduled_entries(str(interaction.guild.id), "announcements")
            if not entries:
                await _reply_interaction(interaction, "No scheduled announcements configured.", delete_after=30)
                return
            await _reply_interaction(interaction, "\n\n".join(_build_schedule_description(entry) for entry in entries), delete_after=30)

        @self.tree.command(name="list_reminders", description="List scheduled reminders.")
        async def list_reminders(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to list scheduled reminders.", delete_after=30)
                return
            entries = _get_scheduled_entries(str(interaction.guild.id), "reminders")
            if not entries:
                await _reply_interaction(interaction, "No scheduled reminders configured.", delete_after=30)
                return
            await _reply_interaction(interaction, "\n\n".join(_build_schedule_description(entry) for entry in entries), delete_after=30)

        @self.tree.command(name="remove_announcement", description="Remove a scheduled announcement.")
        @discord.app_commands.describe(entry_id="The announcement ID to remove.")
        async def remove_announcement(interaction: discord.Interaction, entry_id: str):
            await interaction.response.defer(thinking=True)
            if not _is_moderator(interaction.user):
                await _reply_interaction(interaction, "You do not have permission to remove announcements.", delete_after=30)
                return
            removed = _remove_scheduled_entry(str(interaction.guild.id), "announcements", entry_id)
            await _reply_interaction(interaction, 
                "Announcement removed." if removed else "Announcement not found."
            , delete_after=30)

        @self.tree.command(name="remove_reminder", description="Remove a scheduled reminder.")
        @discord.app_commands.describe(entry_id="The reminder ID to remove.")
        async def remove_reminder(interaction: discord.Interaction, entry_id: str):
            await interaction.response.defer(thinking=True)
            removed = _remove_scheduled_entry(str(interaction.guild.id), "reminders", entry_id)
            await _reply_interaction(interaction, 
                "Reminder removed." if removed else "Reminder not found."
            , delete_after=30)

        @self.tree.command(name="dad_joke", description="Tell a quick dad joke.")
        async def dad_joke(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            await _reply_interaction(interaction, _random_dad_joke())

        @self.tree.command(name="roast", description="Give a playful roast to a user.")
        @discord.app_commands.describe(
            member="Optional user to roast.",
            style="Choose playful, mean, soft, or chaotic."
        )
        async def roast(
            interaction: discord.Interaction,
            member: Optional[discord.Member] = None,
            style: Optional[str] = "playful"
        ):
            await interaction.response.defer(thinking=True)
            await _reply_interaction(interaction, _build_roast(member, style))

        @self.tree.command(name="ask", description="Ask Jarvis a question.")
        @discord.app_commands.describe(query="The question to ask Jarvis.")
        async def ask(interaction: discord.Interaction, query: str):
            await interaction.response.defer(thinking=True)
            answer = await _query_discord_ai(
                query,
                guild_id=str(interaction.guild.id) if interaction.guild else None,
                user_id=interaction.user.id,
                bot=self,
            )
            sent = await _reply_interaction(interaction, answer, delete_after=30)
            # Record the bot reply so follow-ups by the same user are recognized.
            try:
                now = datetime.datetime.now(datetime.timezone.utc)
                channel_id = str(interaction.channel.id) if interaction.channel else None
                thread_id = None
                if interaction.channel and isinstance(interaction.channel, discord.Thread):
                    thread_id = interaction.channel.id
                state_key = (channel_id, interaction.user.id, thread_id)
                fallback_key = (channel_id, interaction.user.id, None)
                if sent and getattr(sent, 'id', None):
                    entry = (getattr(sent, 'id', None), getattr(sent, 'created_at', now))
                    self._last_bot_messages[state_key] = entry
                    self._last_bot_messages[fallback_key] = entry
                self._active_conversations[state_key] = now + datetime.timedelta(seconds=120)
                self._active_conversations[fallback_key] = now + datetime.timedelta(seconds=120)
            except Exception:
                pass

        @self.tree.command(name="play", description="Play music in a Discord voice channel.")
        @discord.app_commands.describe(query="Song name or YouTube link.", channel_id="Optional voice channel ID to join before playing.")
        async def play(interaction: discord.Interaction, query: str, channel_id: Optional[str] = None):
            await interaction.response.defer(thinking=True)
            target_channel = None
            if channel_id:
                target_channel = await self._fetch_channel_by_id(channel_id)
            elif interaction.user.voice and interaction.user.voice.channel:
                target_channel = interaction.user.voice.channel

            if target_channel and isinstance(target_channel, discord.VoiceChannel):
                connected = await self._ensure_voice_connection(target_channel)
                if not connected:
                    await _reply_interaction(
                        interaction,
                        "I couldn't join that voice channel. Please check my permissions.",
                        delete_after=_get_temporary_delete_seconds()
                    )
                    return

            result = await _play_music_in_voice_channel(query, notify_channel_id=interaction.channel.id if interaction.channel else None)
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.tree.command(name="pause", description="Pause currently playing music.")
        async def pause(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            result = await self.pause_music()
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.tree.command(name="resume", description="Resume paused music.")
        async def resume(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            result = await self.resume_music()
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.tree.command(name="stop", description="Stop music and clear the queue.")
        async def stop(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            result = await self.stop_music()
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.tree.command(name="skip", description="Skip the current music track.")
        async def skip(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            result = await self.skip_music()
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.tree.command(name="volume", description="Set the music playback volume (0-200%).")
        @discord.app_commands.describe(level="Volume percent between 0 and 200.")
        async def volume(interaction: discord.Interaction, level: float):
            await interaction.response.defer(thinking=True)
            result = await self.set_music_volume(level / 100.0)
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.tree.command(name="music_queue", description="Show the current music queue.")
        async def music_queue(interaction: discord.Interaction):
            await interaction.response.defer(thinking=True)
            result = await self.get_music_queue_status()
            await _reply_interaction(interaction, result, delete_after=_get_temporary_delete_seconds())

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user or message.author.bot:
                return

            content = message.content or ""
            now = datetime.datetime.now(datetime.timezone.utc)
            channel_id = str(message.channel.id)
            user_id = message.author.id
            thread_id = None
            if hasattr(message, "thread") and message.thread:
                thread_id = getattr(message.thread, "id", None)
            elif isinstance(message.channel, discord.Thread):
                thread_id = message.channel.id
            # Conversation keys use guild id (or 'dm') to match how history is stored.
            guild_id_str = str(message.guild.id) if message.guild else None
            conv_key = _conversation_history_key(guild_id_str, user_id, thread_id)
            conv_fallback_key = _conversation_history_key(guild_id_str, user_id, None)
            # Keep channel-specific id for logging only

            # canonical state keys used across handlers
            state_key = conv_key
            fallback_key = conv_fallback_key

            # Grant XP for activity if gamification enabled
            try:
                if message.guild and hasattr(self, '_gamification'):
                    self._gamification.add_xp(message.guild.id, message.author.id, amount=10, channel=message.channel)
            except Exception as e:
                print(f"[DiscordBot] Failed to add XP: {e}")




            is_directed_at_bot = _is_directed_to_bot(message, self.client.user.id)
            is_directed_elsewhere = _is_directed_at_someone_else(message, self.client.user.id)
            says_jarvis = bool(re.search(r"\bjarvis\b", content, re.IGNORECASE))
            followup_active = False
            command_text = ""
            if is_directed_at_bot or says_jarvis or content.strip().lower().startswith("!jarvis"):
                command_text = _extract_jarvis_command(content, self.client.user.id)
            command_lower = command_text.lower()
            explicit_channel_id = _extract_channel_id(content)

            if command_text and _is_owner(message.author):
                if re.search(r"\b(grant|give)\b.*\b(jarvis|integration)?\s*admin\b", command_lower) and not re.search(r"\btemp(?:orary)?\b", command_lower):
                    if message.guild is None:
                        await message.channel.send("I can only grant Jarvis admin access from inside a server.")
                        return
                    try:
                        bot_member = await _get_discord_bot_member(message.guild)
                        if bot_member is None or not (bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator):
                            await message.channel.send(
                                "I cannot grant Jarvis admin access because I do not have Manage Roles or Administrator permission in this server. "
                                "Please update my bot permissions and try again."
                            )
                            return
                        role = await _get_or_create_jarvis_admin_role(message.guild)
                        await _ensure_role_assignable_by_bot(role, message.guild, "Ensure Jarvis admin role is assignable before grant")
                        role = message.guild.get_role(role.id)
                        if role is None:
                            await message.channel.send("Could not retrieve the Jarvis admin role after repositioning.")
                            return
                        bot_member = message.guild.me
                        if bot_member is None:
                            try:
                                bot_member = await message.guild.fetch_member(self.client.user.id)
                            except Exception:
                                bot_member = None
                        if bot_member is None:
                            await message.channel.send("I could not resolve my own server member entry, so I cannot assign the admin role.")
                            return
                        if role.position >= bot_member.top_role.position:
                            await message.channel.send(
                                "I cannot assign the Jarvis admin role because my Discord role is not high enough. "
                                "Please move my bot role above the Jarvis Admin role."
                            )
                            return
                        member = message.guild.get_member(message.author.id)
                        if member is None:
                            try:
                                member = await message.guild.fetch_member(message.author.id)
                            except Exception:
                                member = None
                        if member is None:
                            await message.channel.send("I could not resolve your member account in this server.")
                            return
                        if role in member.roles:
                            await message.channel.send("You already have the Jarvis admin role.")
                            return
                        await member.add_roles(role, reason="Jarvis admin access granted to bot owner")
                        await message.channel.send("Granted Jarvis admin role to the bot owner.")
                        return
                    except discord.Forbidden as exc:
                        await message.channel.send(
                            "I could not grant Jarvis admin access because I am missing permissions or my role is not high enough. "
                            "Please ensure my bot role has Manage Roles and is above the Jarvis Admin role."
                        )
                        print(f"[DiscordBot] Forbidden granting Jarvis admin in guild {message.guild.id}: {exc}")
                        return
                    except Exception as exc:
                        await message.channel.send(f"Could not grant Jarvis admin access: {exc}")
                        return
                if re.search(r"\b(grant|give)\b.*\b(temp(?:orary)? admin|admin access)\b", command_lower):
                    if message.guild is None:
                        await message.channel.send("I can only grant temporary admin access from inside a server.")
                        return
                    duration_minutes = 10
                    duration_match = re.search(r"(\d+)\s*(hours|hrs|hour|h)\b", command_lower)
                    if duration_match:
                        duration_minutes = int(duration_match.group(1)) * 60
                    else:
                        duration_match = re.search(r"(\d+)\s*(minutes|min)\b", command_lower)
                        if duration_match:
                            duration_minutes = int(duration_match.group(1))
                    try:
                        bot_member = await _get_discord_bot_member(message.guild)
                        if bot_member is None or not (bot_member.guild_permissions.manage_roles or bot_member.guild_permissions.administrator):
                            await message.channel.send(
                                "I cannot grant temporary admin access because I do not have Manage Roles or Administrator permission in this server. "
                                "Please update my bot permissions and try again."
                            )
                            return
                        member = message.guild.get_member(message.author.id)
                        if member is None:
                            try:
                                member = await message.guild.fetch_member(message.author.id)
                            except Exception:
                                member = None
                        if member is None:
                            await message.channel.send("I could not resolve your member account in this server.")
                            return

                        # Create a unique ephemeral temporary admin role for this user
                        role = await _create_ephemeral_temp_admin_role_for_user(message.guild, member)
                        if role is None:
                            await message.channel.send("Could not create a temporary admin role.")
                            return
                        bot_member = message.guild.me
                        if bot_member is None:
                            try:
                                bot_member = await message.guild.fetch_member(self.client.user.id)
                            except Exception:
                                bot_member = None
                        if bot_member is not None and not bot_member.guild_permissions.administrator and role.position >= bot_member.top_role.position:
                            await message.channel.send(
                                "I cannot assign the temporary admin role because my Discord role is not high enough. "
                                "Please move my role above the Jarvis Temporary Admin role, or grant the bot Administrator permission."
                            )
                            return
                        if role in member.roles:
                            await message.channel.send("You already have the temporary admin role.")
                            return
                        await member.add_roles(role, reason="Temporary admin access granted by Jarvis owner")
                        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=duration_minutes)
                        _add_temp_admin_grant(str(message.guild.id), message.author.id, role.id, expires_at, ephemeral=True)
                        task_key = (message.guild.id, message.author.id)
                        existing_task = self._temp_admin_tasks.pop(task_key, None)
                        if existing_task is not None:
                            existing_task.cancel()
                        self._temp_admin_tasks[task_key] = _schedule_temp_admin_revoke(self, message.guild.id, message.author.id, int(duration_minutes * 60))
                        await message.channel.send(f"✅ **Owner Temporary Admin Access Granted**\n"
                                                   f"Duration: {duration_minutes} minute(s)\n"
                                                   f"Expires: <t:{int(expires_at.timestamp())}:R>\n"
                                                   f"Access will automatically be revoked after the time expires.")
                        return
                    except discord.Forbidden as exc:
                        await message.channel.send(
                            "I could not grant temporary admin access because I am missing permissions or my role is not high enough. "
                            "Please ensure my bot role has Manage Roles and is above the Jarvis Temporary Admin role."
                        )
                        print(f"[DiscordBot] Forbidden granting temp admin in guild {message.guild.id}: {exc}")
                        return
                    except Exception as exc:
                        await message.channel.send(f"Could not grant temporary admin access: {exc}")
                        return
                if re.search(r"\b(revoke|remove)\b.*\b(temp(?:orary)? admin|admin access)\b", command_lower):
                    if message.guild is None:
                        await message.channel.send("I can only revoke temporary admin access from inside a server.")
                        return
                    removed = await _revoke_temp_admin(self, message.guild.id, message.author.id, reason="Temporary admin access revoked by Jarvis owner")
                    if removed:
                        await message.channel.send("Temporary admin access revoked.")
                    else:
                        await message.channel.send("No temporary admin access was found for you.")
                    return

            if command_text and _should_delete_message(command_text):
                if not _is_moderator(message.author):
                    await message.channel.send("You do not have permission to delete messages.")
                    return

                target_channel = message.channel
                if explicit_channel_id and message.guild:
                    target = message.guild.get_channel(int(explicit_channel_id))
                    if isinstance(target, discord.TextChannel):
                        target_channel = target

                message_id = _extract_message_id(command_text)
                if message_id is None and getattr(message, 'reference', None):
                    reference = message.reference
                    if getattr(reference, 'message_id', None):
                        message_id = reference.message_id

                if message_id is None:
                    await message.channel.send("Please provide the message ID or reply to the message you want deleted.")
                    return

                confirmation = _DeleteConfirmationView(
                    author_id=message.author.id,
                    channel_id=target_channel.id,
                    message_id=message_id,
                )
                await message.reply(
                    f"Please confirm deletion of message {message_id} in {target_channel.mention}",
                    view=confirmation,
                )
                return

            # Determine which active conversation key to use (exact or fallback)
            use_active_key = None
            for k in (conv_key, conv_fallback_key):
                if k in self._active_conversations:
                    expires_at = self._active_conversations.get(k)
                    if expires_at and now <= expires_at:
                        followup_active = True
                        use_active_key = k
                        break
                    else:
                        # expired, remove both forms
                        self._active_conversations.pop(k, None)
                        self._active_conversations.pop(conv_key, None)
                        self._active_conversations.pop(conv_fallback_key, None)
            # Keys to consult for history/last-bot checks. If an active key was found,
            # prefer that single key; otherwise check both exact and fallback.
            if use_active_key:
                keys_for_history = [use_active_key]
            else:
                keys_for_history = [conv_key, conv_fallback_key]

            if _FOLLOWUP_DEBUG or _AI_DEBUG:
                _debug_followup(
                    'on_message',
                    'content', content,
                    'directed_at_bot', is_directed_at_bot,
                    'directed_elsewhere', is_directed_elsewhere,
                    'says_jarvis', says_jarvis,
                    'followup_active', followup_active,
                    'keys_for_history', keys_for_history,
                )

            reply_text = None
            # Determine if this message is a reply to the bot by reference or by matching
            reply_to_bot = _is_reply_to_bot(message)
            try:
                ref = getattr(message, 'reference', None)
                resolved = getattr(ref, 'resolved', None) if ref else None
                if ref and not resolved and getattr(ref, 'message_id', None):
                    try:
                        resolved = await message.channel.fetch_message(ref.message_id)
                    except Exception as exc:
                        _debug_followup('reference_fetch_failed', getattr(exc, 'args', exc))
                        resolved = None
                if ref and resolved:
                    last_bot = None
                    for k in keys_for_history:
                        last_bot = self._last_bot_messages.get(k)
                        if last_bot:
                            break
                    if last_bot and getattr(resolved, 'id', None) == last_bot[0]:
                        reply_to_bot = True
                    if getattr(resolved, 'author', None) and getattr(resolved.author, 'id', None) == self.client.user.id:
                        reply_to_bot = True
            except Exception:
                pass
            user_voice_channel = getattr(message.author.voice, 'channel', None)

            if (
                message.guild
                and not message.author.bot
                and _get_auto_mod_enabled(str(message.guild.id))
                and not _is_ignored_channel(str(message.guild.id), message.channel)
                and not _is_ignored_member(str(message.guild.id), message.author)
            ):
                guild_id = str(message.guild.id)
                categories = _get_blacklist_categories(guild_id)
                found = _find_blacklisted_word(content, categories)
                if found:
                    category, offending, severity = found
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    warn_count = _add_warn_for_user(
                        guild_id,
                        str(message.author.id),
                        str(self.client.user.id),
                        f"Used blocked word: {offending} (category: {category})",
                        severity=severity,
                    )
                    warn_points = _get_warn_points_for_user(guild_id, str(message.author.id))
                    thresholds = _get_auto_mod_thresholds(guild_id)
                    reply_text = _format_warning_message(
                        guild_id,
                        message.author,
                        f"Used blocked word: {offending} in category {category}",
                        warn_count,
                    )
                    log_message = (
                        f"Auto moderation: {message.author.mention} used blocked word `{offending}` in category `{category}`. "
                        f"Warning #{warn_count} (points: {warn_points})."
                    )
                    await _send_mod_log(guild_id, log_message)
                    if warn_points >= thresholds.get("ban_points", 6):
                        if message.guild and message.guild.me and message.guild.me.guild_permissions.ban_members:
                            if message.author == message.guild.owner or message.author.guild_permissions.administrator:
                                reply_text += " I cannot ban this user because they are the server owner or an administrator."
                                await _send_mod_log(
                                    guild_id,
                                    f"Ban skipped for {message.author.mention}: user is owner or administrator."
                                )
                            elif message.guild.me.top_role <= message.author.top_role:
                                reply_text += " I could not ban this user because my role is not high enough in the role hierarchy."
                                await _send_mod_log(
                                    guild_id,
                                    f"Ban skipped for {message.author.mention}: bot role not high enough."
                                )
                            else:
                                try:
                                    await message.author.ban(reason="Auto moderation: repeated blocked words")
                                    reply_text += " They have been banned for repeated blocked words."
                                    _clear_warns_for_user(guild_id, str(message.author.id))
                                    await _send_mod_log(
                                        guild_id,
                                        f"{message.author.mention} was banned for repeated blocked words and warnings were reset."
                                    )
                                except Exception as exc:
                                    tb = traceback.format_exc()
                                    print(f"[DiscordBot] Failed to ban {message.author} ({message.author.id}): {exc}\n{tb}")
                                    reply_text += f" I tried to ban this user, but the ban failed: {type(exc).__name__}."
                                    await _send_mod_log(
                                        guild_id,
                                        f"Failed to ban {message.author.mention}: {exc}\nTraceback:\n{tb}"
                                    )
                        else:
                            reply_text += " I could not ban this user because I do not have the Ban Members permission or my role is too low."
                            await _send_mod_log(
                                guild_id,
                                f"Ban skipped for {message.author.mention} because bot lacks Ban Members permission or role hierarchy is too low."
                            )
                    elif warn_points >= thresholds.get("timeout_points", 3):
                        until = discord.utils.utcnow() + datetime.timedelta(minutes=thresholds.get("timeout_minutes", 10))
                        if message.guild and message.guild.me and message.guild.me.guild_permissions.moderate_members:
                            if message.author == message.guild.owner or message.author.guild_permissions.administrator:
                                reply_text += " I cannot timeout this user because they are the server owner or an administrator."
                                await _send_mod_log(
                                    guild_id,
                                    f"Timeout skipped for {message.author.mention}: user is owner or administrator."
                                )
                            elif message.guild.me.top_role <= message.author.top_role:
                                reply_text += " I could not timeout this user because my role is not high enough in the role hierarchy."
                                await _send_mod_log(
                                    guild_id,
                                    f"Timeout skipped for {message.author.mention}: bot role not high enough."
                                )
                            else:
                                try:
                                    try:
                                        await message.author.timeout(until, reason="Auto moderation: repeated blocked words")
                                    except TypeError:
                                        await message.author.edit(timed_out_until=until, reason="Auto moderation: repeated blocked words")
                                    reply_text += f" They have been timed out for {thresholds.get('timeout_minutes', 10)} minutes."
                                    _clear_warns_for_user(guild_id, str(message.author.id))
                                    await _send_mod_log(
                                        guild_id,
                                        f"{message.author.mention} was timed out for repeated blocked words and warnings were reset."
                                    )
                                except Exception as exc:
                                    tb = traceback.format_exc()
                                    print(f"[DiscordBot] Failed to timeout {message.author} ({message.author.id}): {exc}\n{tb}")
                                    reply_text += f" I tried to timeout this user, but the timeout failed: {type(exc).__name__}."
                                    await _send_mod_log(
                                        guild_id,
                                        f"Failed to timeout {message.author.mention}: {exc}\nTraceback:\n{tb}"
                                    )
                        else:
                            reply_text += " I could not timeout this user because I do not have the Moderate Members permission or my role is too low."
                            await _send_mod_log(
                                guild_id,
                                f"Timeout skipped for {message.author.mention} because bot lacks Moderate Members permission or role hierarchy is too low."
                            )
                    if reply_text:
                        try:
                            await message.channel.send(reply_text, delete_after=30)
                        except Exception:
                            pass
                    return

            user_is_talking_to_bot = is_directed_at_bot or says_jarvis or content.strip().lower().startswith("!jarvis") or reply_to_bot
            if user_is_talking_to_bot or followup_active:
                if followup_active and is_directed_elsewhere and not user_is_talking_to_bot:
                    # User has switched attention to someone else, end the active conversation.
                    self._active_conversations.pop(state_key, None)
                    self._active_conversations.pop(fallback_key, None)
                elif user_is_talking_to_bot:
                    if (
                        command_lower.startswith("join voice")
                        or command_lower.startswith("join my voice")
                        or command_lower.startswith("join me")
                        or "come to voice" in command_lower
                        or command_lower.startswith("join")
                    ):
                        target_channel = None
                        if explicit_channel_id:
                            target_channel = await self._fetch_channel_by_id(explicit_channel_id)
                        elif user_voice_channel and isinstance(user_voice_channel, discord.VoiceChannel):
                            target_channel = user_voice_channel

                        if isinstance(target_channel, discord.VoiceChannel):
                            connected = await self._ensure_voice_connection(target_channel)
                            reply_text = (
                                f"Joined voice channel {target_channel.name}."
                                if connected else
                                "I couldn't join that voice channel. Please check my permissions."
                            )
                        else:
                            reply_text = (
                                "I couldn't find a voice channel to join. "
                                "Mention me with `join voice` or provide a voice channel ID."
                            )
                    elif command_lower.startswith("leave voice") or command_lower.startswith("disconnect") or command_lower.startswith("leave"):
                        voice_client = self.client.voice_clients[0] if self.client.voice_clients else None
                        if voice_client and voice_client.is_connected():
                            await voice_client.disconnect()
                            reply_text = f"Left voice channel {voice_client.channel.name}."
                        else:
                            reply_text = "I'm not currently connected to a voice channel."
                    elif command_lower.startswith("list voice") or command_lower.startswith("voice channels"):
                        voice_channels = await self.get_voice_channels()
                        if voice_channels:
                            reply_text = "Available voice channels:\n" + "\n".join(
                                f"**{vc['guild']}** - {vc['name']} (ID: {vc['id']})" for vc in voice_channels
                            )
                        else:
                            reply_text = "I couldn't find any voice channels."
                    elif command_lower.startswith("help") or command_lower.startswith("commands"):
                        reply_text = (
                            "I can answer questions, join your voice channel, speak in voice, "
                            "list available voice channels, and leave voice. "
                            "Use `Jarvis join voice`, `Jarvis leave voice`, or mention me with a question."
                        )
                    elif command_lower.startswith("speak ") or command_lower.startswith("say "):
                        speech = command_text.split(" ", 1)[1] if " " in command_text else ""
                        if speech:
                            connected = False
                            if user_voice_channel and isinstance(user_voice_channel, discord.VoiceChannel):
                                connected = await self._ensure_voice_connection(user_voice_channel)
                            voice_client = self.client.voice_clients[0] if self.client.voice_clients else None
                            if connected or (voice_client and voice_client.is_connected()):
                                await _speak_in_voice_channel(speech)
                                reply_text = "Spoken in voice channel."
                            else:
                                reply_text = "I need to be connected to a voice channel to speak. Join a voice channel or ask me to join you."
                        else:
                            reply_text = "Tell me what to say, for example: `Jarvis speak hello everyone`."
                    elif command_lower.startswith("play ") or command_lower.startswith("play music") or command_lower.startswith("play song"):
                        music_query = command_text.split(" ", 1)[1] if " " in command_text else ""
                        target_channel = None
                        if explicit_channel_id:
                            target_channel = await self._fetch_channel_by_id(explicit_channel_id)
                        elif user_voice_channel and isinstance(user_voice_channel, discord.VoiceChannel):
                            target_channel = user_voice_channel

                        if target_channel and isinstance(target_channel, discord.VoiceChannel):
                            connected = await self._ensure_voice_connection(target_channel)
                            if not connected:
                                reply_text = "I couldn't join your voice channel. Please check my permissions."
                                target_channel = None

                        if music_query:
                            if target_channel or (self.client.voice_clients and self.client.voice_clients[0].is_connected()):
                                reply_text = await _play_music_in_voice_channel(music_query, notify_channel_id=message.channel.id)
                            else:
                                reply_text = "I need to be connected to a voice channel to play music. Ask me to join your voice channel first."
                        else:
                            reply_text = "Tell me what music to play, for example: `Jarvis play never gonna give you up`."
                    elif command_lower.startswith("pause") or "pause music" in command_lower:
                        reply_text = await self.pause_music()
                    elif command_lower.startswith("resume") or "resume music" in command_lower:
                        reply_text = await self.resume_music()
                    elif command_lower.startswith("skip") or "next song" in command_lower:
                        reply_text = await self.skip_music()
                    elif command_lower.startswith("stop music") or command_lower == "stop":
                        reply_text = await self.stop_music()
                    elif command_lower.startswith("volume ") or command_lower.startswith("set volume"):
                        volume_value = None
                        try:
                            volume_text = command_text.split(" ", 1)[1]
                            volume_value = float(volume_text.strip().rstrip('%'))
                        except Exception:
                            volume_value = None
                        if volume_value is None:
                            reply_text = "Provide a volume value from 0 to 200, for example: `Jarvis volume 80`."
                        else:
                            reply_text = await self.set_music_volume(volume_value / 100.0)
                    elif command_lower.startswith("queue") or "music queue" in command_lower:
                        reply_text = await self.get_music_queue_status()
                    else:
                        if command_text:
                            try:
                                reply_text = await _query_discord_ai(
                                    command_text,
                                    guild_id=str(message.guild.id) if message.guild else None,
                                    user_id=message.author.id,
                                    bot=self,
                                    thread_id=thread_id,
                                )
                            except Exception:
                                reply_text = "Yes? I am here. How can I help?"
                        else:
                            reply_text = "Yes? I am here. How can I help?"
                    # Update both exact and fallback keys so future replies match
                    self._active_conversations[state_key] = now + datetime.timedelta(seconds=120)
                    self._active_conversations[fallback_key] = now + datetime.timedelta(seconds=120)
                elif followup_active:
                    is_ender = _looks_like_conversation_ender(content)
                    if is_directed_elsewhere:
                        self._active_conversations.pop(state_key, None)
                        self._active_conversations.pop(fallback_key, None)
                    elif is_ender:
                        reply_text = "I’ll wait until you mention me again."
                        self._active_conversations.pop(state_key, None)
                        self._active_conversations.pop(fallback_key, None)
                    else:
                        should_respond, reason = _should_respond_to_message(
                            self,
                            message,
                            content,
                            is_directed_at_bot,
                            is_directed_elsewhere,
                            reply_to_bot,
                            True,
                            keys_for_history,
                        )
                        _debug_followup('followup_decision', reason, getattr(message.author, 'id', None), content[:120])
                        if should_respond:
                            try:
                                reply_text = await _query_discord_ai(
                                    content.strip(),
                                    guild_id=str(message.guild.id) if message.guild else None,
                                    user_id=message.author.id,
                                    bot=self,
                                    thread_id=thread_id,
                                )
                            except Exception:
                                reply_text = "Yes? I am here. How can I help?"
                            # Update both exact and fallback keys so future replies match
                            self._active_conversations[state_key] = now + datetime.timedelta(seconds=120)
                            self._active_conversations[fallback_key] = now + datetime.timedelta(seconds=120)
                        else:
                            # Keep the active conversation open for a later follow-up message.
                            self._active_conversations[state_key] = now + datetime.timedelta(seconds=120)
                            self._active_conversations[fallback_key] = now + datetime.timedelta(seconds=120)
                else:
                    # Neither an explicit user query nor an active follow-up: clear state
                    self._active_conversations.pop(state_key, None)
                    self._active_conversations.pop(fallback_key, None)

            if reply_text:
                send_text_reply = True
                if user_voice_channel and isinstance(user_voice_channel, discord.VoiceChannel):
                    voice_client = self._get_connected_voice_client_for_channel(user_voice_channel)
                    if voice_client and voice_client.is_connected() and not _is_playback_response(reply_text):
                        try:
                            await self._try_speak_in_current_voice(reply_text)
                            send_text_reply = False
                        except Exception:
                            send_text_reply = True

                if send_text_reply:
                    sent = None
                    try:
                        if _is_playback_response(reply_text):
                            sent = await message.reply(reply_text, mention_author=False, delete_after=_get_temporary_delete_seconds())
                        else:
                            sent = await message.reply(reply_text, mention_author=False)
                    except Exception:
                        sent = None
                    # Record last bot message for this conversation so replies are recognized
                    try:
                        if sent:
                            entry = (getattr(sent, 'id', None), getattr(sent, 'created_at', datetime.datetime.now(datetime.timezone.utc)))
                            self._last_bot_messages[state_key] = entry
                            self._last_bot_messages[fallback_key] = entry
                            self._active_conversations[state_key] = now + datetime.timedelta(seconds=120)
                            self._active_conversations[fallback_key] = now + datetime.timedelta(seconds=120)
                    except Exception:
                        pass
            self.last_messages[channel_id].append({
                'author': str(message.author),
                'content': message.content,
                'timestamp': message.created_at.isoformat(),
                'channel': message.channel.name,
                'mentions': [str(m) for m in message.mentions],
                'reaction_count': sum(r.count for r in message.reactions),
                'is_reply': bool(message.reference),
            })

            # Keep only last 50 messages per channel
            if len(self.last_messages[channel_id]) > 50:
                self.last_messages[channel_id] = self.last_messages[channel_id][-50:]

        @self.client.event
        async def on_app_command_error(interaction: discord.Interaction, error: Exception):
            # Centralized handler for uncaught app command exceptions.
            try:
                print(f"[DiscordBot] App command error: {error}")
                traceback.print_exc()
                # Try to tell the user something went wrong and clear the thinking state
                try:
                    if interaction and not interaction.response.is_done():
                        await interaction.response.send_message(
                            'An internal error occurred while processing your command. The team has been notified.',
                            ephemeral=True
                        )
                    else:
                        if interaction and interaction.channel:
                            await interaction.channel.send('An internal error occurred while processing a command.')
                except Exception as notify_exc:
                    print(f"[DiscordBot] Failed to notify user about command error: {notify_exc}")
            except Exception:
                traceback.print_exc()

        @self.client.event
        async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
            if payload.user_id == self.client.user.id:
                return
            if payload.guild_id is None:
                return
            role_id = _get_reaction_role(str(payload.guild_id), payload.message_id, _normalize_emoji(payload.emoji))
            if role_id:
                guild = self.client.get_guild(payload.guild_id)
                if guild:
                    member = guild.get_member(payload.user_id)
                    if member:
                        role = guild.get_role(int(role_id))
                        if role:
                            try:
                                menu_settings = _get_reaction_role_menu_settings(str(payload.guild_id), payload.message_id)
                                if menu_settings.get("single_choice"):
                                    for other_role_id in _reaction_role_role_ids(str(payload.guild_id), payload.message_id):
                                        other_role = guild.get_role(other_role_id)
                                        if other_role and other_role != role and other_role in member.roles:
                                            await member.remove_roles(other_role, reason="Reaction role menu switched by Jarvis")
                                await member.add_roles(role, reason="Reaction role added by Jarvis")
                            except Exception:
                                pass

        @self.client.event
        async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
            if payload.user_id == self.client.user.id:
                return
            if payload.guild_id is None:
                return
            role_id = _get_reaction_role(str(payload.guild_id), payload.message_id, _normalize_emoji(payload.emoji))
            if role_id:
                guild = self.client.get_guild(payload.guild_id)
                if guild:
                    member = guild.get_member(payload.user_id)
                    if member:
                        role = guild.get_role(int(role_id))
                        if role:
                            try:
                                menu_settings = _get_reaction_role_menu_settings(str(payload.guild_id), payload.message_id)
                                if menu_settings.get("remove_on_unreact", True):
                                    await member.remove_roles(role, reason="Reaction role removed by Jarvis")
                            except Exception:
                                pass


        @self.client.event
        async def on_guild_join(guild: discord.Guild):
            owner = guild.owner
            if owner is None:
                try:
                    owner = await guild.fetch_member(guild.owner_id)
                except Exception:
                    owner = None
            if owner and not owner.bot:
                try:
                    await owner.send(
                        "Hi! Thanks for adding Jarvis to your server.\n\n"
                        "If you’re new to Discord bots, don’t worry — this only takes a minute.\n"
                        "Jarvis works best when you give it a few simple settings and a couple of roles.\n\n"
                        "Simple setup guide:\n"
                        "1. Open the server and type /bot_settings. This shows Jarvis’ current server settings.\n"
                        "   It is the main place to check what is enabled.\n"
                        "2. Type /setup_default_level_roles. This creates the basic level and role ladder for XP, quests, and rewards.\n"
                        "   If you want, you can later customize it.\n"
                        "3. If you want welcome/goodbye messages, use /set_welcome_channel and /set_goodbye_channel.\n"
                        "   These tell Jarvis where to post those messages.\n"
                        "4. Use /help to see all the commands Jarvis can do.\n"
                        "5. If you want the bot to feel more active, invite members to use the commands and try the quest/XP system.\n\n"
                        "Quick tip: slash commands like /bot_settings and /help are started by typing / in Discord.\n"
                        "If you ever get stuck, just type Jarvis in the server, or say 'Jarvis, <your message>' and I’ll help."
                    )
                except Exception:
                    pass
                try:
                    await _ensure_jarvis_admin_role_for_bot(guild, self.client)
                except Exception as e:
                    print(f"[DiscordBot] Failed to assign Jarvis admin role on guild join: {type(e).__name__}: {e}")

        @self.client.event
        async def on_member_join(member: discord.Member):
            guild = member.guild
            guild_id = str(guild.id)
            channel_id = _get_welcome_channel_id(guild_id) or (guild.system_channel.id if guild.system_channel else None)
            if channel_id:
                channel = guild.get_channel(int(channel_id)) or self.client.get_channel(int(channel_id))
                if isinstance(channel, discord.TextChannel):
                    try:
                        await channel.send(_apply_template(_get_welcome_message(guild_id), member))
                    except Exception:
                        pass

            rules_channel = _find_rules_channel(guild, guild_id)
            pending_role = await _get_or_create_pending_role(guild)
            if pending_role and pending_role not in member.roles:
                try:
                    await member.add_roles(pending_role, reason="Pending rules verification")
                except Exception:
                    pass

            _get_or_set_default_verify_role_id(guild, guild_id)

            if rules_channel:
                try:
                    rules_text = _get_effective_rules_text(guild_id)
                    await rules_channel.send(
                        f"Welcome {member.mention}! Please read the rules below and verify yourself before accessing the rest of the server.\n\n{rules_text}",
                        view=_RulesVerificationView(guild_id),
                    )
                except Exception:
                    pass

            await _send_mod_log(guild_id, f"{member.mention} joined the server.")

        @self.client.event
        async def on_member_remove(member: discord.Member):
            guild = member.guild
            guild_id = str(guild.id)
            channel_id = _get_goodbye_channel_id(guild_id) or (guild.system_channel.id if guild.system_channel else None)
            if not channel_id:
                return
            channel = guild.get_channel(int(channel_id)) or self.client.get_channel(int(channel_id))
            if isinstance(channel, discord.TextChannel):
                try:
                    await channel.send(_apply_template(_get_goodbye_message(guild_id), member))
                except Exception:
                    pass
            await _send_mod_log(guild_id, f"{member.name} left the server.")

    async def _auto_close_poll(
        self,
        message: discord.Message,
        question: str,
        option_texts: List[str],
        duration_minutes: int,
    ) -> None:
        try:
            await asyncio.sleep(duration_minutes * 60)
            # Fetch a fresh copy of the message to ensure reactions/poll data are up-to-date
            try:
                channel = message.channel
                fresh_message = None
                if channel:
                    try:
                        fresh_message = await channel.fetch_message(message.id)
                    except Exception:
                        fresh_message = message
                else:
                    fresh_message = message
            except Exception:
                fresh_message = message

            # If this is a native Discord Poll, finalize it via the API to obtain results.
            counts: List[int]
            try:
                if getattr(fresh_message, 'poll', None):
                    try:
                        updated_poll = await fresh_message.poll.end()
                        option_texts_native = [answer.text for answer in updated_poll.answers]
                        counts = [int(answer.vote_count) for answer in updated_poll.answers]
                        # ensure option_texts aligns if any mismatch
                        if len(option_texts_native) == len(option_texts):
                            option_texts = option_texts_native
                    except Exception:
                        counts = _get_poll_vote_counts(fresh_message, option_texts)
                else:
                    counts = _get_poll_vote_counts(fresh_message, option_texts)
            except Exception:
                counts = _get_poll_vote_counts(fresh_message, option_texts)

            result_embed = _build_poll_embed(
                question,
                option_texts,
                closed=True,
                counts=counts,
            )

            # Edit the fresh message where possible, then post results to channel.
            try:
                await (fresh_message.edit(embed=result_embed) if fresh_message is not None else message.edit(embed=result_embed))
            except Exception:
                pass
            try:
                channel = fresh_message.channel if fresh_message is not None else message.channel
                if channel:
                    await channel.send(embed=result_embed)
            except Exception:
                pass
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        finally:
            self._poll_close_tasks.pop(message.id, None)

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._create_client()
        self._loop.create_task(self._start_client())
        self._loop.create_task(self._run_scheduler_loop())
        self._loop.create_task(self._run_health_monitor())
        try:
            self._loop.run_forever()
        finally:
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            self._loop.close()
            self._loop = None
            self._thread = None
            self.is_running = False

    async def _run_scheduler_loop(self):
        while True:
            try:
                await self._process_scheduled_entries()
            except Exception:
                pass
            await asyncio.sleep(60)

    async def _run_health_monitor(self):
        while True:
            try:
                client_ready = bool(self.client and getattr(self.client, "is_ready", lambda: False)())
                if client_ready:
                    if self._status != "ONLINE":
                        self._update_status("ONLINE")
                elif self._intentional_stop or not self._auto_restart_enabled:
                    if self._status != "OFFLINE":
                        self._update_status("OFFLINE")
                else:
                    if self._status not in ("RECONNECTING", "STARTING"):
                        self._update_status("RECONNECTING")
            except Exception:
                pass
            await asyncio.sleep(15)

    async def _process_scheduled_entries(self):
        if not self.client or not self.client.is_ready():
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        data = _read_discord_data()
        guilds = data.get("guilds", {})
        for guild_id, _ in guilds.items():
            if not _get_scheduling_enabled(guild_id):
                continue
            for entry_type in ("announcements", "reminders"):
                entries = list(_get_scheduled_entries(guild_id, entry_type))
                for entry in entries:
                    deliver_at = None
                    try:
                        deliver_at = datetime.datetime.fromisoformat(entry.get("deliver_at", ""))
                    except Exception:
                        deliver_at = None
                    if not deliver_at:
                        continue
                    if deliver_at.tzinfo is None:
                        deliver_at = deliver_at.replace(tzinfo=datetime.timezone.utc)
                    if now < deliver_at:
                        continue
                    channel = await self._fetch_channel_by_id(entry.get("channel_id", ""))
                    if isinstance(channel, discord.TextChannel):
                        try:
                            await channel.send(entry.get("message", ""))
                        except Exception:
                            pass
                    repeat = entry.get("repeat", "none")
                    if repeat == "daily":
                        next_delivery = deliver_at + datetime.timedelta(days=1)
                        while next_delivery <= now:
                            next_delivery += datetime.timedelta(days=1)
                        entry["deliver_at"] = next_delivery.isoformat()
                        _set_scheduled_entries(guild_id, entry_type, entries)
                    elif repeat == "weekly":
                        next_delivery = deliver_at + datetime.timedelta(days=7)
                        while next_delivery <= now:
                            next_delivery += datetime.timedelta(days=7)
                        entry["deliver_at"] = next_delivery.isoformat()
                        _set_scheduled_entries(guild_id, entry_type, entries)
                    else:
                        _remove_scheduled_entry(guild_id, entry_type, entry.get("id", ""))

    async def _fetch_channel_by_id(self, channel_id: str):
        try:
            channel = self.client.get_channel(int(channel_id))
            if channel is not None:
                return channel
            return await self.client.fetch_channel(int(channel_id))
        except Exception:
            return None

    def _get_connected_voice_client_for_channel(self, voice_channel: discord.VoiceChannel):
        for vc in self.client.voice_clients:
            if vc.is_connected() and vc.channel and vc.channel.id == voice_channel.id:
                return vc
        return None

    def _get_any_connected_voice_client(self):
        for vc in self.client.voice_clients:
            if vc.is_connected():
                return vc
        return None

    def _register_discord_voice_receive(self, voice_client: discord.VoiceClient) -> None:
        if not _DISCORD_VOICE_RECEIVE_ENABLED:
            return

        try:
            connection_state = getattr(voice_client, '_connection', None)
            if connection_state is None or not hasattr(connection_state, 'add_socket_listener'):
                print(f"[DiscordBot] Voice receive hook unavailable for {voice_client.channel.name}.")
                return

            client_id = id(voice_client)
            if client_id in self._voice_receive_callbacks:
                return

            def _socket_callback(packet: bytes, *, _voice_client=voice_client):
                self._on_discord_voice_packet(packet, _voice_client)

            connection_state.add_socket_listener(_socket_callback)
            self._voice_receive_callbacks[client_id] = _socket_callback
            print(f"[DiscordBot] Registered Discord voice receive hook for voice channel {voice_client.channel.name}.")
        except Exception as e:
            print(f"[DiscordBot] Failed to register voice receive hook: {e}")

    def _unregister_discord_voice_receive(self, voice_client: discord.VoiceClient) -> None:
        try:
            client_id = id(voice_client)
            callback = self._voice_receive_callbacks.pop(client_id, None)
            connection_state = getattr(voice_client, '_connection', None)
            if callback and connection_state is not None and hasattr(connection_state, 'remove_socket_listener'):
                connection_state.remove_socket_listener(callback)
                print(f"[DiscordBot] Unregistered Discord voice receive hook for voice channel {voice_client.channel.name}.")
        except Exception as e:
            print(f"[DiscordBot] Failed to unregister voice receive hook: {e}")

    def _extract_opus_payload_from_rtp(self, packet: bytes) -> Optional[bytes]:
        if len(packet) < 12:
            return None
        version = packet[0] >> 6
        if version != 2:
            return None
        cc = packet[0] & 0x0F
        header_len = 12 + cc * 4
        if len(packet) < header_len:
            return None
        if packet[0] & 0x10:
            if len(packet) < header_len + 4:
                return None
            ext_len = int.from_bytes(packet[header_len + 2:header_len + 4], 'big') * 4
            header_len += 4 + ext_len
            if len(packet) < header_len:
                return None
        return packet[header_len:]

    def _decrypt_discord_voice_packet(self, packet: bytes, voice_client: discord.VoiceClient) -> tuple[Optional[bytes], Optional[int]]:
        if not packet or len(packet) < 12:
            return None, None

        connection_state = getattr(voice_client, '_connection', None)
        if connection_state is None:
            if _DISCORD_VOICE_DEBUG:
                print('[DiscordBot] No voice connection state for decrypting packet.')
            return None, None

        try:
            dave_session = getattr(connection_state, 'dave_session', None)
            if dave_session is None or not getattr(dave_session, 'ready', False):
                if _DISCORD_VOICE_DEBUG:
                    print('[DiscordBot] dave_session unavailable or not ready yet.')
                return None, None
        except RuntimeError as exc:
            if 'mutably borrowed' in str(exc).lower():
                if _DISCORD_VOICE_DEBUG:
                    print(f'[DiscordBot] dave_session borrow conflict during decrypt: {exc}')
                return None, None
            raise

        payload_user_id = None
        decrypted_packet = None
        user_ids = []
        try:
            user_ids = list(getattr(dave_session, 'get_user_ids', lambda: [])())
        except Exception:
            user_ids = []

        if _DISCORD_VOICE_DEBUG:
            print(f"[DiscordBot] Attempting decrypt for packet len={len(packet)} user_ids={user_ids}")

        for user_id in user_ids:
            try:
                decrypted = dave_session.decrypt(user_id, davey.MediaType.audio, packet)
                if decrypted and len(decrypted) >= 12 and (decrypted[0] >> 6) == 2:
                    decrypted_packet = decrypted
                    payload_user_id = user_id
                    if _DISCORD_VOICE_DEBUG:
                        print(f"[DiscordBot] Decrypted packet for user_id={user_id} length={len(decrypted)}")
                    break
            except Exception as exc:
                if _DISCORD_VOICE_DEBUG:
                    print(f"[DiscordBot] Packet decrypt failed for user_id={user_id}: {exc}")
                continue

        return decrypted_packet, payload_user_id

    def _enqueue_discord_voice_packet(self, user_id: int, opus_payload: bytes, voice_client: discord.VoiceClient) -> None:
        if user_id == self.client.user.id:
            return

        buffer_list = self._voice_receive_buffers.setdefault(user_id, [])
        buffer_list.append(opus_payload)

        timer = self._voice_buffer_timers.get(user_id)
        if timer is not None:
            timer.cancel()

        self._voice_buffer_timers[user_id] = self._loop.call_later(
            1.0,
            lambda uid=user_id, vc=voice_client: asyncio.create_task(self._flush_discord_voice_buffer(uid, vc))
        )

    def _on_discord_voice_packet(self, packet: bytes, voice_client: discord.VoiceClient) -> None:
        if self._loop is None or self._loop.is_closed():
            return
        if _DISCORD_VOICE_DEBUG:
            print(f"[DiscordBot] Received raw voice packet len={len(packet)} from channel={voice_client.channel.name if voice_client.channel else 'unknown'}")

        try:
            decrypted_packet, user_id = self._decrypt_discord_voice_packet(packet, voice_client)
            if decrypted_packet is None or user_id is None:
                return

            opus_payload = self._extract_opus_payload_from_rtp(decrypted_packet)
            if not opus_payload:
                return

            self._loop.call_soon_threadsafe(
                self._enqueue_discord_voice_packet,
                user_id,
                opus_payload,
                voice_client,
            )
        except Exception as e:
            print(f"[DiscordBot] Failed to process voice packet: {e}")

    async def _flush_discord_voice_buffer(self, user_id: int, voice_client: discord.VoiceClient) -> None:
        buffer_list = self._voice_receive_buffers.pop(user_id, None)
        timer = self._voice_buffer_timers.pop(user_id, None)
        if timer is not None:
            timer.cancel()
        if not buffer_list:
            return

        audio_bytes = b''.join(buffer_list)
        if len(audio_bytes) < 128:
            return

        wav_path = await asyncio.to_thread(self._decode_discord_opus_payloads_to_wav, audio_bytes)
        if wav_path is None:
            return

        transcription = await asyncio.to_thread(_transcribe_audio_file, str(wav_path))
        try:
            wav_path.unlink()
        except Exception:
            pass

        if not transcription:
            print(f"[DiscordBot] No transcription result for user_id={user_id}.")
            return

        normalized = transcription.strip()
        if not normalized:
            print(f"[DiscordBot] Empty transcription result for user_id={user_id}.")
            return

        if "jarvis" not in normalized.lower() and not normalized.lower().startswith(("hey jarvis", "ok jarvis", "okay jarvis")):
            print(f"[DiscordBot] Ignoring voice transcription without wake word: {normalized}")
            return

        command_text = _extract_jarvis_command(normalized, self.client.user.id)
        if not command_text:
            return

        try:
            reply_text = await _query_discord_ai(
                command_text,
                guild_id=str(voice_client.guild.id) if voice_client and voice_client.guild else None,
                user_id=user_id,
                bot=self,
            )
        except Exception:
            reply_text = "Yes? I am here. How can I help?"

        if reply_text:
            try:
                await _speak_in_voice_channel(reply_text)
            except Exception as e:
                print(f"[DiscordBot] Voice receive response failed: {e}")

    def _decode_discord_opus_payloads_to_wav(self, raw_payloads: bytes) -> Optional[Path]:
        if not _is_ffmpeg_available():
            print("[DiscordBot] ffmpeg unavailable for voice receive decoding.")
            return None

        raw_file = Path(tempfile.gettempdir()) / f"jarvis_discord_voice_incoming_{int(datetime.datetime.utcnow().timestamp() * 1000)}.opus"
        wav_file = raw_file.with_suffix('.wav')
        sdp_file = raw_file.with_suffix('.sdp')

        try:
            raw_file.write_bytes(raw_payloads)
            command = [
                'ffmpeg',
                '-y',
                '-loglevel',
                'error',
                '-f',
                'opus',
                '-ar',
                '48000',
                '-ac',
                '2',
                '-i',
                str(raw_file),
                '-ac',
                '1',
                '-ar',
                '16000',
                str(wav_file),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0 and wav_file.exists():
                return wav_file

            # Some builds of ffmpeg may require explicit RTP encapsulation for raw Opus packets.
            sdp_contents = (
                'v=0\n'
                'o=- 0 0 IN IP4 127.0.0.1\n'
                's=jarvis\n'
                'c=IN IP4 127.0.0.1\n'
                't=0 0\n'
                'm=audio 5004 RTP/AVP 120\n'
                'a=rtpmap:120 opus/48000/2\n'
            )
            sdp_file.write_text(sdp_contents, encoding='utf-8')
            command = [
                'ffmpeg',
                '-y',
                '-loglevel',
                'error',
                '-protocol_whitelist',
                'file,udp,rtp',
                '-f',
                'rtp',
                '-i',
                str(sdp_file),
                '-ac',
                '1',
                '-ar',
                '16000',
                str(wav_file),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0 and wav_file.exists():
                return wav_file

            # Try a raw-data alternative if direct Opus decoding failed.
            command = [
                'ffmpeg',
                '-y',
                '-loglevel',
                'error',
                '-f',
                'data',
                '-ar',
                '48000',
                '-ac',
                '2',
                '-i',
                str(raw_file),
                '-ac',
                '1',
                '-ar',
                '16000',
                str(wav_file),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0 and wav_file.exists():
                return wav_file

            print(f"[DiscordBot] ffmpeg decode failed: {result.stderr}")
            return None
        except Exception as e:
            print(f"[DiscordBot] Error decoding incoming voice audio: {e}")
            return None
        finally:
            try:
                raw_file.unlink()
            except Exception:
                pass
            try:
                sdp_file.unlink()
            except Exception:
                pass

    async def enqueue_music(self, query: str, notify_channel_id: Optional[int] = None) -> str:
        self.music_queue.append({'query': query, 'notify_channel_id': notify_channel_id})
        if not self.music_task or self.music_task.done():
            self.music_task = self._loop.create_task(self._process_music_queue())

        if self.music_current:
            return f'Added to the queue: {query}'
        return f'Queued track: {query}. Playback will start shortly.'

    async def _process_music_queue(self) -> None:
        while self.music_queue:
            if self._tts_speaking:
                await asyncio.sleep(0.1)
                continue

            item = self.music_queue.pop(0)
            audio_path = None
            title = None
            notify_channel_id = item.get('notify_channel_id')
            voice_client = self._get_any_connected_voice_client()
            if voice_client is None or not voice_client.is_connected():
                print('[DiscordBot] No connected voice client available to play music. Waiting for a voice connection...')
                self.music_queue.insert(0, item)
                await asyncio.sleep(1.0)
                continue

            if item.get('audio_path'):
                audio_path = Path(item['audio_path'])
                title = item.get('title') or audio_path.stem
                if not audio_path.exists():
                    print(f"[DiscordBot] Saved audio file no longer exists: {audio_path}")
                    continue
            else:
                query = item.get('query')
                if not query:
                    continue
                result = await asyncio.to_thread(_download_youtube_audio_to_file, query)
                if not result:
                    print(f"[DiscordBot] Failed to download audio for query: {query}")
                    continue
                audio_path, title = result

            self.music_current = title
            self.music_current_path = audio_path
            self.music_started_at = datetime.datetime.utcnow()
            playback_completed = asyncio.Event()

            # Update bot presence to show current playing track
            try:
                await self.client.change_presence(
                    activity=discord.Activity(type=discord.ActivityType.listening, name=title)
                )
            except Exception:
                pass

            def _after_play(error):
                if error:
                    print(f"[DiscordBot] Voice playback error: {error}")
                self._loop.call_soon_threadsafe(playback_completed.set)

            try:
                if voice_client.is_playing() or voice_client.is_paused():
                    voice_client.stop()

                seek_offset = item.get('seek', 0.0)
                seek_options = f'-ss {seek_offset}' if seek_offset else ''
                try:
                    raw_source = _make_ffmpeg_opus_source(str(audio_path), extra_options=seek_options)
                except Exception:
                    raw_source = discord.FFmpegPCMAudio(str(audio_path), executable='ffmpeg', options=f'{seek_options} -vn -ac 2 -ar 48000'.strip())

                try:
                    voice_client.play(raw_source, after=_after_play)
                except Exception as e:
                    print(f"[DiscordBot] Playback start error: {e}")
                    playback_completed.set()
                    raise
                # Send a "Now playing" message to the requesting channel if available
                if notify_channel_id:
                    try:
                        chan = self.client.get_channel(int(notify_channel_id))
                        if chan is None:
                            chan = await self.client.fetch_channel(int(notify_channel_id))
                        if chan:
                            try:
                                await chan.send(f'Now playing: {title}', delete_after=_get_temporary_delete_seconds())
                            except Exception:
                                pass
                    except Exception:
                        pass
                await playback_completed.wait()
            finally:
                self.music_current = None
                self.music_current_path = None
                self.music_started_at = None
                try:
                    await self.client.change_presence(activity=discord.Game("Jarvis is listening"))
                except Exception:
                    pass
                try:
                    if audio_path.exists() and not self._tts_speaking:
                        audio_path.unlink()
                except Exception:
                    pass

        self.music_task = None

    async def pause_music(self) -> str:
        voice_client = self._get_any_connected_voice_client()
        if not voice_client or not voice_client.is_connected():
            return 'I am not connected to a voice channel.'
        if not voice_client.is_playing():
            return 'Nothing is playing right now.'
        try:
            voice_client.pause()
            return 'Music playback paused.'
        except Exception as e:
            return f'Could not pause playback: {e}'

    async def resume_music(self) -> str:
        voice_client = self._get_any_connected_voice_client()
        if not voice_client or not voice_client.is_connected():
            return 'I am not connected to a voice channel.'
        if not voice_client.is_paused():
            return 'Music is not paused.'
        try:
            voice_client.resume()
            return 'Music playback resumed.'
        except Exception as e:
            return f'Could not resume playback: {e}'

    async def stop_music(self) -> str:
        self.music_queue.clear()
        voice_client = self._get_any_connected_voice_client()
        if not voice_client or not voice_client.is_connected():
            return 'I am not connected to a voice channel.'
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
            self.music_current = None
            return 'Stopped playback and cleared the queue.'
        return 'Nothing is playing.'

    async def skip_music(self) -> str:
        voice_client = self._get_any_connected_voice_client()
        if not voice_client or not voice_client.is_connected():
            return 'I am not connected to a voice channel.'
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
            return 'Skipped the current track.'
        return 'Nothing is playing.'

    async def set_music_volume(self, volume: float) -> str:
        voice_client = self._get_any_connected_voice_client()
        if not voice_client or not voice_client.is_connected():
            return 'I am not connected to a voice channel.'
        if not hasattr(voice_client, 'source') or voice_client.source is None:
            return 'Volume control is not available for the current playback source.'

        if not isinstance(voice_client.source, discord.PCMVolumeTransformer):
            return 'Volume control is not supported for this source.'

        volume = max(0.0, min(volume, 2.0))
        voice_client.source.volume = volume
        return f'Set music volume to {int(volume * 100)}%.'

    async def get_music_queue_status(self) -> str:
        status_parts = []
        if self.music_current:
            status_parts.append(f'Now playing: {self.music_current}')
        if self.music_queue:
            status_parts.append('Upcoming queue:')
            status_parts.extend(f'{idx+1}. {item}' for idx, item in enumerate(self.music_queue[:10]))
        if not status_parts:
            return 'No music is currently queued or playing.'
        return '\n'.join(status_parts)

    async def _start_client(self):
        try:
            await self.client.start(self.token)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[DiscordBot] ❌ Client start error ({type(e).__name__}): {e}")
            traceback.print_exc()
        finally:
            self._is_ready = False
    def set_status_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        self._status_callback = callback

    def set_poll_image_picker_callback(self, callback: Optional[Callable[[], List[str]]]) -> None:
        self._poll_image_picker_callback = callback

    def _update_status(self, status: str) -> None:
        status = (status or "").strip().upper()
        self._status = status
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception:
                pass

    def _watch_bot_loop(self):
        while not self._watcher_stop.wait(1.0):
            if not self._auto_restart_enabled:
                continue
            if self.is_running and self._thread and self._thread.is_alive():
                continue
            backoff = min(self._restart_backoff, 60.0)
            print(f"[DiscordBot] 🔁 Bot stopped unexpectedly; restarting in {backoff:.1f}s...")
            self._update_status("RECONNECTING")
            waited = 0.0
            while waited < backoff and not self._watcher_stop.wait(0.5):
                waited += 0.5
            if self._watcher_stop.is_set():
                break
            try:
                self.ensure_running()
                self._restart_backoff = 1.0
                self._restart_attempts = 0
            except Exception as exc:
                self._restart_attempts += 1
                print(f"[DiscordBot] ❌ Auto-restart failed: {exc}")
                traceback.print_exc()
                self._restart_backoff = min(self._restart_backoff * 2.0, 60.0)
                time.sleep(1.0)

    def ensure_running(self, timeout: float = 20.0):
        with self._startup_lock:
            if self.is_running and self._thread and self._thread.is_alive():
                return

            self._intentional_stop = False
            self._auto_restart_enabled = True
            self._restart_backoff = 1.0
            self._restart_attempts = 0
            self._update_status("STARTING")
            self._ready_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="JarvisDiscordBot")
            try:
                self._thread.start()
            except Exception as exc:
                self._thread = None
                raise

            if not self._ready_event.wait(timeout):
                self._thread = None
                raise RuntimeError("Discord bot did not become ready in time")

            if not self.client or not getattr(self.client, "is_ready", lambda: False)():
                self._thread = None
                self.is_running = False
                raise RuntimeError("Discord bot did not become ready: login failed or client not ready")

            self.is_running = True
            if self._watcher_thread is None or not self._watcher_thread.is_alive():
                self._watcher_stop.clear()
                self._watcher_thread = threading.Thread(target=self._watch_bot_loop, daemon=True, name="JarvisDiscordWatcher")
                self._watcher_thread.start()
            return None

    def stop_bot(self, timeout: float = 10.0):
        """Stop the Discord bot cleanly.

        This method is defensive: it tolerates missing loop/client state and
        logs tracebacks for easier debugging when closing fails.
        """
        print("[DiscordBot] 🛑 Stopping bot...")
        self._intentional_stop = True
        self._auto_restart_enabled = False
        self._update_status("OFFLINE")
        self._watcher_stop.set()
        self._is_ready = False
        if self._watcher_thread:
            try:
                self._watcher_thread.join(timeout)
            except Exception:
                pass
            self._watcher_thread = None

        # If no client exists, ensure flags are cleared and return early.
        if not self.client:
            print("[DiscordBot] ✅ No client to close.")
            self.is_running = False
            self._thread = None
            self._loop = None
            self._update_status("OFFLINE")
            return

        # If the loop is running, schedule a coroutine to close the client.
        if self._loop and getattr(self._loop, "is_running", lambda: False)():
            print("[DiscordBot] 📴 Closing client and stopping loop...")
            try:
                future = asyncio.run_coroutine_threadsafe(self.client.close(), self._loop)
                try:
                    future.result(timeout=timeout)
                    print("[DiscordBot] ✅ Client closed.")
                except (asyncio.CancelledError, concurrent.futures.CancelledError):
                    # The close operation was cancelled because the loop or client
                    # is already shutting down. Treat this as a normal stop.
                    print("[DiscordBot] ℹ️ Client close was cancelled (already closing).")
                    pass
                except Exception as e:
                    print(f"[DiscordBot] ❌ Error closing Discord bot: {e}")
                    traceback.print_exc()
            except Exception as e:
                print(f"[DiscordBot] ❌ Error scheduling Discord bot close: {e}")
                traceback.print_exc()
            finally:
                try:
                    if self._loop and self._loop.is_running():
                        print("[DiscordBot] 🛑 Stopping event loop...")
                        self._loop.call_soon_threadsafe(self._loop.stop)
                except Exception:
                    pass
                if self._thread:
                    try:
                        print("[DiscordBot] ⏳ Waiting for bot thread to exit...")
                        self._thread.join(timeout)
                        print("[DiscordBot] ✅ Bot thread exited.")
                    except Exception:
                        pass
        else:
            print("[DiscordBot] ⚠️ Loop not running, attempting synchronous close...")
            # Loop is not running — attempt best-effort synchronous cleanup.
            try:
                if hasattr(self.client, "is_closed") and not self.client.is_closed():
                    # try close synchronously in a new temporary loop if possible
                    try:
                        asyncio.run(self.client.close())
                        print("[DiscordBot] ✅ Client closed synchronously.")
                    except Exception:
                        # last resort: ignore and log
                        print("[DiscordBot] ⚠️ Could not synchronously close Discord client.")
                        traceback.print_exc()
            except Exception:
                traceback.print_exc()

        # Final cleanup
        try:
            self.is_running = False
            self._thread = None
            self.client = None
            self._loop = None
            self._update_status("OFFLINE")  # Notify UI that bot is offline
            print("[DiscordBot] ✅ Bot stopped.")
        except Exception:
            pass

    def restart_bot(self, timeout: float = 20.0):
        self.stop_bot(timeout=timeout)
        self.ensure_running(timeout=timeout)

    def execute_in_loop(self, coro, timeout: float = 60.0):
        if not self._loop:
            raise RuntimeError("Discord bot event loop is not available.")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError as e:
            raise RuntimeError(f"Discord bot event loop sync timed out after {timeout}s") from e

    def sync_commands(self, guild_id: int | None = None, timeout: float = 60.0):
        if not self._loop:
            raise RuntimeError("Discord bot event loop is not available.")
        if not self.client:
            raise RuntimeError("Discord bot client is not available for command sync.")
        if not self._is_ready and not getattr(self.client, "is_ready", lambda: False)():
            raise RuntimeError("Discord bot is not ready for command sync.")

        async def _sync():
            try:
                if guild_id is None:
                    await self.tree.sync()
                    print("[DiscordBot] ✅ Discord slash commands synced (global).")
                    for guild in self.client.guilds:
                        await self.tree.sync(guild=guild)
                        print(f"[DiscordBot] ✅ Synced commands for guild {guild.id}")
                else:
                    guild = self.client.get_guild(guild_id) or discord.Object(id=guild_id)
                    await self.tree.sync(guild=guild)
                    print(f"[DiscordBot] ✅ Synced commands for guild {guild_id}")
                print(f"[DiscordBot] Available commands after sync: {[cmd.name for cmd in self.tree.walk_commands()]}")
            except Exception as e:
                print(f"[DiscordBot] ❌ Manual slash command sync failed: {e}")
                raise

        return self.execute_in_loop(_sync(), timeout)

    async def get_recent_messages(self, channel_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages from a specific channel"""
        if channel_id not in self.last_messages:
            return []

        return self.last_messages[channel_id][-limit:]

    async def send_message(self, channel_id: str, content: str) -> bool:
        """Send a message to a specific channel"""
        try:
            channel = self.client.get_channel(int(channel_id))
            if channel:
                await channel.send(content)
                return True
            return False
        except Exception as e:
            print(f"Error sending Discord message: {e}")
            return False

    async def get_channels(self) -> List[Dict]:
        """Get all accessible channels"""
        channels = []
        for guild in self.client.guilds:
            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    channels.append({
                        'id': str(channel.id),
                        'name': channel.name,
                        'guild': guild.name
                    })
        return channels

    async def get_voice_channels(self, guild_id: str = "") -> List[Dict]:
        """Get all accessible voice channels"""
        voice_channels = []
        for guild in self.client.guilds:
            if guild_id and str(guild.id) != str(guild_id):
                continue
            for channel in guild.voice_channels:
                voice_channels.append({
                    'guild': guild.name,
                    'guild_id': str(guild.id),
                    'name': channel.name,
                    'id': str(channel.id),
                })
        return voice_channels

    async def _ensure_voice_connection(self, voice_channel: discord.VoiceChannel) -> bool:
        if not isinstance(voice_channel, discord.VoiceChannel):
            return False

        if not _DISCORD_VOICE_AVAILABLE:
            missing = []
            if not _DISCORD_NACL_AVAILABLE:
                missing.append("PyNaCl")
            if not _DISCORD_DAVEY_AVAILABLE:
                missing.append("davey")
            print(
                f"[DiscordBot] ❌ Missing voice dependencies: {', '.join(missing)}"
            )
            return False

        existing = self._get_connected_voice_client_for_channel(voice_channel)
        if existing:
            self._register_discord_voice_receive(existing)
            return True

        # Disconnect any other voice connection in this guild before joining the target channel
        for vc in self.client.voice_clients:
            if vc.is_connected() and vc.guild.id == voice_channel.guild.id and vc.channel.id != voice_channel.id:
                self._unregister_discord_voice_receive(vc)
                await vc.disconnect()

        try:
            voice_client = await voice_channel.connect()
            if voice_client is not None:
                self._register_discord_voice_receive(voice_client)
            return True
        except Exception as e:
            print(f"[DiscordBot] ❌ Voice connect error: {e}")
            return False

    async def _try_speak_in_current_voice(self, text: str) -> None:
        if not _PYTTSX3_AVAILABLE:
            return

        voice_client = self._get_any_connected_voice_client()
        if voice_client is None or not voice_client.is_connected():
            return

        try:
            await _speak_in_voice_channel(text)
        except Exception as e:
            print(f"[DiscordBot] ❌ Voice speak error: {e}")

# Global bot instance
_bot_instance = None

def get_discord_bot() -> DiscordBot:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = DiscordBot()
    return _bot_instance

async def check_discord_messages(channel_id: str, limit: int = 10) -> str:
    """Check recent messages in a Discord channel"""
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    try:
        messages = await bot.get_recent_messages(channel_id, limit)
        if not messages:
            return f"No recent messages found in channel {channel_id}"

        result = f"Recent messages in channel {channel_id}:\n\n"
        for msg in messages:
            result += f"**{msg['author']}** ({msg['timestamp'][:19]}): {msg['content']}\n"

        return result
    except Exception as e:
        return f"Error checking Discord messages: {str(e)}"

async def send_discord_message(channel_id: str, message: str) -> str:
    """Send a message to a Discord channel"""
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    try:
        success = bot.execute_in_loop(bot.send_message(channel_id, message))
        if success:
            return f"Message sent successfully to channel {channel_id}"
        else:
            return f"Failed to send message to channel {channel_id}"
    except Exception as e:
        return f"Error sending Discord message: {str(e)}"

async def _list_discord_channels() -> str:
    """List all accessible Discord channels"""
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    try:
        channels = bot.execute_in_loop(bot.get_channels())
        if not channels:
            return "No channels found or bot not connected to any servers"

        result = "Available Discord channels:\n\n"
        for channel in channels:
            result += f"**{channel['guild']}** - #{channel['name']} (ID: {channel['id']})\n"

        return result
    except Exception as e:
        return f"Error listing Discord channels: {str(e)}"


def list_discord_channels() -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_list_discord_channels())


async def _list_discord_voice_channels(guild_id: str = "") -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    try:
        if not bot.client.guilds:
            return "Bot is not connected to any Discord servers. Verify the bot token and that it has been invited to the target guild."

        voice_channels = bot.execute_in_loop(bot.get_voice_channels(guild_id))

        if not voice_channels:
            return "No voice channels found for the requested guild, or the bot is not in that server."

        result = "Available Discord voice channels:\n\n"
        for channel in voice_channels:
            result += f"**{channel['guild']}** (ID: {channel['guild_id']}) - {channel['name']} (ID: {channel['id']})\n"

        return result
    except Exception as e:
        return f"Error listing Discord voice channels: {str(e)}"


def list_voice_channels(guild_id: str = "") -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_list_discord_voice_channels(guild_id))


async def _join_discord_channel(channel_id: str, join_message: str = "Jarvis has joined the channel.") -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    try:
        channel = await bot._fetch_channel_by_id(channel_id)
        if channel is None:
            guild = bot.client.get_guild(int(channel_id))
            if guild:
                for text_channel in guild.text_channels:
                    if text_channel.permissions_for(guild.me).send_messages:
                        await asyncio.wait_for(text_channel.send(join_message), timeout=15.0)
                        return (
                            f"Joined guild {guild.name} and announced in text channel {text_channel.name} "
                            f"(ID: {text_channel.id})."
                        )
                return (
                    f"Found guild {guild.name} but could not access any text channels. "
                    f"Use a specific text channel ID or ensure Jarvis has send permissions."
                )
            return f"Could not find a Discord channel with ID {channel_id}. Verify the ID is a text channel or use join_discord_voice_channel for voice channels."

        if isinstance(channel, discord.VoiceChannel):
            join_result = await _join_discord_voice_channel(voice_channel_id=str(channel.id))
            return f"The provided ID is a voice channel. {join_result}"

        if not isinstance(channel, discord.TextChannel):
            return f"Channel ID {channel_id} is not a text channel. Use a text channel ID or join_discord_voice_channel for voice."

        await asyncio.wait_for(channel.send(join_message), timeout=15.0)
        return f"Joined and announced in Discord channel {channel.name} (ID: {channel_id})."
    except asyncio.TimeoutError:
        return f"Error: sending to Discord text channel {channel_id} timed out. The bot may not have permissions or the server may be unreachable."
    except Exception as e:
        return f"Error joining Discord text channel: {str(e)}"


def join_discord_channel(channel_id: str, join_message: str = "Jarvis has joined the channel.") -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_join_discord_channel(channel_id, join_message))


async def _join_discord_voice_channel(
    voice_channel_id: str = "",
    member_id: str = "",
    member_name: str = "",
    channel_name: str = "",
    guild_id: str = ""
) -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    channel = None
    if voice_channel_id:
        channel = await bot._fetch_channel_by_id(voice_channel_id)
    elif member_id or member_name:
        for guild in bot.client.guilds:
            if guild_id and str(guild.id) != str(guild_id):
                continue
            member = None
            if member_id:
                member = guild.get_member(int(member_id))
            elif member_name:
                for m in guild.members:
                    if m.display_name.lower() == member_name.lower() or m.name.lower() == member_name.lower():
                        member = m
                        break
            if member and member.voice and member.voice.channel:
                channel = member.voice.channel
                break
    else:
        for guild in bot.client.guilds:
            if guild_id and str(guild.id) != str(guild_id):
                continue
            # First try exact voice channel name match
            for voice_channel in guild.voice_channels:
                if voice_channel.name.lower() == channel_name.lower():
                    channel = voice_channel
                    break
            if channel:
                break
            # Then try matching guild name to pick a voice channel inside that guild
            if guild.name.lower() == channel_name.lower() and guild.voice_channels:
                channel = guild.voice_channels[0]
                break

    # If a guild ID is present and a channel name was not found, use the guild's first voice channel
    if channel is None and guild_id:
        guild = bot.client.get_guild(int(guild_id))
        if guild and guild.voice_channels:
            channel = guild.voice_channels[0]

    if not _DISCORD_VOICE_AVAILABLE:
        missing = []
        if not _DISCORD_NACL_AVAILABLE:
            missing.append("PyNaCl")
        if not _DISCORD_DAVEY_AVAILABLE:
            missing.append("davey")
        return (
            "Discord voice support requires the following packages: "
            f"{', '.join(missing)}. Install them with `pip install {' '.join(name.lower() for name in missing)}` "
            "and restart Jarvis."
        )

    if channel is None or not isinstance(channel, discord.VoiceChannel):
        return "Could not find the requested Discord voice channel. Provide a valid voice_channel_id, member_id, member_name, or channel_name."

    try:
        existing = bot._get_connected_voice_client_for_channel(channel)
        if existing and existing.is_connected():
            return f"Already connected to voice channel {channel.name} in {channel.guild.name}."

        connected = await bot._ensure_voice_connection(channel)
        if connected:
            return f"Joined Discord voice channel {channel.name} in {channel.guild.name}."
        return f"I couldn't join the requested voice channel. Please check permissions."
    except Exception as e:
        return f"Error joining Discord voice channel: {str(e)}"


def join_discord_voice_channel(
    voice_channel_id: str = "",
    member_id: str = "",
    member_name: str = "",
    channel_name: str = "",
    guild_id: str = ""
) -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_join_discord_voice_channel(voice_channel_id, member_id, member_name, channel_name, guild_id))


async def _speak_in_voice_channel(message: str) -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    voice_client = bot.client.voice_clients[0] if bot.client.voice_clients else None
    if voice_client is None or not voice_client.is_connected():
        return "Jarvis is not currently connected to a Discord voice channel."

    if not _DISCORD_VOICE_AVAILABLE:
        missing = []
        if not _DISCORD_NACL_AVAILABLE:
            missing.append("PyNaCl")
        if not _DISCORD_DAVEY_AVAILABLE:
            missing.append("davey")
        return (
            "Discord voice support requires the following packages: "
            f"{', '.join(missing)}. Install them with `pip install {' '.join(name.lower() for name in missing)}` "
            "and restart Jarvis."
        )

    try:
        # Prefer high-quality Gemini/ElevenLabs/Coqui TTS if available; fallback to pyttsx3.
        temp_file = None
        try:
            temp_file = await asyncio.to_thread(_synthesize_high_quality_tts, message)
        except Exception:
            temp_file = None

        if temp_file is None and _PYTTSX3_AVAILABLE:
            temp_file = Path(tempfile.gettempdir()) / f"jarvis_discord_tts_{int(datetime.datetime.utcnow().timestamp())}.wav"
            engine = pyttsx3.init()
            engine.save_to_file(message, str(temp_file))
            engine.runAndWait()

        if temp_file is None:
            if not _PYTTSX3_AVAILABLE:
                return "TTS failed: no available TTS engine and pyttsx3 is not installed."
            return "TTS failed: no available TTS engine."

        try:
            was_playing_music = voice_client.is_playing() and bot.music_current_path is not None
            if was_playing_music and bot.music_current_path and bot.music_current:
                # Preserve current playback position and resume from the same place after TTS.
                seek_offset = 0.0
                if bot.music_started_at:
                    seek_offset = (datetime.datetime.utcnow() - bot.music_started_at).total_seconds()
                if bot.music_current_path.exists():
                    bot._tts_speaking = True
                    bot.music_queue.insert(0, {
                        'audio_path': str(bot.music_current_path),
                        'title': bot.music_current,
                        'notify_channel_id': None,
                        'seek': round(seek_offset, 2)
                    })
            if voice_client.is_playing():
                voice_client.stop()

            voice_effect = _get_voice_effect_for_guild(str(voice_client.guild.id)) if voice_client.guild else 'none'
            extra_options = VOICE_EFFECTS.get(voice_effect, '')
            try:
                raw_source = _make_ffmpeg_opus_source(str(temp_file), extra_options=extra_options)
            except Exception:
                raw_source = discord.FFmpegPCMAudio(
                    str(temp_file), executable='ffmpeg', options=f'-vn -ac 2 -ar 48000 {extra_options}'.strip()
                )

            try:
                voice_client.play(raw_source)
            except Exception as e:
                print(f"[DiscordBot] Voice playback error: {e}")
                raise
            while voice_client.is_playing():
                await asyncio.sleep(0.1)
            try:
                os.remove(temp_file)
            except Exception:
                pass
        finally:
            bot._tts_speaking = False

        return f"Spoke in voice channel {voice_client.channel.name}."
    except Exception as e:
        error_message = str(e).lower()
        if "davey" in error_message:
            return (
                "Discord voice playback requires the davey library. Install it with `pip install davey` "
                "and restart Jarvis."
            )
        if "pynacl" in error_message or "nacl" in error_message:
            return (
                "Discord voice playback requires PyNaCl. Install it with `pip install pynacl` "
                "and restart Jarvis."
            )
        return f"Error speaking in Discord voice channel: {str(e)}"


def speak_in_voice_channel(message: str) -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_speak_in_voice_channel(message))


def discord_play_music(query: str, channel_id: str = "") -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    if channel_id:
        try:
            channel = bot.execute_in_loop(bot._fetch_channel_by_id(channel_id))
            if isinstance(channel, discord.VoiceChannel):
                connected = bot.execute_in_loop(bot._ensure_voice_connection(channel))
                if not connected:
                    return "I couldn't join the requested voice channel. Please check permissions."
        except Exception:
            pass
    return bot.execute_in_loop(_play_music_in_voice_channel(query))


async def _discord_voice_receive_support() -> str:
    if not _DISCORD_VOICE_AVAILABLE:
        missing = []
        if not _DISCORD_NACL_AVAILABLE:
            missing.append("PyNaCl")
        if not _DISCORD_DAVEY_AVAILABLE:
            missing.append("davey")
        return (
            "Discord voice receive requires the following packages: "
            f"{', '.join(missing)}. Install them with `pip install {' '.join(name.lower() for name in missing)}` "
            "and restart Jarvis."
        )

    if not _is_ffmpeg_available():
        return (
            "Discord voice receive is available, but speech transcription requires ffmpeg. "
            "Install ffmpeg and restart Jarvis to enable voice command processing."
        )

    return (
        "Discord voice receive is available. Jarvis can now listen to Discord voice channel audio, "
        "attempt speech transcription using OpenAI, and respond with voice replies in the same channel. "
        "A valid OpenAI API key in config/api_keys.json or OPENAI_API_KEY is required for transcription."
    )


def discord_voice_receive_support() -> str:
    return asyncio.run(_discord_voice_receive_support())


def join_my_discord_voice_channel(
    voice_channel_id: str = "",
    member_id: str = "",
    member_name: str = "",
    channel_name: str = "",
    guild_id: str = ""
) -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_join_discord_voice_channel(
        voice_channel_id=voice_channel_id,
        member_id=member_id,
        member_name=member_name,
        channel_name=channel_name,
        guild_id=guild_id
    ))


async def _leave_discord_voice_channel(guild_id: str = "") -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    voice_client = None
    if guild_id:
        for vc in bot.client.voice_clients:
            if str(vc.guild.id) == str(guild_id):
                voice_client = vc
                break
    else:
        voice_client = bot.client.voice_clients[0] if bot.client.voice_clients else None

    if voice_client is None or not voice_client.is_connected():
        return "Bot is not connected to any Discord voice channel."

    try:
        bot._unregister_discord_voice_receive(voice_client)
        await voice_client.disconnect()
        return f"Left voice channel {voice_client.channel.name} in {voice_client.guild.name}."
    except Exception as e:
        return f"Error leaving Discord voice channel: {str(e)}"


def leave_discord_voice_channel(guild_id: str = "") -> str:
    bot = get_discord_bot()
    if not bot.is_running:
        bot.ensure_running()
    return bot.execute_in_loop(_leave_discord_voice_channel(guild_id))


async def _filter_messages_by_timeframe(messages: List[Dict], timeframe: str) -> List[Dict]:
    now = datetime.datetime.now(datetime.timezone.utc)
    match = re.match(r"^(\d+)([hd])$", timeframe.strip().lower())
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        delta = datetime.timedelta(hours=amount) if unit == "h" else datetime.timedelta(days=amount)
    else:
        delta = datetime.timedelta(hours=24)

    cutoff = now - delta
    results = []
    for entry in messages:
        try:
            ts = datetime.datetime.fromisoformat(entry['timestamp'])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            if ts >= cutoff:
                results.append(entry)
        except Exception:
            continue
    return results

async def check_discord_engagement(
    action: str,
    timeframe: str = "24h",
    channel_id: Optional[str] = None,
    include_reactions: bool = True,
    include_replies: bool = True,
    sort_by: str = "recent"
) -> str:
    bot = get_discord_bot()

    if not bot.is_running:
        bot.ensure_running()

    messages = []
    for cid, entries in bot.last_messages.items():
        if channel_id and cid != channel_id:
            continue
        filtered = await _filter_messages_by_timeframe(entries, timeframe)
        messages.extend(filtered)

    if not messages:
        return "No Discord activity found for the requested timeframe."

    mentions = [msg for msg in messages if msg.get('mentions')]
    reacted = [msg for msg in messages if include_reactions and msg.get('reaction_count', 0) > 0]
    replies = [msg for msg in messages if include_replies and msg.get('is_reply')]

    if action == "check_mentions" or action == "track_mentions":
        if not mentions:
            return "No mentions were detected in the selected timeframe."
        output = "Recent mentions:\n\n"
        for msg in mentions[-10:]:
            output += f"{msg['timestamp'][:19]} [{msg['channel']}] {msg['author']}: {msg['content']}\n"
        return output

    if action == "unread_count":
        channel_counts = {}
        for msg in messages:
            channel_counts[msg['channel']] = channel_counts.get(msg['channel'], 0) + 1
        output = "Discord unread activity by channel:\n\n"
        for channel, count in channel_counts.items():
            output += f"{channel}: {count} new messages\n"
        return output

    if action == "get_channel_activity":
        if not channel_id:
            return "Channel ID is required for get_channel_activity."
        output = f"Recent activity for channel {channel_id}:\n\n"
        for msg in sorted(messages, key=lambda m: m['timestamp']):
            output += f"{msg['timestamp'][:19]} {msg['author']}: {msg['content']}\n"
        return output

    # Default engagement summary / activity report
    channel_counts = {}
    author_counts = {}
    for msg in messages:
        channel_counts[msg['channel']] = channel_counts.get(msg['channel'], 0) + 1
        author_counts[msg['author']] = author_counts.get(msg['author'], 0) + 1

    top_channels = sorted(channel_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_authors = sorted(author_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]

    output = [
        f"Discord engagement summary for the last {timeframe}:",
        f"Total messages: {len(messages)}",
        f"Mentions found: {len(mentions)}",
        f"Replied messages: {len(replies)}",
        f"Messages with reactions: {len(reacted)}",
        "Top channels:",
    ]
    for channel, count in top_channels:
        output.append(f" - {channel}: {count} messages")
    output.append("Top active authors:")
    for author, count in top_authors:
        output.append(f" - {author}: {count} messages")

    return "\n".join(output)

# Synchronous wrappers for the tool system

def _safe_sync_run(coro):
    try:
        asyncio.get_running_loop()
        loop_running = True
    except RuntimeError:
        loop_running = False

    if loop_running:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result(timeout=30)

    return asyncio.run(coro)


def check_messages(channel_id: str, limit: int = 10) -> str:
    """Synchronous wrapper for checking Discord messages"""
    try:
        return _safe_sync_run(check_discord_messages(channel_id, limit))
    except Exception as e:
        return f"Error in check_messages: {str(e)}"


def send_message(channel_id: str, message: str) -> str:
    """Synchronous wrapper for sending Discord messages"""
    try:
        return _safe_sync_run(send_discord_message(channel_id, message))
    except Exception as e:
        return f"Error in send_message: {str(e)}"


def list_channels() -> str:
    """Synchronous wrapper for listing Discord channels"""
    try:
        return _safe_sync_run(_list_discord_channels())
    except Exception as e:
        return f"Error in list_channels: {str(e)}"


def check_engagement(
    action: str,
    timeframe: str = "24h",
    channel_id: Optional[str] = None,
    include_reactions: bool = True,
    include_replies: bool = True,
    sort_by: str = "recent"
) -> str:
    """Synchronous wrapper for Discord engagement and mention monitoring"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, check_discord_engagement(
                    action=action,
                    timeframe=timeframe,
                    channel_id=channel_id,
                    include_reactions=include_reactions,
                    include_replies=include_replies,
                    sort_by=sort_by,
                ))
                return future.result(timeout=30)
        else:
            return asyncio.run(check_discord_engagement(
                action=action,
                timeframe=timeframe,
                channel_id=channel_id,
                include_reactions=include_reactions,
                include_replies=include_replies,
                sort_by=sort_by,
            ))
    except Exception as e:
        return f"Error in check_engagement: {str(e)}"
