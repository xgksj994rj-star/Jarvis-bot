"""
Discord Ticket System
Provides support channels, auto-archiving, and mod assignment
"""

import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os

class TicketSystem:
    """Manages support tickets with auto-archiving and mod assignment"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tickets_file = "config/tickets.json"
        self.tickets = {}
        self.ticket_config = {}
        self.load_tickets()
        self.check_inactive_tickets.start()
    
    def load_tickets(self):
        """Load tickets from file"""
        if os.path.exists(self.tickets_file):
            try:
                with open(self.tickets_file, 'r') as f:
                    data = json.load(f)
                    self.tickets = data.get("tickets", {})
                    self.ticket_config = data.get("config", {})
            except:
                self.tickets = {}
                self.ticket_config = {}
    
    def save_tickets(self):
        """Save tickets to file"""
        os.makedirs("config", exist_ok=True)
        with open(self.tickets_file, 'w') as f:
            json.dump({
                "tickets": self.tickets,
                "config": self.ticket_config
            }, f, indent=2)
    
    async def setup_ticket_system(self, guild_id: int, support_role_id: int, archive_category_id: int) -> bool:
        """
        Setup ticket system for a guild
        
        Args:
            guild_id: Guild ID
            support_role_id: Role ID for ticket moderators
            archive_category_id: Category ID for archived tickets
        """
        if guild_id not in self.ticket_config:
            self.ticket_config[guild_id] = {}
        
        self.ticket_config[guild_id]["support_role_id"] = support_role_id
        self.ticket_config[guild_id]["archive_category_id"] = archive_category_id
        self.save_tickets()
        return True
    
    async def create_ticket(self, user_id: int, guild_id: int, subject: str) -> Optional[Dict]:
        """
        Create a new support ticket
        
        Args:
            user_id: User creating the ticket
            guild_id: Guild ID
            subject: Ticket subject
        
        Returns:
            Ticket info dict
        """
        if guild_id not in self.ticket_config:
            return None
        
        config = self.ticket_config[guild_id]
        
        # Get guild and create channel
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None
        
        try:
            user = await self.bot.fetch_user(user_id)
            
            # Create ticket channel
            channel_name = f"ticket-{user.name}-{len(self.tickets) % 1000}"
            
            # Get support role
            support_role = guild.get_role(config.get("support_role_id"))
            
            # Create channel with permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)
            
            channel = await guild.create_text_channel(
                channel_name,
                overwrites=overwrites,
                reason=f"Support ticket created by {user.name}"
            )
            
            # Generate ticket ID
            ticket_id = f"ticket_{datetime.now().timestamp()}"
            
            ticket_data = {
                "id": ticket_id,
                "user_id": user_id,
                "guild_id": guild_id,
                "channel_id": channel.id,
                "subject": subject,
                "created_at": datetime.now().isoformat(),
                "last_message": datetime.now().isoformat(),
                "assigned_to": None,
                "status": "open",
                "archived": False
            }
            
            self.tickets[ticket_id] = ticket_data
            self.save_tickets()
            
            # Send welcome message
            embed = discord.Embed(
                title="📋 Support Ticket",
                description=f"Subject: {subject}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Ticket ID", value=ticket_id, inline=True)
            embed.add_field(name="User", value=user.mention, inline=True)
            embed.add_field(name="Status", value="Open", inline=True)
            embed.set_footer(text="React with 🔒 to close ticket, ✅ to resolve")
            
            msg = await channel.send(embed=embed)
            await msg.add_reaction("🔒")
            await msg.add_reaction("✅")
            
            return ticket_data
        
        except Exception as e:
            print(f"Error creating ticket: {e}")
            return None
    
    async def assign_ticket(self, ticket_id: str, mod_id: int) -> bool:
        """Assign ticket to a moderator"""
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        ticket["assigned_to"] = mod_id
        
        # Add mod to channel
        try:
            guild = self.bot.get_guild(ticket["guild_id"])
            channel = guild.get_channel(ticket["channel_id"])
            mod = await guild.fetch_member(mod_id)
            
            if channel and mod:
                await channel.set_permissions(mod, view_channel=True, send_messages=True, manage_messages=True)
                
                # Send assignment message
                embed = discord.Embed(
                    title="✅ Ticket Assigned",
                    description=f"This ticket has been assigned to {mod.mention}",
                    color=discord.Color.green()
                )
                await channel.send(embed=embed)
        
        except:
            pass
        
        self.save_tickets()
        return True
    
    async def resolve_ticket(self, ticket_id: str) -> bool:
        """Mark ticket as resolved"""
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        ticket["status"] = "resolved"
        
        try:
            guild = self.bot.get_guild(ticket["guild_id"])
            channel = guild.get_channel(ticket["channel_id"])
            
            if channel:
                embed = discord.Embed(
                    title="✅ Ticket Resolved",
                    description="This ticket has been marked as resolved.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Next Step", value="This channel will be archived shortly.", inline=False)
                await channel.send(embed=embed)
        
        except:
            pass
        
        self.save_tickets()
        return True
    
    async def close_ticket(self, ticket_id: str) -> bool:
        """Close and archive a ticket"""
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        ticket["status"] = "closed"
        ticket["archived"] = True
        
        try:
            guild = self.bot.get_guild(ticket["guild_id"])
            channel = guild.get_channel(ticket["channel_id"])
            config = self.ticket_config.get(ticket["guild_id"], {})
            
            if channel:
                # Get archive category
                archive_category_id = config.get("archive_category_id")
                if archive_category_id:
                    archive_category = guild.get_channel(archive_category_id)
                    if archive_category:
                        # Move to archive
                        await channel.edit(category=archive_category)
                
                # Lock channel
                await channel.edit(slowmode_delay=0)
                
                # Send archived message
                embed = discord.Embed(
                    title="🔒 Ticket Archived",
                    description="This ticket has been archived.",
                    color=discord.Color.dark_gray()
                )
                await channel.send(embed=embed)
        
        except:
            pass
        
        self.save_tickets()
        return True
    
    @tasks.loop(hours=1)
    async def check_inactive_tickets(self):
        """Archive inactive tickets"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        for ticket_id, ticket in list(self.tickets.items()):
            if ticket["archived"] or ticket["status"] != "open":
                continue
            
            last_message = datetime.fromisoformat(ticket["last_message"])
            
            if last_message < cutoff_time:
                await self.close_ticket(ticket_id)
    
    @check_inactive_tickets.before_loop
    async def before_check_inactive_tickets(self):
        """Wait for bot to be ready"""
        await self.bot.wait_until_ready()
    
    async def update_last_message(self, ticket_id: str):
        """Update last message timestamp"""
        if ticket_id in self.tickets:
            self.tickets[ticket_id]["last_message"] = datetime.now().isoformat()
            self.save_tickets()
    
    async def get_ticket_info(self, ticket_id: str) -> Optional[Dict]:
        """Get ticket information"""
        if ticket_id in self.tickets:
            return self.tickets[ticket_id]
        return None
    
    async def get_user_tickets(self, user_id: int, guild_id: int) -> List[Dict]:
        """Get all tickets for a user"""
        tickets = []
        for ticket in self.tickets.values():
            if ticket["user_id"] == user_id and ticket["guild_id"] == guild_id:
                tickets.append(ticket)
        return tickets


