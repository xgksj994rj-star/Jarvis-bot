import sqlite3
import discord
from discord import app_commands
from typing import Optional
from actions import settings as settings_mod
import datetime
import asyncio
import random

DB_PATH = "data/jarvis.db"

QUEST_DEFINITIONS = {
    "daily_chatter": {
        "title": "Daily Chatter",
        "description": "Send 10 messages today to earn bonus XP.",
        "target": 10,
        "reward_xp": 50,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "daily_xp_boost": {
        "title": "XP Booster",
        "description": "Earn 100 XP today to get a bonus reward.",
        "target": 100,
        "reward_xp": 100,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "daily_chat_rush": {
        "title": "Chat Rush",
        "description": "Send 15 messages today to stack bonus XP.",
        "target": 15,
        "reward_xp": 60,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "daily_xp_surge": {
        "title": "XP Surge",
        "description": "Earn 150 XP today to unlock a bigger reward.",
        "target": 150,
        "reward_xp": 120,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "daily_level_push": {
        "title": "Level Push",
        "description": "Reach level 4 today to complete this quest.",
        "target": 4,
        "reward_xp": 90,
        "repeat": "daily",
        "progress_mode": "level",
    },
    "daily_level_up": {
        "title": "Level Up",
        "description": "Reach level 5 today to earn a fresh bonus.",
        "target": 5,
        "reward_xp": 110,
        "repeat": "daily",
        "progress_mode": "level",
    },
    "daily_streak": {
        "title": "Message Streak",
        "description": "Send 20 messages today to keep the streak alive.",
        "target": 20,
        "reward_xp": 70,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "daily_hero": {
        "title": "Daily Hero",
        "description": "Earn 200 XP today to become the hero of the server.",
        "target": 200,
        "reward_xp": 140,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "daily_burst": {
        "title": "XP Burst",
        "description": "Earn 250 XP today to trigger a power-up.",
        "target": 250,
        "reward_xp": 150,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "daily_blitz": {
        "title": "Chat Blitz",
        "description": "Send 25 messages today to keep the momentum rolling.",
        "target": 25,
        "reward_xp": 80,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "daily_legend": {
        "title": "Server Legend",
        "description": "Earn 300 XP today to become a legend of the community.",
        "target": 300,
        "reward_xp": 180,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "daily_chat_ninja": {
        "title": "Chat Ninja",
        "description": "Send 30 messages today to prove your speed.",
        "target": 30,
        "reward_xp": 100,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "daily_rising_star": {
        "title": "Rising Star",
        "description": "Reach level 6 today to climb the leaderboard.",
        "target": 6,
        "reward_xp": 130,
        "repeat": "daily",
        "progress_mode": "level",
    },
    "holiday_sparkle": {
        "title": "Holiday Sparkle",
        "description": "Earn 220 XP during the holiday season for a festive bonus.",
        "target": 220,
        "reward_xp": 170,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "holiday_cookie": {
        "title": "Cookie Quest",
        "description": "Send 18 festive messages to spread holiday cheer.",
        "target": 18,
        "reward_xp": 90,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "spooky_spree": {
        "title": "Spooky Spree",
        "description": "Send 12 spooky messages to keep the Halloween energy alive.",
        "target": 12,
        "reward_xp": 110,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "harvest_hustle": {
        "title": "Harvest Hustle",
        "description": "Earn 180 XP for a cozy autumn reward.",
        "target": 180,
        "reward_xp": 120,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "winter_wonder": {
        "title": "Winter Wonder",
        "description": "Send 16 winter-themed messages to warm up the server.",
        "target": 16,
        "reward_xp": 95,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "new_year_resolve": {
        "title": "New Year Resolve",
        "description": "Earn 210 XP to kick off the year in style.",
        "target": 210,
        "reward_xp": 160,
        "repeat": "daily",
        "progress_mode": "xp",
    },
    "valentine_vibes": {
        "title": "Valentine Vibes",
        "description": "Send 14 sweet messages to spread some love.",
        "target": 14,
        "reward_xp": 85,
        "repeat": "daily",
        "progress_mode": "message",
    },
    "level_3_milestone": {
        "title": "Rising Star",
        "description": "Reach level 3 to unlock this reward.",
        "target": 3,
        "reward_xp": 75,
        "repeat": "once",
    },
}

SEASONAL_QUEST_KEYS = {
    "holiday_sparkle",
    "holiday_cookie",
    "spooky_spree",
    "harvest_hustle",
    "winter_wonder",
    "new_year_resolve",
    "valentine_vibes",
}

ACHIEVEMENT_DEFINITIONS = {
    "first_xp": {
        "title": "First XP",
        "description": "Earn your first experience points.",
    },
    "level_5": {
        "title": "Level 5 Achiever",
        "description": "Reach level 5.",
    },
    "level_10": {
        "title": "Level 10 Legend",
        "description": "Reach level 10.",
    },
}


def _ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS xp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            xp INTEGER DEFAULT 0,
            last_message DATETIME,
            last_message_hash TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS xp_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            day TEXT,
            xp INTEGER DEFAULT 0,
            UNIQUE(guild_id, user_id, day)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS level_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            level INTEGER,
            role_id INTEGER,
            UNIQUE(guild_id, level)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS quest_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            quest_key TEXT,
            day TEXT,
            progress INTEGER DEFAULT 0,
            completed_at DATETIME,
            claimed_at DATETIME,
            UNIQUE(guild_id, user_id, quest_key, day)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS achievements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            user_id INTEGER,
            achievement_key TEXT,
            unlocked_at DATETIME,
            UNIQUE(guild_id, user_id, achievement_key)
        )
        """
    )
    conn.commit()
    conn.close()


def _get_today():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> datetime.date:
    first = datetime.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + 7 * (occurrence - 1))


def _holiday_windows(now: Optional[datetime.datetime] = None) -> list[str]:
    current = now or datetime.datetime.now(datetime.timezone.utc)
    current_date = current.date()
    year = current.year
    seasonal = []

    halloween_start = datetime.date(year, 10, 24)
    halloween_end = datetime.date(year, 10, 31)
    if halloween_start <= current_date <= halloween_end:
        seasonal += ["spooky_spree", "harvest_hustle"]

    thanksgiving = _nth_weekday(year, 11, 3, 4)
    thanksgiving_window_start = thanksgiving - datetime.timedelta(days=7)
    thanksgiving_window_end = thanksgiving
    if thanksgiving_window_start <= current_date <= thanksgiving_window_end:
        seasonal += ["harvest_hustle"]

    christmas_start = datetime.date(year, 12, 1)
    christmas_end = datetime.date(year, 12, 31)
    if christmas_start <= current_date <= christmas_end:
        seasonal += ["holiday_sparkle", "holiday_cookie", "winter_wonder"]

    if current_date.month == 1 and current_date.day <= 5:
        new_year_start = datetime.date(year - 1, 12, 28)
        new_year_end = datetime.date(year, 1, 5)
    else:
        new_year_start = datetime.date(year, 12, 28)
        new_year_end = datetime.date(year + 1, 1, 5)
    if new_year_start <= current_date <= new_year_end:
        seasonal += ["new_year_resolve"]

    valentine_start = datetime.date(year, 2, 7)
    valentine_end = datetime.date(year, 2, 14)
    if valentine_start <= current_date <= valentine_end:
        seasonal += ["valentine_vibes"]

    return list(dict.fromkeys(seasonal))


def _daily_quest_pool() -> list[str]:
    seasonal = _holiday_windows()
    base = [key for key, quest in QUEST_DEFINITIONS.items() if quest.get("repeat") == "daily" and key not in SEASONAL_QUEST_KEYS]
    return list(dict.fromkeys(base + seasonal))


def _chunk_text(text: str, max_chars: int = 1800) -> list[str]:
    chunks = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) > max_chars:
            if current:
                chunks.append(current)
                current = ""
                candidate = paragraph
            if len(candidate) > max_chars:
                words = candidate.split()
                current = words[0]
                for word in words[1:]:
                    next_candidate = f"{current} {word}"
                    if len(next_candidate) > max_chars:
                        chunks.append(current)
                        current = word
                    else:
                        current = next_candidate
                if current:
                    chunks.append(current)
                continue
        current = candidate
    if current:
        chunks.append(current)
    return chunks or [text[:max_chars]]


def _roll_daily_quests(guild_id: int, user_id: int, day: str) -> list[str]:
    pool = _daily_quest_pool()
    if not pool:
        return []
    rng = random.Random(f"{guild_id}:{user_id}:{day}")
    return rng.sample(pool, k=min(3, len(pool)))


class GamificationCog:
    def __init__(self, tree: app_commands.CommandTree, client: discord.Client):
        _ensure_db()
        self.tree = tree
        self.client = client
        self.COOLDOWN_SECONDS = 60
        self._register_commands()

    def add_xp(self, guild_id: int, user_id: int, amount: int = 10, channel: Optional[discord.abc.Messageable] = None):
        try:
            enabled = settings_mod.get_setting(guild_id, "gamification_enabled")
            if enabled is not None and enabled == 0:
                return
        except Exception:
            pass

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT xp, last_message FROM xp WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        row = cur.fetchone()

        try:
            cooldown_override = settings_mod.get_setting(guild_id, "cooldown_seconds")
            cd_seconds = int(cooldown_override) if cooldown_override is not None else self.COOLDOWN_SECONDS
        except Exception:
            cd_seconds = self.COOLDOWN_SECONDS

        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        if row and row[1]:
            try:
                last_ts = int(row[1])
                if now_ts - last_ts < cd_seconds:
                    conn.close()
                    return
            except Exception:
                pass

        if row:
            prev_xp = row[0]
            cur.execute(
                "UPDATE xp SET xp = xp + ?, last_message = ? WHERE guild_id=? AND user_id=?",
                (amount, now_ts, guild_id, user_id),
            )
        else:
            prev_xp = 0
            cur.execute(
                "INSERT INTO xp (guild_id, user_id, xp, last_message) VALUES (?, ?, ?, ?)",
                (guild_id, user_id, amount, now_ts),
            )
        conn.commit()

        cur.execute("SELECT xp FROM xp WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        new_xp = cur.fetchone()[0]

        today = _get_today()
        try:
            cur.execute(
                "INSERT INTO xp_daily (guild_id, user_id, day, xp) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id, day) DO UPDATE SET xp = xp + ?",
                (guild_id, user_id, today, amount, amount),
            )
            conn.commit()
            cap = settings_mod.get_setting(guild_id, "daily_xp_cap")
            if cap is not None:
                cur.execute("SELECT xp FROM xp_daily WHERE guild_id=? AND user_id=? AND day=?", (guild_id, user_id, today))
                dxp = cur.fetchone()[0]
                if dxp > int(cap):
                    cur.execute("UPDATE xp SET xp = xp - ? WHERE guild_id=? AND user_id=?", (amount, guild_id, user_id))
                    conn.commit()
                    conn.close()
                    return
        except Exception:
            pass

        prev_level = int(prev_xp ** 0.5)
        new_level = int(new_xp ** 0.5)
        if new_level > prev_level:
            try:
                self._assign_level_roles(guild_id, user_id, prev_level, new_level)
            except Exception:
                pass

        conn.close()
        self._process_achievements(guild_id, user_id, prev_xp, new_xp, channel=channel)
        self._update_quests(guild_id, user_id, amount, channel=channel)

    def _process_achievements(self, guild_id: int, user_id: int, prev_xp: int, new_xp: int, channel: Optional[discord.abc.Messageable] = None):
        if prev_xp == 0 and new_xp > 0:
            if self._award_achievement(guild_id, user_id, "first_xp"):
                self._queue_notification(channel, f"🎉 {self._format_achievement('first_xp')} unlocked by <@{user_id}>!")

        prev_level = int(prev_xp ** 0.5)
        new_level = int(new_xp ** 0.5)
        if prev_level < 5 <= new_level:
            if self._award_achievement(guild_id, user_id, "level_5"):
                self._queue_notification(channel, f"🎉 {self._format_achievement('level_5')} unlocked by <@{user_id}>!")
        if prev_level < 10 <= new_level:
            if self._award_achievement(guild_id, user_id, "level_10"):
                self._queue_notification(channel, f"🎉 {self._format_achievement('level_10')} unlocked by <@{user_id}>!")

    def _update_quests(self, guild_id: int, user_id: int, amount: int, channel: Optional[discord.abc.Messageable] = None):
        today = _get_today()
        self._ensure_daily_quest_set(guild_id, user_id, today)
        for quest_key in _roll_daily_quests(guild_id, user_id, today):
            quest = QUEST_DEFINITIONS.get(quest_key, {})
            mode = quest.get("progress_mode", "xp")
            if mode == "message":
                delta = 1
            elif mode == "level":
                self._update_quest_progress(guild_id, user_id, quest_key, 0, today, check_level=True, channel=channel)
                continue
            else:
                delta = amount
            self._update_quest_progress(guild_id, user_id, quest_key, delta, today, channel=channel)

    def _ensure_daily_quest_set(self, guild_id: int, user_id: int, day: str):
        quest_keys = _roll_daily_quests(guild_id, user_id, day)
        if not quest_keys:
            return
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for quest_key in quest_keys:
            cur.execute(
                "INSERT OR IGNORE INTO quest_progress (guild_id, user_id, quest_key, day, progress, completed_at) VALUES (?, ?, ?, ?, 0, NULL)",
                (guild_id, user_id, quest_key, day),
            )
        conn.commit()
        conn.close()

    def _update_quest_progress(
        self,
        guild_id: int,
        user_id: int,
        quest_key: str,
        delta: int,
        day: str,
        check_level: bool = False,
        channel: Optional[discord.abc.Messageable] = None,
    ):
        quest = QUEST_DEFINITIONS.get(quest_key)
        if quest is None:
            return

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        key_day = day if quest["repeat"] == "daily" else None
        cur.execute(
            "SELECT progress, completed_at, claimed_at FROM quest_progress "
            "WHERE guild_id=? AND user_id=? AND quest_key=? AND day IS ?",
            (guild_id, user_id, quest_key, key_day),
        )
        row = cur.fetchone()
        progress = row[0] if row else 0
        completed_at = row[1] if row else None
        claimed_at = row[2] if row else None

        if completed_at is not None:
            conn.close()
            return

        new_progress = progress + delta
        if check_level:
            xp_val = self._get_xp(guild_id, user_id)
            new_progress = int(xp_val ** 0.5)

        completed = new_progress >= quest["target"]
        should_notify = completed and completed_at is None

        if row:
            cur.execute(
                "UPDATE quest_progress SET progress=?, completed_at=? WHERE guild_id=? AND user_id=? AND quest_key=? AND day IS ?",
                (
                    new_progress,
                    datetime.datetime.now(datetime.timezone.utc).isoformat() if completed else None,
                    guild_id,
                    user_id,
                    quest_key,
                    key_day,
                ),
            )
        else:
            cur.execute(
                "INSERT INTO quest_progress (guild_id, user_id, quest_key, day, progress, completed_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    guild_id,
                    user_id,
                    quest_key,
                    key_day,
                    new_progress,
                    datetime.datetime.now(datetime.timezone.utc).isoformat() if completed else None,
                ),
            )
        conn.commit()
        conn.close()

        if should_notify and channel is not None:
            self._queue_notification(
                channel,
                f"✅ <@{user_id}> completed the quest '{quest['title']}'! Use `/claim_quest {quest_key}` to collect {quest['reward_xp']} XP."
            )

    def _award_achievement(self, guild_id: int, user_id: int, achievement_key: str) -> bool:
        if achievement_key not in ACHIEVEMENT_DEFINITIONS:
            return False
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM achievements WHERE guild_id=? AND user_id=? AND achievement_key=?",
            (guild_id, user_id, achievement_key),
        )
        if cur.fetchone():
            conn.close()
            return False
        cur.execute(
            "INSERT INTO achievements (guild_id, user_id, achievement_key, unlocked_at) VALUES (?, ?, ?, ?)",
            (guild_id, user_id, achievement_key, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()
        return True

    def _format_achievement(self, achievement_key: str) -> str:
        achievement = ACHIEVEMENT_DEFINITIONS.get(achievement_key)
        if not achievement:
            return achievement_key
        return f"{achievement['title']} — {achievement['description']}"

    def _queue_notification(self, channel: discord.abc.Messageable, message: str):
        if channel is None or not hasattr(self.client, 'loop'):
            return
        try:
            loop = self.client.loop
            if loop.is_running():
                loop.create_task(self._send_notification(channel, message))
            else:
                asyncio.run_coroutine_threadsafe(self._send_notification(channel, message), loop)
        except Exception:
            pass

    async def _send_notification(self, channel: discord.abc.Messageable, message: str):
        try:
            await channel.send(message)
        except Exception:
            pass

    def _get_xp(self, guild_id: int, user_id: int) -> int:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT xp FROM xp WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

    def _get_user_achievements(self, guild_id: int, user_id: int):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT achievement_key, unlocked_at FROM achievements WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        rows = cur.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}

    def _get_quest_rows(self, guild_id: int, user_id: int):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT quest_key, day, progress, completed_at, claimed_at FROM quest_progress "
            "WHERE guild_id=? AND user_id=?",
            (guild_id, user_id),
        )
        rows = cur.fetchall()
        conn.close()
        return {(row[0], row[1]): row[2:] for row in rows}

    def _format_quest(self, quest_key: str, day: Optional[str], progress: int, completed_at: Optional[str], claimed_at: Optional[str]):
        quest = QUEST_DEFINITIONS.get(quest_key)
        if not quest:
            return None
        target = quest["target"]
        if quest["repeat"] == "daily":
            label = f"{quest['title']} ({day or _get_today()})"
        else:
            label = quest["title"]
        status = "Completed" if completed_at else f"{min(progress, target)}/{target}"
        if claimed_at:
            status = "Claimed"
        return f"{label}: {quest['description']} — {status}"

    def _claim_quest(self, guild_id: int, user_id: int, quest_key: str):
        quest = QUEST_DEFINITIONS.get(quest_key)
        if not quest:
            return False, "Unknown quest."

        key_day = _get_today() if quest["repeat"] == "daily" else None
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "SELECT progress, completed_at, claimed_at FROM quest_progress "
            "WHERE guild_id=? AND user_id=? AND quest_key=? AND day IS ?",
            (guild_id, user_id, quest_key, key_day),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False, "You don't have progress for that quest yet."
        progress, completed_at, claimed_at = row
        if claimed_at:
            conn.close()
            return False, "This quest has already been claimed."
        if completed_at is None or progress < quest["target"]:
            conn.close()
            return False, "This quest is not complete yet."

        cur.execute(
            "UPDATE quest_progress SET claimed_at=? WHERE guild_id=? AND user_id=? AND quest_key=? AND day IS ?",
            (datetime.datetime.now(datetime.timezone.utc).isoformat(), guild_id, user_id, quest_key, key_day),
        )
        conn.commit()
        conn.close()
        if quest["reward_xp"] > 0:
            self.add_xp(guild_id, user_id, amount=quest["reward_xp"])
        return True, f"Quest '{quest['title']}' claimed! You earned {quest['reward_xp']} XP."

    def _register_commands(self):
        @self.tree.command(name="xp", description="Show your XP and level.")
        async def xp(interaction: discord.Interaction, user: Optional[discord.User] = None):
            target = user or interaction.user
            xp_val = self._get_xp(interaction.guild_id, target.id)
            level = int(xp_val ** 0.5)
            await interaction.response.send_message(f"{target.mention} — XP: {xp_val}, Level: {level}")

        @self.tree.command(name="rank", description="Show your rank and progress to next level.")
        async def rank(interaction: discord.Interaction, user: Optional[discord.User] = None):
            target = user or interaction.user
            xp_val = self._get_xp(interaction.guild_id, target.id)
            level = int(xp_val ** 0.5)
            next_level_xp = (level + 1) ** 2
            progress = xp_val - (level ** 2)
            needed = next_level_xp - xp_val
            bar_total = 10
            filled = int((progress / max(1, next_level_xp - (level ** 2))) * bar_total)
            bar = ('▓' * filled) + ('░' * (bar_total - filled))
            await interaction.response.send_message(
                f"{target.mention} — Level {level} ({xp_val} XP)\n{bar} {progress}/{next_level_xp - (level ** 2)} XP — {needed} XP to next level"
            )

        @self.tree.command(name="quests", description="Show your current quests and progress.")
        async def quests(interaction: discord.Interaction):
            rows = self._get_quest_rows(interaction.guild_id, interaction.user.id)
            if not rows:
                await interaction.response.send_message("No quest progress yet. Keep chatting to unlock daily quests!")
                return
            lines = []
            for (quest_key, day), (progress, completed_at, claimed_at) in rows.items():
                item = self._format_quest(quest_key, day, progress, completed_at, claimed_at)
                if item:
                    lines.append(item)
            await interaction.response.send_message("\n".join(lines))

        @self.tree.command(name="quest_board", description="Show available quests and how to complete them.")
        async def quest_board(interaction: discord.Interaction):
            today = _get_today()
            active_keys = _roll_daily_quests(interaction.guild_id, interaction.user.id, today)
            lines = ["Today’s active quests:"]
            for key in active_keys:
                quest = QUEST_DEFINITIONS.get(key)
                if not quest:
                    continue
                repeat = "Daily" if quest["repeat"] == "daily" else "One-time"
                lines.append(
                    f"**{quest['title']}** ({key}) — {quest['description']}\n"
                    f"Target: {quest['target']} ({repeat}). Claim with `/claim_quest {key}`."
                )
            if not active_keys:
                lines.append("No active quests right now — check back tomorrow.")
            content = "\n\n".join(lines)
            chunks = _chunk_text(content)
            await interaction.response.send_message(chunks[0], ephemeral=True)
            for chunk in chunks[1:]:
                await interaction.followup.send(chunk, ephemeral=True)

        @self.tree.command(name="claim_quest", description="Claim a completed quest reward.")
        @app_commands.describe(quest_key="Quest to claim (daily_chatter, daily_xp_boost, level_3_milestone)")
        async def claim_quest(interaction: discord.Interaction, quest_key: str):
            success, message = self._claim_quest(interaction.guild_id, interaction.user.id, quest_key)
            await interaction.response.send_message(message, ephemeral=not success)

        @self.tree.command(name="achievements", description="Show your earned achievements.")
        async def achievements(interaction: discord.Interaction):
            earned = self._get_user_achievements(interaction.guild_id, interaction.user.id)
            if not earned:
                await interaction.response.send_message("No achievements earned yet. Keep earning XP to unlock them!")
                return
            lines = []
            for key, unlocked_at in earned.items():
                entry = ACHIEVEMENT_DEFINITIONS.get(key)
                if not entry:
                    continue
                lines.append(f"{entry['title']}: {entry['description']} — unlocked {unlocked_at}")
            await interaction.response.send_message("\n".join(lines))

        @self.tree.command(name="reset_xp", description="Reset a user's XP (admin only).")
        @app_commands.describe(user="User to reset XP for")
        async def reset_xp(interaction: discord.Interaction, user: discord.User):
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("You need Manage Server permission to use this.", ephemeral=True)
                return
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("UPDATE xp SET xp = 0 WHERE guild_id=? AND user_id=?", (interaction.guild_id, user.id))
            conn.commit()
            conn.close()
            try:
                current_level = 0
                self._assign_level_roles(interaction.guild_id, user.id, current_level, current_level)
            except Exception:
                pass
            await interaction.response.send_message(f"Reset XP for {user.mention}.")

        @self.tree.command(name="refresh_level_roles", description="Recalculate your current level role and title.")
        async def refresh_level_roles(interaction: discord.Interaction, user: Optional[discord.User] = None):
            target = user or interaction.user
            current_level = int(self._get_xp(interaction.guild_id, target.id) ** 0.5)
            try:
                self._assign_level_roles(interaction.guild_id, target.id, max(0, current_level - 1), current_level)
            except Exception:
                pass
            await interaction.response.send_message(f"Refreshed level roles and title for {target.mention}.", ephemeral=True)

        @self.tree.command(name="leaderboard", description="Show guild XP leaderboard.")
        @app_commands.describe(page="Page number (starting at 1)")
        async def leaderboard(interaction: discord.Interaction, page: Optional[int] = 1):
            page = max(1, page or 1)
            per_page = 10
            offset = (page - 1) * per_page
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT user_id, xp FROM xp WHERE guild_id=? ORDER BY xp DESC LIMIT ? OFFSET ?", (interaction.guild_id, per_page, offset))
            rows = cur.fetchall()
            conn.close()
            if not rows:
                await interaction.response.send_message("No XP recorded on this page.")
                return
            lines = [f"{offset + i + 1}. <@{r[0]}> — {r[1]} XP" for i, r in enumerate(rows)]
            await interaction.response.send_message("\n".join(lines))

        @self.tree.command(name="setup_default_level_roles", description="Create the default beginner-to-legend level role ladder.")
        async def setup_default_level_roles(interaction: discord.Interaction):
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message("You need Manage Server permission to use this.", ephemeral=True)
                return

            ladder = [
                (0, "Novice", 0x95a5a6),
                (6, "Apprentice", 0x2ecc71),
                (11, "Adept", 0x3498db),
                (16, "Champion", 0x9b59b6),
                (21, "Legend", 0xffd700),
            ]

            guild = interaction.guild
            if guild is None:
                await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
                return

            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            created = []
            for level, name, color in ladder:
                existing = cur.execute("SELECT role_id FROM level_roles WHERE guild_id=? AND level=?", (guild.id, level)).fetchone()
                if existing:
                    role = guild.get_role(existing[0])
                    if role is None:
                        cur.execute("DELETE FROM level_roles WHERE guild_id=? AND level=?", (guild.id, level))
                    else:
                        created.append((level, role.name, role.id))
                        continue
                role = await guild.create_role(name=name, colour=discord.Colour(color), mentionable=True, reason="Default level role ladder")
                cur.execute("INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)", (guild.id, level, role.id))
                created.append((level, role.name, role.id))
            conn.commit()
            conn.close()

            try:
                conn = sqlite3.connect(DB_PATH)
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM xp WHERE guild_id=?", (guild.id,))
                users = [row[0] for row in cur.fetchall()]
                conn.close()
                for user_id in users:
                    current_level = int(self._get_xp(guild.id, user_id) ** 0.5)
                    self._assign_level_roles(guild.id, user_id, max(0, current_level - 1), current_level)
            except Exception:
                pass

            await interaction.response.send_message(
                "Created/updated the default level-role ladder:\n" + "\n".join(
                    f"• Level {level}: {name} (role ID {role_id})" for level, name, role_id in created
                ) + "\n\nApplied the current tier to members with XP.",
                ephemeral=True,
            )

        @self.tree.command(name="set_level_role", description="Assign a role reward for reaching a level.")
        @app_commands.describe(level="Level threshold", role="Role to assign when reaching level")
        async def set_level_role(interaction: discord.Interaction, level: int, role: discord.Role):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)", (interaction.guild_id, level, role.id))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"Assigned role {role.name} for level {level}.")

        @self.tree.command(name="remove_level_role", description="Remove a role reward for a level.")
        @app_commands.describe(level="Level threshold to remove")
        async def remove_level_role(interaction: discord.Interaction, level: int):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("DELETE FROM level_roles WHERE guild_id=? AND level=?", (interaction.guild_id, level))
            conn.commit()
            conn.close()
            await interaction.response.send_message(f"Removed role reward for level {level}.")

    async def _set_level_title(self, guild: discord.Guild, member: discord.Member, level: int):
        try:
            current_name = member.display_name
            prefix = f"[Lv {level}]"
            if current_name.startswith("[Lv "):
                current_name = current_name.split(']', 1)[-1].lstrip()
            await member.edit(nick=f"{prefix} {current_name}", reason="Level title update")
        except Exception:
            pass

    def _assign_level_roles(self, guild_id: int, user_id: int, prev_level: int, new_level: int):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT level, role_id FROM level_roles WHERE guild_id=? ORDER BY level ASC", (guild_id,))
        rows = cur.fetchall()
        conn.close()
        if not rows:
            return
        guild = self.client.get_guild(guild_id)
        if not guild:
            return
        member = guild.get_member(user_id)
        if not member:
            return

        configured_roles = {role_id for _, role_id in rows}
        for role_id in configured_roles:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    asyncio.run_coroutine_threadsafe(member.remove_roles(role, reason="Level role update"), self.client.loop)
                except Exception:
                    pass

        best_level = max((lvl for lvl, _ in rows if lvl <= new_level), default=None)
        if best_level is None:
            return
        role_id = next((rid for lvl, rid in rows if lvl == best_level), None)
        role = guild.get_role(role_id) if role_id is not None else None
        if role and role not in member.roles:
            try:
                asyncio.run_coroutine_threadsafe(member.add_roles(role, reason="Level reward"), self.client.loop)
            except Exception:
                pass

        try:
            loop = self.client.loop
            if loop and loop.is_running():
                loop.create_task(self._set_level_title(guild, member, best_level))
            else:
                asyncio.run_coroutine_threadsafe(self._set_level_title(guild, member, best_level), loop)
        except Exception:
            pass
