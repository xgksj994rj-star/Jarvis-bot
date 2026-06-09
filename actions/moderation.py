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
        CREATE TABLE IF NOT EXISTS mod_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER,
            action TEXT,
            target_id INTEGER,
            moderator_id INTEGER,
            reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


class ModerationCog:
    def __init__(self, tree: app_commands.CommandTree):
        _ensure_db()
        self.tree = tree
        self._register_commands()

    def _log_action(self, guild_id: int, action: str, target_id: int, moderator_id: int, reason: Optional[str]):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO mod_logs (guild_id, action, target_id, moderator_id, reason) VALUES (?, ?, ?, ?, ?)",
            (guild_id, action, target_id, moderator_id, reason),
        )
        conn.commit()
        conn.close()

    def _register_commands(self):
        @self.tree.command(name="modlog", description="View moderation logs for a user.")
        async def modlog(interaction: discord.Interaction, user: discord.User):
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT action, moderator_id, reason, timestamp FROM mod_logs WHERE guild_id=? AND target_id=? ORDER BY timestamp DESC LIMIT 25", (interaction.guild_id, user.id))
            rows = cur.fetchall()
            conn.close()

            if not rows:
                await interaction.response.send_message(f"No moderation logs for {user.mention}.")
                return

            lines = [f"[{r[3]}] {r[0]} by <@{r[1]}>: {r[2] or 'No reason'}" for r in rows]
            text = "\n".join(lines)
            if len(text) > 1900:
                text = text[:1900] + "..."
            await interaction.response.send_message(f"Moderation logs for {user.mention}:\n{text}")

        @self.tree.command(name="appeal", description="Submit a moderation appeal to moderators.")
        async def appeal(interaction: discord.Interaction, message: str):
            # In a full implementation this would notify moderators and create a review ticket.
            self._log_action(interaction.guild_id, "appeal_submitted", interaction.user.id, interaction.user.id, message)
            await interaction.response.send_message("Your appeal has been submitted to the moderation team.")