class TicketCog(commands.Cog):
    """Discord commands for ticket system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.system = TicketSystem(bot)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Track message activity in tickets"""
        if message.author.bot or not message.guild:
            return
        
        # Check if message is in a ticket channel
        for ticket in self.system.tickets.values():
            if ticket["channel_id"] == message.channel.id:
                await self.system.update_last_message(ticket["id"])
                break
    
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Handle ticket actions via reactions"""
        if payload.emoji.name not in ["🔒", "✅"]:
            return
        
        # Find ticket by channel
        for ticket_id, ticket in self.system.tickets.items():
            if ticket["channel_id"] == payload.channel_id:
                guild = self.bot.get_guild(payload.guild_id)
                user = await self.bot.fetch_user(payload.user_id)
                
                if not guild or user.bot:
                    return
                
                member = await guild.fetch_member(payload.user_id)
                
                # Check permissions
                support_role_id = self.system.ticket_config.get(payload.guild_id, {}).get("support_role_id")
                has_permission = (
                    member.guild_permissions.manage_messages or
                    (support_role_id and any(r.id == support_role_id for r in member.roles)) or
                    user.id == ticket["user_id"]
                )
                
                if not has_permission:
                    return
                
                if payload.emoji.name == "✅":
                    await self.system.resolve_ticket(ticket_id)
                elif payload.emoji.name == "🔒":
                    await self.system.close_ticket(ticket_id)
                
                break
    
    @discord.app_commands.command(name="ticket", description="Create a support ticket")
    @discord.app_commands.describe(subject="Subject of your ticket")
    async def ticket_create(self, interaction: discord.Interaction, subject: str):
        """Create a new support ticket"""
        await interaction.response.defer(ephemeral=True)
        
        ticket = await self.system.create_ticket(interaction.user.id, interaction.guild_id, subject)
        
        if ticket:
            await interaction.followup.send(
                f"✅ Ticket created! {interaction.guild.get_channel(ticket['channel_id']).mention}",
                ephemeral=True
            )
        else:
            await interaction.followup.send("❌ Could not create ticket. Ticket system not configured.", ephemeral=True)
    
    @discord.app_commands.command(name="ticket_setup", description="Setup ticket system")
    @discord.app_commands.describe(
        support_role="Role for ticket moderators",
        archive_category="Category for archived tickets"
    )
    async def ticket_setup(self, interaction: discord.Interaction, support_role: discord.Role, archive_category: discord.CategoryChannel):
        """Setup ticket system for the guild"""
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return
        
        await self.system.setup_ticket_system(interaction.guild_id, support_role.id, archive_category.id)
        await interaction.response.send_message(
            f"✅ Ticket system configured!\n- Support Role: {support_role.mention}\n- Archive Category: {archive_category.mention}",
            ephemeral=True
        )
    
    @discord.app_commands.command(name="ticket_assign", description="Assign ticket to moderator")
    @discord.app_commands.describe(ticket_id="Ticket ID", moderator="Moderator to assign")
    async def ticket_assign(self, interaction: discord.Interaction, ticket_id: str, moderator: discord.User):
        """Assign a ticket to a moderator"""
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return
        
        success = await self.system.assign_ticket(ticket_id, moderator.id)
        
        if success:
            await interaction.response.send_message(f"✅ Ticket assigned to {moderator.mention}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ticket not found.", ephemeral=True)


async def setup_ticket(bot):
    """Setup ticket cog"""
    await bot.add_cog(TicketCog(bot))
