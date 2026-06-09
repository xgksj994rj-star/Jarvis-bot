"""
Discord Birthday Tracker System
Automatically announces birthdays and grants temporary roles
"""

import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os

class BirthdayTracker:
    """Manages birthday tracking and announcements"""
    
    def __init__(self, bot):
        self.bot = bot
        self.birthdays_file = "config/birthdays.json"
        self.birthdays = {}
        self.birthday_role_config = {}
        self.load_birthdays()
        self.check_birthdays.start()
    
    def load_birthdays(self):
        """Load birthdays from file"""
        if os.path.exists(self.birthdays_file):
            try:
                with open(self.birthdays_file, 'r') as f:
                    data = json.load(f)
                    self.birthdays = data.get("birthdays", {})
                    self.birthday_role_config = data.get("config", {})
            except:
                self.birthdays = {}
                self.birthday_role_config = {}
    
    def save_birthdays(self):
        """Save birthdays to file"""
        os.makedirs("config", exist_ok=True)
        with open(self.birthdays_file, 'w') as f:
            json.dump({
                "birthdays": self.birthdays,
                "config": self.birthday_role_config
            }, f, indent=2)
    
    async def set_birthday(self, user_id: int, month: int, day: int, guild_id: int) -> bool:
        """
        Set a user's birthday
        
        Args:
            user_id: Discord user ID
            month: Birth month (1-12)
            day: Birth day (1-31)
            guild_id: Guild ID for this birthday entry
        """
        if month < 1 or month > 12 or day < 1 or day > 31:
            return False
        
        key = f"{user_id}_{guild_id}"
        self.birthdays[key] = {
            "user_id": user_id,
            "guild_id": guild_id,
            "month": month,
            "day": day,
            "last_announced": None
        }
        self.save_birthdays()
        return True
    
    async def set_birthday_channel(self, guild_id: int, channel_id: int) -> bool:
        """Set the channel for birthday announcements"""
        if guild_id not in self.birthday_role_config:
            self.birthday_role_config[guild_id] = {}
        
        self.birthday_role_config[guild_id]["announcement_channel"] = channel_id
        self.save_birthdays()
        return True
    
    async def set_birthday_role(self, guild_id: int, role_id: int, duration_hours: int = 24) -> bool:
        """
        Set the role to grant on birthday
        
        Args:
            guild_id: Guild ID
            role_id: Role ID to grant
            duration_hours: How long to keep the role
        """
        if guild_id not in self.birthday_role_config:
            self.birthday_role_config[guild_id] = {}
        
        self.birthday_role_config[guild_id]["birthday_role"] = role_id
        self.birthday_role_config[guild_id]["role_duration_hours"] = duration_hours
        self.save_birthdays()
        return True
    
    @tasks.loop(hours=1)
    async def check_birthdays(self):
        """Check for birthdays and announce them"""
        today = datetime.now()
        
        for key, birthday_data in list(self.birthdays.items()):
            # Check if today is their birthday
            if birthday_data["month"] == today.month and birthday_data["day"] == today.day:
                # Don't announce multiple times per year
                last_announced = birthday_data.get("last_announced")
                if last_announced:
                    last_date = datetime.fromisoformat(last_announced)
                    if last_date.year == today.year:
                        continue
                
                guild_id = birthday_data["guild_id"]
                user_id = birthday_data["user_id"]
                
                await self.announce_birthday(guild_id, user_id)
                
                birthday_data["last_announced"] = today.isoformat()
                self.save_birthdays()
    
    @check_birthdays.before_loop
    async def before_check_birthdays(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
    
    async def announce_birthday(self, guild_id: int, user_id: int):
        """Announce a birthday and grant temporary role"""
        if guild_id not in self.birthday_role_config:
            return
        
        config = self.birthday_role_config[guild_id]
        
        # Get announcement channel
        channel_id = config.get("announcement_channel")
        if not channel_id:
            return
        
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            
            member = await guild.fetch_member(user_id)
            if not member:
                return
            
            # Send announcement
            embed = discord.Embed(
                title="🎂 BIRTHDAY! 🎂",
                description=f"Today is {member.mention}'s birthday! 🎉",
                color=discord.Color.magenta()
            )
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Month/Day", value=f"{member.created_at.month}/{member.created_at.day}", inline=True)
            
            await channel.send(embed=embed)
            
            # Grant birthday role if configured
            birthday_role_id = config.get("birthday_role")
            if birthday_role_id:
                role = guild.get_role(birthday_role_id)
                if role:
                    await member.add_roles(role)
                    
                    # Schedule role removal
                    duration = config.get("role_duration_hours", 24)
                    self.bot.loop.create_task(
                        self._remove_role_later(member, role, duration)
                    )
        
        except Exception as e:
            print(f"Error announcing birthday: {e}")
    
    async def _remove_role_later(self, member: discord.Member, role: discord.Role, hours: int):
        """Remove a role after a delay"""
        await asyncio.sleep(hours * 3600)
        
        try:
            await member.remove_roles(role)
        except:
            pass
    
    async def get_birthday(self, user_id: int, guild_id: int) -> Optional[Dict]:
        """Get birthday info for a user"""
        key = f"{user_id}_{guild_id}"
        if key in self.birthdays:
            data = self.birthdays[key]
            return {
                "month": data["month"],
                "day": data["day"],
                "next_birthday": self._get_next_birthday(data["month"], data["day"])
            }
        return None
    
    def _get_next_birthday(self, month: int, day: int) -> str:
        """Calculate next birthday date"""
        today = datetime.now()
        this_year = datetime(today.year, month, day)
        
        if this_year < today:
            next_birthday = datetime(today.year + 1, month, day)
        else:
            next_birthday = this_year
        
        days_until = (next_birthday - today).days
        return f"{next_birthday.strftime('%B %d, %Y')} ({days_until} days away)"
    
    async def list_birthdays(self, guild_id: int) -> List[Dict]:
        """List all birthdays in a guild"""
        birthdays = []
        
        for key, data in self.birthdays.items():
            if data["guild_id"] == guild_id:
                birthdays.append({
                    "user_id": data["user_id"],
                    "month": data["month"],
                    "day": data["day"]
                })
        
        return sorted(birthdays, key=lambda x: (x["month"], x["day"]))
    
    async def remove_birthday(self, user_id: int, guild_id: int) -> bool:
        """Remove a birthday entry"""
        key = f"{user_id}_{guild_id}"
        if key in self.birthdays:
            del self.birthdays[key]
            self.save_birthdays()
            return True
        return False


class BirthdayCog(commands.Cog):
    """Discord commands for birthday tracking"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tracker = BirthdayTracker(bot)
    
    @discord.app_commands.command(name="birthday_set", description="Set your birthday")
    @discord.app_commands.describe(month="Birth month (1-12)", day="Birth day (1-31)")
    async def birthday_set(self, interaction: discord.Interaction, month: int, day: int):
        """Set your birthday"""
        success = await self.tracker.set_birthday(interaction.user.id, month, day, interaction.guild_id)
        
        if success:
            embed = discord.Embed(
                title="✅ Birthday Set!",
                description=f"Your birthday is set to {month}/{day}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ Invalid month or day.", ephemeral=True)
    
    @discord.app_commands.command(name="birthday_info", description="Check someone's birthday")
    @discord.app_commands.describe(user="The user to check")
    async def birthday_info(self, interaction: discord.Interaction, user: discord.User):
        """Get birthday information"""
        info = await self.tracker.get_birthday(user.id, interaction.guild_id)
        
        if not info:
            await interaction.response.send_message(f"{user.mention} hasn't set a birthday yet.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎂 Birthday Info",
            description=f"User: {user.mention}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Birthday", value=f"{info['month']}/{info['day']}", inline=True)
        embed.add_field(name="Next Birthday", value=info['next_birthday'], inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="birthday_list", description="List all birthdays in server")
    async def birthday_list(self, interaction: discord.Interaction):
        """List all registered birthdays"""
        birthdays = await self.tracker.list_birthdays(interaction.guild_id)
        
        if not birthdays:
            await interaction.response.send_message("No birthdays registered yet.", ephemeral=True)
            return
        
        birthday_list = "\n".join([
            f"<@{b['user_id']}> - {b['month']}/{b['day']}"
            for b in birthdays
        ])
        
        embed = discord.Embed(
            title="📅 Server Birthdays",
            description=birthday_list,
            color=discord.Color.purple()
        )
        
        await interaction.response.send_message(embed=embed)
    
    @discord.app_commands.command(name="birthday_channel", description="Set birthday announcement channel")
    @discord.app_commands.describe(channel="The channel for announcements")
    async def birthday_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Set birthday announcement channel"""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return
        
        await self.tracker.set_birthday_channel(interaction.guild_id, channel.id)
        await interaction.response.send_message(f"✅ Birthday announcements will be posted in {channel.mention}", ephemeral=True)
    
    @discord.app_commands.command(name="birthday_role", description="Set birthday role")
    @discord.app_commands.describe(
        role="Role to grant on birthday",
        duration="How many hours to keep role (default 24)"
    )
    async def birthday_role(self, interaction: discord.Interaction, role: discord.Role, duration: int = 24):
        """Set birthday role"""
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return
        
        await self.tracker.set_birthday_role(interaction.guild_id, role.id, duration)
        await interaction.response.send_message(f"✅ Birthday role set to {role.mention} ({duration}h)", ephemeral=True)


import asyncio

async def setup_birthday(bot):
    """Setup birthday cog"""
    await bot.add_cog(BirthdayCog(bot))
