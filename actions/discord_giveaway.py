"""
Discord Giveaway System
Handles creation, management, and automated drawing of giveaways
"""

import discord
from discord.ext import commands, tasks
import json
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import os

class GiveawayManager:
    """Manages Discord giveaways with auto-drawing and notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.giveaways_file = "config/giveaways.json"
        self.giveaways = {}
        self.load_giveaways()
        self.check_giveaways.start()
    
    def load_giveaways(self):
        """Load giveaways from file"""
        if os.path.exists(self.giveaways_file):
            try:
                with open(self.giveaways_file, 'r') as f:
                    self.giveaways = json.load(f)
            except:
                self.giveaways = {}
    
    def save_giveaways(self):
        """Save giveaways to file"""
        os.makedirs("config", exist_ok=True)
        with open(self.giveaways_file, 'w') as f:
            json.dump(self.giveaways, f, indent=2)
    
    async def create_giveaway(self, 
                             channel: discord.TextChannel,
                             title: str,
                             duration_minutes: int,
                             winner_count: int = 1,
                             requirements: Optional[Dict] = None) -> str:
        """
        Create a new giveaway
        
        Args:
            channel: Channel to post giveaway in
            title: Giveaway title/prize
            duration_minutes: Duration in minutes
            winner_count: Number of winners
            requirements: Optional dict with 'role' or 'min_age_days' requirements
        
        Returns:
            Giveaway ID
        """
        giveaway_id = f"giveaway_{datetime.now().timestamp()}"
        end_time = (datetime.now() + timedelta(minutes=duration_minutes)).isoformat()
        
        giveaway_data = {
            "id": giveaway_id,
            "title": title,
            "channel_id": channel.id,
            "end_time": end_time,
            "winner_count": winner_count,
            "participants": [],
            "requirements": requirements or {},
            "drawn": False,
            "winners": []
        }
        
        # Create announcement message
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Prize:** {title}",
            color=discord.Color.gold()
        )
        embed.add_field(name="Winners", value=str(winner_count), inline=True)
        embed.add_field(name="Duration", value=f"{duration_minutes} minutes", inline=True)
        embed.add_field(name="React with 🎉", value="to enter!", inline=False)
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")
        
        message = await channel.send(embed=embed)
        await message.add_reaction("🎉")
        
        giveaway_data["message_id"] = message.id
        self.giveaways[giveaway_id] = giveaway_data
        self.save_giveaways()
        
        return giveaway_id
    
    async def add_participant(self, giveaway_id: str, user_id: int) -> bool:
        """Add participant to giveaway"""
        if giveaway_id not in self.giveaways:
            return False
        
        giveaway = self.giveaways[giveaway_id]
        
        # Check requirements
        if giveaway["requirements"]:
            member = None
            try:
                channel = self.bot.get_channel(giveaway["channel_id"])
                if channel:
                    guild = channel.guild
                    member = await guild.fetch_member(user_id)
            except:
                return False
            
            # Check role requirement
            if "role" in giveaway["requirements"] and member:
                role_id = giveaway["requirements"]["role"]
                if not any(r.id == role_id for r in member.roles):
                    return False
            
            # Check account age requirement
            if "min_age_days" in giveaway["requirements"] and member:
                account_age = datetime.now() - member.created_at.replace(tzinfo=None)
                min_age = timedelta(days=giveaway["requirements"]["min_age_days"])
                if account_age < min_age:
                    return False
        
        if user_id not in giveaway["participants"]:
            giveaway["participants"].append(user_id)
            self.save_giveaways()
            return True
        
        return False
    
    async def remove_participant(self, giveaway_id: str, user_id: int) -> bool:
        """Remove participant from giveaway"""
        if giveaway_id not in self.giveaways:
            return False
        
        giveaway = self.giveaways[giveaway_id]
        if user_id in giveaway["participants"]:
            giveaway["participants"].remove(user_id)
            self.save_giveaways()
            return True
        
        return False
    
    async def draw_winners(self, giveaway_id: str) -> List[int]:
        """Draw winners from giveaway"""
        if giveaway_id not in self.giveaways:
            return []
        
        giveaway = self.giveaways[giveaway_id]
        
        if giveaway["drawn"] or not giveaway["participants"]:
            return []
        
        # Select random winners
        winner_count = min(giveaway["winner_count"], len(giveaway["participants"]))
        winners = random.sample(giveaway["participants"], winner_count)
        
        giveaway["winners"] = winners
        giveaway["drawn"] = True
        self.save_giveaways()
        
        # Notify winners
        await self.notify_winners(giveaway_id, winners)
        
        return winners
    
    async def notify_winners(self, giveaway_id: str, winner_ids: List[int]):
        """Notify winners via DM and announce in channel"""
        if giveaway_id not in self.giveaways:
            return
        
        giveaway = self.giveaways[giveaway_id]
        channel = self.bot.get_channel(giveaway["channel_id"])
        
        if not channel:
            return
        
        # Announce winners
        winner_mentions = ", ".join([f"<@{uid}>" for uid in winner_ids])
        embed = discord.Embed(
            title="🎉 GIVEAWAY WINNER(S) 🎉",
            description=f"**Prize:** {giveaway['title']}\n**Winners:** {winner_mentions}",
            color=discord.Color.green()
        )
        
        await channel.send(embed=embed)
        
        # Send DM to winners
        for winner_id in winner_ids:
            try:
                user = await self.bot.fetch_user(winner_id)
                if user:
                    dm_embed = discord.Embed(
                        title="🎉 You Won! 🎉",
                        description=f"Congratulations! You won: **{giveaway['title']}**\n\nPlease contact a moderator to claim your prize.",
                        color=discord.Color.gold()
                    )
                    await user.send(embed=dm_embed)
            except:
                pass
    
    @tasks.loop(minutes=1)
    async def check_giveaways(self):
        """Check if giveaways should be drawn"""
        for giveaway_id, giveaway in list(self.giveaways.items()):
            if giveaway["drawn"]:
                continue
            
            end_time = datetime.fromisoformat(giveaway["end_time"])
            if datetime.now() >= end_time:
                await self.draw_winners(giveaway_id)
    
    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
    
    async def get_giveaway_status(self, giveaway_id: str) -> Optional[Dict]:
        """Get status of a giveaway"""
        if giveaway_id in self.giveaways:
            giveaway = self.giveaways[giveaway_id]
            return {
                "title": giveaway["title"],
                "participants": len(giveaway["participants"]),
                "winners_needed": giveaway["winner_count"],
                "drawn": giveaway["drawn"],
                "winners": giveaway["winners"],
                "end_time": giveaway["end_time"]
            }
        return None
    
    async def end_giveaway_early(self, giveaway_id: str) -> bool:
        """End a giveaway early"""
        if giveaway_id not in self.giveaways or self.giveaways[giveaway_id]["drawn"]:
            return False
        
        return bool(await self.draw_winners(giveaway_id))


class GiveawayCog(commands.Cog):
    """Discord commands for giveaways"""
    
    def __init__(self, bot):
        self.bot = bot
        self.manager = GiveawayManager(bot)
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle giveaway reaction additions"""
        if payload.emoji.name != "🎉":
            return
        
        user = await self.bot.fetch_user(payload.user_id)
        if user.bot:
            return
        
        # Find giveaway by message ID
        for giveaway_id, giveaway in self.manager.giveaways.items():
            if giveaway.get("message_id") == payload.message_id:
                await self.manager.add_participant(giveaway_id, payload.user_id)
                break
    
    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle giveaway reaction removals"""
        if payload.emoji.name != "🎉":
            return
        
        user = await self.bot.fetch_user(payload.user_id)
        if user.bot:
            return
        
        # Remove from giveaway
        for giveaway_id, giveaway in self.manager.giveaways.items():
            if giveaway.get("message_id") == payload.message_id:
                await self.manager.remove_participant(giveaway_id, payload.user_id)
                break
    
    @discord.app_commands.command(name="giveaway", description="Create a giveaway")
    @discord.app_commands.describe(
        prize="The prize for the giveaway",
        duration="Duration in minutes",
        winners="Number of winners"
    )
    async def giveaway_create(self, interaction: discord.Interaction, prize: str, duration: int, winners: int = 1):
        """Create a new giveaway"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to create giveaways.", ephemeral=True)
            return
        
        await self.manager.create_giveaway(
            interaction.channel,
            prize,
            duration,
            winners
        )
        
        await interaction.response.send_message(f"✅ Giveaway created for **{prize}** ({duration} minutes, {winners} winner(s))", ephemeral=True)
    
    @discord.app_commands.command(name="giveaway_status", description="Check giveaway status")
    @discord.app_commands.describe(giveaway_id="The giveaway ID")
    async def giveaway_status(self, interaction: discord.Interaction, giveaway_id: str):
        """Check status of a giveaway"""
        status = await self.manager.get_giveaway_status(giveaway_id)
        
        if not status:
            await interaction.response.send_message("Giveaway not found.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Giveaway Status",
            description=f"**Prize:** {status['title']}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Participants", value=str(status['participants']), inline=True)
        embed.add_field(name="Winners Needed", value=str(status['winners_needed']), inline=True)
        embed.add_field(name="Status", value="Drawn" if status['drawn'] else "Active", inline=True)
        
        if status['drawn']:
            embed.add_field(name="Winners", value=", ".join([f"<@{uid}>" for uid in status['winners']]), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.app_commands.command(name="giveaway_end", description="End a giveaway early")
    @discord.app_commands.describe(giveaway_id="The giveaway ID")
    async def giveaway_end(self, interaction: discord.Interaction, giveaway_id: str):
        """End a giveaway early and draw winners"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to end giveaways.", ephemeral=True)
            return
        
        success = await self.manager.end_giveaway_early(giveaway_id)
        
        if success:
            await interaction.response.send_message("✅ Giveaway ended and winners drawn!", ephemeral=True)
        else:
            await interaction.response.send_message("Could not end giveaway (already drawn or not found).", ephemeral=True)


async def setup_giveaway(bot):
    """Setup giveaway cog"""
    await bot.add_cog(GiveawayCog(bot))
