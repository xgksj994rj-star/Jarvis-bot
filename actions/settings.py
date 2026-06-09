import sqlite3
import discord
from discord import app_commands
from typing import Optional

DB_PATH = "data/jarvis.db"

def _ensure_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id INTEGER PRIMARY KEY,
            gamification_enabled INTEGER DEFAULT 1,
            moderation_enabled INTEGER DEFAULT 1
        )
        """
    )
    conn.commit()
    conn.close()
    # Add extra columns if they don't exist
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE guild_settings ADD COLUMN cooldown_seconds INTEGER DEFAULT 60")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE guild_settings ADD COLUMN daily_xp_cap INTEGER DEFAULT 500")
    except Exception:
        pass
    conn.commit()
    conn.close()


def get_setting(guild_id: int, key: str) -> Optional[int]:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"SELECT {key} FROM guild_settings WHERE guild_id=?", (guild_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return None


def set_setting(guild_id: int, key: str, value: int):
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Use UPSERT to insert or update the setting
    cur.execute(
        "INSERT INTO guild_settings (guild_id, {k}) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET {k} = excluded.{k}".format(k=key),
        (guild_id, value),
    )
    conn.commit()
    conn.close()


class SettingsCog:
    def __init__(self, tree: 'app_commands.CommandTree'):
        _ensure_db()
        self.tree = tree
        self._register_commands()

    def _register_commands(self):
        @self.tree.command(name="set_feature", description="Enable or disable a server feature.")
        @app_commands.describe(feature="Feature to toggle (gamification/moderation)", enabled="Enable (true) or disable (false)")
        async def set_feature(interaction: 'discord.Interaction', feature: str, enabled: bool):
            key = None
            if feature.lower() == "gamification":
                key = "gamification_enabled"
            elif feature.lower() == "moderation":
                key = "moderation_enabled"
            else:
                await interaction.response.send_message("Unknown feature. Use 'gamification' or 'moderation'.", ephemeral=True)
                return
            set_setting(interaction.guild_id, key, 1 if enabled else 0)
            await interaction.response.send_message(f"Set {feature} to {enabled} for this server.")

        @self.tree.command(name="set_gamification", description="Configure gamification settings for this server.")
        @app_commands.describe(cooldown="Cooldown seconds between XP awards (optional)", daily_cap="Daily XP cap per user (optional)")
        async def set_gamification(interaction: 'discord.Interaction', cooldown: Optional[int] = None, daily_cap: Optional[int] = None):
            if cooldown is None and daily_cap is None:
                await interaction.response.send_message("Provide at least one option: cooldown or daily_cap", ephemeral=True)
                return
            if cooldown is not None:
                set_setting(interaction.guild_id, "cooldown_seconds", int(cooldown))
            if daily_cap is not None:
                set_setting(interaction.guild_id, "daily_xp_cap", int(daily_cap))
            await interaction.response.send_message("Gamification settings updated.")

        @self.tree.command(name="show_features", description="Show enabled features for this server.")
        async def show_features(interaction: 'discord.Interaction'):
            g = interaction.guild_id
            gam = get_setting(g, "gamification_enabled")
            mod = get_setting(g, "moderation_enabled")
            await interaction.response.send_message(f"gamification: {bool(gam) if gam is not None else True}\nmoderation: {bool(mod) if mod is not None else True}")
