import discord.member
from discord.app_commands import CommandInvokeError
from discord.types.embed import EmbedFooter
import os
import re
import json
import asyncio
import datetime
from datetime import timezone
from zoneinfo import ZoneInfo
import discord
import aiohttp
import random
import math
import requests
from datetime import datetime, timedelta
from mcstatus import JavaServer
from discord import app_commands, Interaction
from google import genai

# Intents
intents = discord.Intents.default()


intents.guilds = True
intents.members = True
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


http_session: aiohttp.ClientSession | None = None

PAGE_SIZE = 5

AI_REPLY_MESSAGES = set()

DATA_FILE = "moddata.json"


def load_mod_data() -> dict:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_mod_data(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_guild_data(data: dict, guild_id: int) -> dict:
    guild_key = str(guild_id)
    if guild_key not in data:
        data[guild_key] = {"modlog_channel": None, "warnings": {}}
    if "warnings" not in data[guild_key]:
        data[guild_key]["warnings"] = {}
    if "modlog_channel" not in data[guild_key]:
        data[guild_key]["modlog_channel"] = None
    return data[guild_key]


ACTION_ICONS = {
    "Member Warned": "⚠️",
    "Member Banned": "🔨",
    "Member Unbanned": "🕊️",
    "Member Kicked": "👢",
    "Member Timed Out": "🔇",
    "Timeout Removed": "🔊",
    "Messages Cleared": "🧹",
}


def build_action_embed(
    action: str,
    color: discord.Color,
    moderator: discord.abc.User,
    target: str,
    reason: str = None,
    extra_fields: list = None,
    target_member: discord.abc.User = None,
) -> discord.Embed:
    icon = ACTION_ICONS.get(action, "🛡️")
    embed = discord.Embed(
        title=f"{icon}  {action}",
        color=color,
        timestamp=discord.utils.utcnow(),
    )
    if target_member is not None:
        embed.set_thumbnail(url=target_member.display_avatar.url)
    embed.add_field(name="👤 Member", value=target, inline=True)
    embed.add_field(name="🛡️ Moderator", value=moderator.mention, inline=True)
    if reason is not None:
        embed.add_field(name="📝 Reason", value=reason, inline=False)
    if extra_fields:
        for name, value in extra_fields:
            embed.add_field(name=name, value=value, inline=True)
    embed.set_footer(
        text=f"Moderator: {moderator}",
        icon_url=moderator.display_avatar.url,
    )
    return embed


async def send_modlog(guild: discord.Guild, embed: discord.Embed) -> None:
    data = load_mod_data()
    guild_data = get_guild_data(data, guild.id)
    channel_id = guild_data.get("modlog_channel")
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        pass


@client.event
async def on_ready():
    global http_session

    print(f"Logged in as {client.user}")

    if http_session is None:
        http_session = aiohttp.ClientSession()


        await client.change_presence(activity=discord.Game(name="development"))


gemini = genai.Client(api_key="Place your Google Studio Api key/token here")



@tree.command(
    name="ask",
    description="Ask Google's Gemini AI a question. It does has a cutoff date of about 2025, so keep that in mind",
)
@app_commands.describe(prompt="What would you like to ask?")
async def askai(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()

    try:
        response = gemini.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
        )

        answer = response.text or "I couldn't generate a response."

        if len(answer) > 1900:
            for i in range(0, len(answer), 1900):
                if i == 0:
                    await interaction.followup.send(answer[i : i + 1900])
                else:
                    await interaction.channel.send(answer[i : i + 1900])
        else:
            msg = await interaction.followup.send(answer, wait=True)
            AI_REPLY_MESSAGES.add(msg.id)

    except Exception as e:
        await interaction.followup.send(
            f"Error communicating with Gemini:\n```{e}```",
            ephemeral=True,
        )


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if not message.reference:
        return

    try:
        replied = await message.channel.fetch_message(message.reference.message_id)
    except discord.NotFound:
        return

    if replied.id not in AI_REPLY_MESSAGES:
        return

    try:
        response = gemini.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=[
                f"Previous AI message:\n{replied.content}",
                f"{message.author.display_name}: {message.content}",
            ],
        )

        reply = response.text or "I don't have a response."

        if len(reply) > 2000:
            reply = reply[:1997] + "..."

        sent = await message.reply(reply, mention_author=False)

        AI_REPLY_MESSAGES.add(sent.id)

    except Exception as e:
        await message.reply(f"Error: `{e}`", mention_author=False)


@tree.command(name="userinfo", description="Get information about a user")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    if member is None:
        member = interaction.user

    embed = discord.Embed(
        title=f"User Info - {member.display_name}", color=discord.Color.blue()
    )
    embed.add_field(name="Username", value=member.name, inline=True)
    embed.add_field(name="Discriminator", value=member.discriminator, inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(
        name="Joined Server",
        value=member.joined_at.strftime("%m-%d-%y %H:%M:%S"),
        inline=True,
    )
    embed.add_field(
        name="Account Created",
        value=member.created_at.strftime("%m-%d-%y %H:%M:%S"),
        inline=True,
    )
    embed.set_thumbnail(
        url=member.avatar.url if member.avatar else member.default_avatar.url
    )
    embed.set_footer(
        text=f"Requested by {interaction.user.display_name}",
        icon_url=interaction.user.avatar.url
        if interaction.user.avatar
        else interaction.user.default_avatar.url,
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="serverinfo", description="Get information about the server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(
        title=f"Server Info - {guild.name}", color=discord.Color.blue()
    )
    embed.add_field(name="Server Name", value=guild.name, inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    embed.add_field(name="Owner", value=guild.owner.display_name, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(
        name="Created on",
        value=guild.created_at.strftime("%m-%d-%y %H:%M:%S"),
        inline=True,
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(
        text=f"Requested by {interaction.user.display_name}",
        icon_url=interaction.user.avatar.url
        if interaction.user.avatar
        else interaction.user.default_avatar.url,
    )
    await interaction.response.send_message(embed=embed)


class BanListView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, bans: list):
        super().__init__(timeout=180)
        self.interaction = interaction
        self.bans = bans
        self.page = 0
        self.per_page = 10
        self.max_pages = math.ceil(len(bans) / self.per_page)

        self.update_buttons()

    def update_buttons(self):
        self.previous.disabled = self.page == 0
        self.next.disabled = self.page >= self.max_pages - 1

    def get_embed(self):
        start = self.page * self.per_page
        end = start + self.per_page

        embed = discord.Embed(
            title="🔨 Server Ban List",
            description=f"Showing **{len(self.bans)}** banned user(s).",
            color=discord.Color.red(),
        )

        for i, entry in enumerate(self.bans[start:end], start=start + 1):
            user = entry.user
            reason = entry.reason or "No reason provided"

            # Small avatar (Discord CDN)
            avatar_url = user.display_avatar.replace(size=32).url

            embed.add_field(
                name=f"{i}. {user}",
                value=(f"[🖼️]({avatar_url}) **ID:** `{user.id}`\n📝 {reason}"),
                inline=False,
            )

        embed.set_footer(
            text=f"Page {self.page + 1}/{self.max_pages} • Requested by {self.interaction.user}",
            icon_url=self.interaction.user.display_avatar.url,
        )

        return embed

    @discord.ui.button(label="⬅ Previous", style=discord.ButtonStyle.secondary)
    async def previous(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message(
                "Only the person who ran this command can use these buttons.",
                ephemeral=True,
            )

        self.page -= 1
        self.update_buttons()

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Next ➡", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.interaction.user:
            return await interaction.response.send_message(
                "Only the person who ran this command can use these buttons.",
                ephemeral=True,
            )

        self.page += 1
        self.update_buttons()

        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        try:
            await self.message.edit(view=self)
        except Exception:
            pass



@app_commands.default_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@tree.command(name="banlist", description="List all banned users in the server")
async def banlist(interaction: discord.Interaction):
    bans = [entry async for entry in interaction.guild.bans()]

    if not bans:
        embed = discord.Embed(
            title="📜 Ban List",
            description="There are currently **no banned users** in this server.",
            color=discord.Color.green(),
        )
        embed.set_footer(
            text=f"Requested by {interaction.user}",
            icon_url=interaction.user.display_avatar.url,
        )
        return await interaction.response.send_message(embed=embed)

    view = BanListView(interaction, bans)

    await interaction.response.send_message(embed=view.get_embed(), view=view)

    view.message = await interaction.original_response()


@tree.command(name="mcserver", description="Get information about a Minecraft server")
async def mcserver(interaction: discord.Interaction, server_ip: str):
    try:
        server = JavaServer.lookup(server_ip)
        status = server.status()
        embed = discord.Embed(
            title=f"Minecraft Server Info - {server_ip}", color=discord.Color.green()
        )
        embed.add_field(name="Server IP", value=server_ip, inline=True)
        embed.add_field(name="Version", value=status.version.name, inline=True)
        embed.add_field(
            name="Players Online",
            value=f"{status.players.online}/{status.players.max}",
            inline=True,
        )
        embed.set_thumbnail(url=f"https://api.mcsrvstat.us/icon/{server_ip}")
        embed.add_field(name="Latency", value=f"{status.latency}ms", inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(f"Error: {e}")
        


@tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    result = "Heads" if random.choice([True, False]) else "Tails"
    await interaction.response.send_message(f"The coin landed on: {result}")



@tree.command(name="8ball", description="Ask the magic 8ball a question")
async def eightball(interaction: discord.Interaction, question: str):
    responses = [
        "It is certain.",
        "It is decidedly so.",
        "Without a doubt.",
        "Yes definitely.",
        "You may rely on it.",
        "As I see it, yes.",
        "Most likely.",
        "Outlook good.",
        "Yes.",
        "Signs point to yes.",
        "Reply hazy, try again.",
        "Ask again later.",
        "Better not tell you now.",
        "Cannot predict now.",
        "Concentrate and ask again.",
        "Don't count on it.",
        "My reply is no.",
        "My sources say no.",
        "Outlook not so good.",
        "Very doubtful.",
    ]
    response = random.choice(responses)
    await interaction.response.send_message(f"Question: {question}\nAnswer: {response}")


@tree.command(name="dice", description="Roll a dice with a specified number of sides")
async def dice(interaction: discord.Interaction, sides: int = 6):
    if sides <= 0:
        await interaction.response.send_message(
            "Please provide a positive number of sides."
        )
        return

    result = random.randint(1, sides)
    await interaction.response.send_message(
        f"You rolled a {result} on a {sides}-sided dice."
    )


@tree.command(name="russianroulette", description="Play Russian Roulette")
async def russianroulette(interaction: discord.Interaction):
    result = random.choice(["Click!", "Bang!"])
    await interaction.response.send_message(f"You spun the chamber... {result}")
    if result == "Bang!":
        await interaction.user.timeout(
            datetime.timedelta(minutes=1), reason="Lost at Russian Roulette"
        )
        await interaction.followup.send(
            f"{interaction.user.mention} has been timed out for 1 minute!"
        )






@tree.command(name="sync", description="Sync the command tree")
async def sync(interaction: discord.Interaction):
    await tree.sync()
    await interaction.response.send_message("Command tree synced successfully!")
    print("Command tree synced successfully! (debug command)")


@app_commands.default_permissions(moderate_members=True)
@app_commands.checks.bot_has_permissions(moderate_members=True)
@tree.command(name="removetimeout", description="Remove a timeout from a user")
async def removetimeout(interaction: discord.Interaction, member: discord.Member):
    await member.timeout(None, reason=f"Timeout removed by {interaction.user}")
    await interaction.response.send_message(
        f"🔊 {member.mention}'s timeout has been removed."
    )

    embed = build_action_embed(
        "Timeout Removed",
        discord.Color.green(),
        interaction.user,
        f"{member.mention} ({member.id})",
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.bot_has_permissions(manage_messages=True)
@tree.command(
    name="purge", description="Purge a specified number of messages from the channel"
)
async def clear(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            "Please provide a positive number of messages to delete.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        await interaction.channel.purge(limit=amount + 1)
        await interaction.followup.send(
            f"🧹 Successfully deleted {amount} messages.", ephemeral=True
        )

        embed = build_action_embed(
            "Messages Purged",
            discord.Color.blue(),
            interaction.user,
            interaction.channel.mention,
            extra_fields=[("🔢 Amount", str(amount))],
        )
        await send_modlog(interaction.guild, embed)

    except discord.Forbidden:
        await interaction.followup.send(
            "🚫 I don't have permission to delete messages in this channel.",
            ephemeral=True,
        )


@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.bot_has_permissions(manage_messages=True)
@tree.command(
    name="purgeuser", description="Purge messages from a specific user in the channel"
)
async def clearuser(
    interaction: discord.Interaction, member: discord.Member, amount: int
):
    if amount <= 0:
        await interaction.response.send_message(
            "Please provide a positive number of messages to delete.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        deleted = await interaction.channel.purge(
            limit=amount + 1, check=lambda m: m.author == member
        )
        await interaction.followup.send(
            f"🧹 Successfully deleted {len(deleted)} messages from {member.mention}.",
            ephemeral=True,
        )

        embed = build_action_embed(
            "Member Messages Purged",
            discord.Color.blue(),
            interaction.user,
            interaction.channel.mention,
            extra_fields=[("🔢 Amount", str(amount))],
            target_member=member,
        )
        await send_modlog(interaction.guild, embed)

    except discord.Forbidden:
        await interaction.followup.send(
            "🚫 I don't have permission to delete messages in this channel.",
            ephemeral=True,
        )


@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.bot_has_permissions(manage_messages=True)
@tree.command(
    name="purgeimages", description="Purge messages containing images in the channel"
)
async def clearimages(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            "Please provide a positive number of images to delete.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        deleted = await interaction.channel.purge(
            limit=amount + 1, check=lambda m: len(m.attachments) > 0
        )
        await interaction.followup.send(
            f"🧹 Successfully deleted {len(deleted)} messages containing images.",
            ephemeral=True,
        )

        embed = build_action_embed(
            "Images Purged",
            discord.Color.blue(),
            interaction.user,
            interaction.channel.mention,
            extra_fields=[("🔢 Amount", str(amount))],
        )
        await send_modlog(interaction.guild, embed)

    except discord.Forbidden:
        await interaction.followup.send(
            "🚫 I don't have permission to delete messages in this channel.",
            ephemeral=True,
        )


@app_commands.default_permissions(manage_messages=True)
@app_commands.checks.bot_has_permissions(manage_messages=True)
@tree.command(
    name="purgelinks", description="Purge messages containing links in the channel"
)
async def clearlinks(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            "Please provide a positive number of messages to delete.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        deleted = await interaction.channel.purge(
            limit=amount + 1,
            check=lambda m: any(url in m.content for url in ["http://", "https://"]),
        )
        await interaction.followup.send(
            f"🧹 Successfully deleted {len(deleted)} messages containing links.",
            ephemeral=True,
        )

        embed = build_action_embed(
            "Links Purged",
            discord.Color.blue(),
            interaction.user,
            interaction.channel.mention,
            extra_fields=[("🔢 Amount", str(amount))],
        )
        await send_modlog(interaction.guild, embed)

    except discord.Forbidden:
        await interaction.followup.send(
            "🚫 I don't have permission to delete messages in this channel.",
            ephemeral=True,
        )


@tree.command(name="youtube", description="Get a link to the YouTube channel")
async def youtube(interaction: discord.Interaction):
    await interaction.response.send_message("https://www.youtube.com/@batbattlesrbx")


@app_commands.default_permissions(manage_nicknames=True)
@app_commands.checks.bot_has_permissions(manage_nicknames=True)
@tree.command(name="nick", description="Change a user's nickname")
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    
    if len(nickname) > 32 or len(nickname) < 1:
        await interaction.response.send_message(
            "Nicknames must be between 1 and 32 characters long.", ephemeral=True)
    if nickname == member.nick:
        await interaction.response.send_message(
            f"{member.mention} already has the nickname {nickname}.", ephemeral=True
        )
    else:
         await member.edit(nick=nickname)
         await interaction.response.send_message(
        f"Changed {member.mention}'s nickname to {nickname}."
    )

         embed = build_action_embed(
        "Nickname Changed",
        discord.Color.blue(),
        interaction.user,
        f"{member.mention} ({member.id})",
        extra_fields=[("🔤 New Nickname", nickname)],
        target_member=member,
    )

    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(manage_nicknames=True)
@app_commands.checks.bot_has_permissions(manage_nicknames=True)
@tree.command(name="resetnick", description="Reset a user's nickname")
async def resetnick(interaction: discord.Interaction, member: discord.Member):
    
    if member.nick == None:
        await interaction.response.send_message(
            f"{member.mention} already has their default nickname.", ephemeral=True
        )
    else:
        await member.edit(nick=None)
        await interaction.response.send_message(
        f"Reset {member.mention}'s nickname to their default.")

        embed = build_action_embed(
        "Nickname Reset",
        discord.Color.blue(),
        interaction.user,
        f"{member.mention} ({member.id})",
        target_member=member,
    )

    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(moderate_members=True)
@tree.command(name="warn", description="Warn a user")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    user_key = str(member.id)

    if user_key not in guild_data["warnings"]:
        guild_data["warnings"][user_key] = []

    now = discord.utils.utcnow()
    warning_entry = {
        "reason": reason,
        "moderator_id": interaction.user.id,
        "timestamp": int(now.timestamp()),
    }
    guild_data["warnings"][user_key].append(warning_entry)
    save_mod_data(data)

    await interaction.response.send_message(
        f"⚠️ {member.mention} has been warned for: {reason}"
    )

    embed = build_action_embed(
        "Member Warned",
        discord.Color.orange(),
        interaction.user,
        f"{member.mention} ({member.id})",
        reason,
        extra_fields=[
            ("📋 Total Warnings", str(len(guild_data["warnings"][user_key])))
        ],
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)



@app_commands.default_permissions(moderate_members=True)
@tree.command(name="editwarning", description="Edit a specific warning for a user")
async def editwarn(
    interaction: discord.Interaction,
    member: discord.Member,
    warning_number: int,
    new_reason: str,
):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    user_key = str(member.id)
    warnings = guild_data["warnings"].get(user_key, [])

    if not warnings:
        await interaction.response.send_message(
            f"❌ {member.mention} has no warnings to edit."
        )
        return

    if warning_number < 1 or warning_number > len(warnings):
        await interaction.response.send_message(
            f"❌ Invalid warning number. Please provide a number between 1 and {len(warnings)}."
        )
        return

    warnings[warning_number - 1]["reason"] = new_reason
    save_mod_data(data)
    await interaction.response.send_message(
        f"✅ Warning #{warning_number} for {member.mention} has been updated to: {new_reason}"
    )

    embed = build_action_embed(
        "Member Warning Edited",
        discord.Color.dark_orange(),
        interaction.user,
        f"{member.mention} ({member.id})",
        new_reason,
        extra_fields=[
            ("📋 Total Warnings", str(len(guild_data["warnings"][user_key])))
        ],
        target_member=member,
    )

    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(moderate_members=True)
@tree.command(name="clearwarning", description="Clear all warnings for a user")
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    user_key = str(member.id)

    if user_key in guild_data["warnings"]:
        guild_data["warnings"][user_key] = []
        save_mod_data(data)
        await interaction.response.send_message(
            f"✅ All warnings have been cleared for {member.mention}."
        )

    else:
        await interaction.response.send_message(
            f"❌ {member.mention} has no warnings to clear."
        )

    embed = build_action_embed(
        "Member Warnings Cleared",
        discord.Color.blurple(),
        interaction.user,
        f"{member.mention} ({member.id})",
        extra_fields=[
            ("📋 Total Warnings", str(len(guild_data["warnings"][user_key])))
        ],
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(moderate_members=True)
@tree.command(name="delwarning", description="Delete a specific warning for a user")
async def delwarn(
    interaction: discord.Interaction,
    member: discord.Member,
    warning_number: int,
    reason: str,
):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    user_key = str(member.id)
    warnings = guild_data["warnings"].get(user_key, [])

    if not warnings:
        await interaction.response.send_message(
            f"❌ {member.mention} has no warnings to delete."
        )
        return

    if warning_number < 1 or warning_number > len(warnings):
        await interaction.response.send_message(
            f"❌ Invalid warning number. Please provide a number between 1 and {len(warnings)}."
        )
        return

    deleted_warning = warnings.pop(warning_number - 1)
    save_mod_data(data)
    await interaction.response.send_message(
        f"✅ Warning #{warning_number} has been deleted for {member.mention}. Reason: {reason}"
    )

    embed = build_action_embed(
        "Member Warning Deleted",
        discord.Color.dark_red(),
        interaction.user,
        f"{member.mention} ({member.id})",
        reason,
        extra_fields=[
            ("📋 Total Warnings", str(len(guild_data["warnings"][user_key])))
        ],
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(moderate_members=True)
@tree.command(name="warnings", description="View the warnings for a user")
async def warnlogs(interaction: discord.Interaction, member: discord.Member):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    warnings = guild_data["warnings"].get(str(member.id), [])

    if not warnings:
        await interaction.response.send_message(
            f"✅ {member.mention} has no warnings on record."
        )
        return

    embed = discord.Embed(
        title=f"⚠️ Warning Logs — {member.display_name}",
        color=discord.Color.orange(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    for i, w in enumerate(warnings, start=1):
        moderator = interaction.guild.get_member(w.get("moderator_id"))
        moderator_str = (
            moderator.mention if moderator else f"<@{w.get('moderator_id')}>"
        )
        timestamp = w.get("timestamp")
        time_str = f"<t:{timestamp}:f>" if timestamp else "Unknown"
        embed.add_field(
            name=f"📌 Warning #{i}",
            value=f"**Reason:** {w.get('reason', 'No reason provided')}\n**Moderator:** {moderator_str}\n**Date:** {time_str}",
            inline=False,
        )

    embed.set_footer(text=f"Total warnings: {len(warnings)}")
    await interaction.response.send_message(embed=embed)


@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.bot_has_permissions(manage_channels=True)
@tree.command(name="getmodlogs", description="Get the current modlog channel")
async def getmodlogs(interaction: discord.Interaction):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    channel_id = guild_data.get("modlog_channel")

    if channel_id:
        channel = interaction.guild.get_channel(channel_id)
        if channel:
            await interaction.response.send_message(
                f"The current modlog channel is {channel.mention}."
            )
        else:
            await interaction.response.send_message(
                "The current modlog channel is set but no longer exists."
            )
            guild_data["modlog_channel"] = None
            save_mod_data(data)

    else:
        await interaction.response.send_message(
            "No modlog channel has been set for this server."
        )


@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.bot_has_permissions(manage_channels=True)
@tree.command(name="removemodlogs", description="Remove the current modlog channel")
async def removemodlogs(interaction: discord.Interaction):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    guild_data["modlog_channel"] = None
    save_mod_data(data)
    await interaction.response.send_message("The modlog channel has been removed.")


@app_commands.default_permissions(manage_channels=True)
@app_commands.checks.bot_has_permissions(manage_channels=True)
@tree.command(name="slowmode", description="Set slowmode for the current channel")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if seconds < 0:
        await interaction.response.send_message(
            "Slowmode must be a positive number of seconds.", ephemeral=True
        )
        return

    await interaction.channel.edit(slowmode_delay=seconds)

    if seconds == 0:
        await interaction.response.send_message(
            f"Slowmode has been disabled in this channel."
        )

    elif CommandInvokeError:
        await interaction.response.send_message(
            f"Slowmode cannot be set to {seconds} seconds. Please choose a number between 0 and 21600."
        )

    else:
        await interaction.response.send_message(
            f"Slowmode set to {seconds} seconds in this channel."
        )


@tree.command(name="randomuser", description="Get a random user from the server")
async def randomuser(interaction: discord.Interaction):
    members = [member for member in interaction.guild.members if not member.bot]
    if not members:
        await interaction.response.send_message("No users found in the server.")
        return

    random_member = random.choice(members)
    await interaction.response.send_message(f"Random user: {random_member.mention}")


@tree.command(name="echo", description="Make the bot say something")
async def echo(interaction: discord.Interaction, message: str):
    if "@everyone" in message or "@here" in message:
        await interaction.response.send_message(
            "You cannot mention everyone or here.", ephemeral=True
        )
        return
    else:
        await interaction.response.send_message(message)


@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@tree.command(name="addrole", description="Add a role to a user")
async def addrole(
    interaction: discord.Interaction, member: discord.Member, role: discord.Role
):
    

    if role in member.roles:
        await interaction.response.send_message(
            f"{member.mention} already has the {role.mention} role.", ephemeral=True
        )
    else:
        await member.add_roles(role)
        await interaction.response.send_message(
        f"Added {role.mention} to {member.mention}."
    )

        embed = build_action_embed(
        "Role Added",
        discord.Color.green(),
        interaction.user,
        f"{member.mention} ({member.id})",
        extra_fields=[("🎭 Role", role.mention)],
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(manage_roles=True)
@app_commands.checks.bot_has_permissions(manage_roles=True)
@tree.command(name="delrole", description="Delete roles from a user")
async def delrole(
    interaction: discord.Interaction, member: discord.Member, role: discord.Role
):

    if role not in member.roles:
        await interaction.response.send_message(
            f"{member.mention} does not have the {role.mention} role.", ephemeral=True
        )
    else:
        await member.remove_roles(role)
        await interaction.response.send_message(
        f"Removed {role.mention} from {member.mention}."
    )

        embed = build_action_embed(
        "Role Removed",
        discord.Color.red(),
        interaction.user,
        f"{member.mention} ({member.id})",
        extra_fields=[("🎭 Role", role.mention)],
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)



@app_commands.default_permissions(manage_channels=True)
@tree.command(
    name="setmodlogs", description="Set the channel where moderation logs will be sent"
)
@app_commands.describe(channel="The text channel to use for moderation logs")
async def setmodlogs(interaction: discord.Interaction, channel: discord.TextChannel):
    data = load_mod_data()
    guild_data = get_guild_data(data, interaction.guild.id)
    guild_data["modlog_channel"] = channel.id
    save_mod_data(data)

    await interaction.response.send_message(
        f"Moderation logs will now be sent to {channel.mention}."
    )



@app_commands.default_permissions(manage_messages=True)
@tree.command(name="poll", description="Create a poll with up to 10 options")
async def poll(interaction: discord.Interaction, question: str, options: str):
    options_list = [option.strip() for option in options.split(",") if option.strip()]

    if len(options_list) < 2:
        await interaction.response.send_message(
            "Please provide at least two options separated by commas.", ephemeral=True
        )
        return

    if len(options_list) > 10:
        await interaction.response.send_message(
            "You can only have up to 10 options.", ephemeral=True
        )
        return

    embed = discord.Embed(title=f"Poll: {question}", color=discord.Color.blue())

    for i, option in enumerate(options_list, start=1):
        embed.add_field(name=f"Option {i}", value=option, inline=False)

    now = interaction.created_at.astimezone(ZoneInfo("America/New_York"))

    embed.set_footer(
        text=f"Poll by {interaction.user.display_name} • {now.strftime('%m/%d/%y %H:%M:%S')}, EST"
    )

    await interaction.response.send_message(embed=embed)

    message = await interaction.original_response()

    for i in range(len(options_list)):
        await message.add_reaction(f"{i + 1}\u20e3")


@tree.command(name="ping", description="Check the bot's latency")
async def ping(interaction: discord.Interaction):
    latency_ms = round(client.latency * 1000)
    await interaction.response.send_message(f"Pong! Latency: {latency_ms}ms")


@tree.command(name="example", description="An example command")
async def example(interaction: discord.Interaction):
    await interaction.response.send_message("This is an example command.")
    

@app_commands.default_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@tree.command(name="ban", description="Bans a user from the server with a reason")
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):
    await member.ban(reason=reason)
    await interaction.response.send_message(
        f"🔨 {member.mention} has been banned. Reason: {reason}"
    )

    embed = build_action_embed(
        "Member Banned",
        discord.Color.red(),
        interaction.user,
        f"{member.mention} ({member.id})",
        reason,
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)


def parse_user_id(text: str):
    text = text.strip()
    mention_match = re.match(r"^<@!?(\d+)>$", text)
    if mention_match:
        return int(mention_match.group(1))
    if text.isdigit():
        return int(text)
    return None


@app_commands.default_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@tree.command(name="idban", description="Bans a user by ID")
async def banid(
    interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"
):
    try:
        user_id_int = int(user_id)
        user = await client.fetch_user(user_id_int)
        await interaction.guild.ban(user, reason=reason)
        await interaction.response.send_message(
            f"🔨 User with ID {user_id} has been banned. Reason: {reason}"
        )
        embed = build_action_embed(
            "Member Banned",
            discord.Color.red(),
            interaction.user,
            f"{user} ({user.id})",
            reason,
            target_member=user,
        )
        await send_modlog(interaction.guild, embed)

    except ValueError:
        await interaction.response.send_message(
            "Please provide a valid user ID.", ephemeral=True
        )

    except discord.NotFound:
        await interaction.response.send_message("User not found.", ephemeral=True)


@banid.autocomplete("user_id")
async def banid_autocomplete(interaction: discord.Interaction, current: str):
    if not current:
        return []

    try:
        user_id = int(current)
        return [app_commands.Choice(name=str(user_id), value=str(user_id))]

    except ValueError:
        return [app_commands.Choice(name="Invalid ID", value="invalid")]


@app_commands.default_permissions(ban_members=True)
@app_commands.checks.bot_has_permissions(ban_members=True)
@tree.command(
    name="unban",
    description="Unbans a user from the server by @mention, username, or user ID",
)
@app_commands.describe(
    user="The user to unban: an @mention, their username, or their user ID",
    reason="Reason for the unban",
)
async def unban(
    interaction: discord.Interaction, user: str, reason: str = "No reason provided"
):
    if interaction.guild is None:
        await interaction.response.send_message(
            "This command can only be used in a server.", ephemeral=True
        )
        return

    await interaction.response.defer()

    uid = parse_user_id(user)
    ban_entry = None

    if uid is not None:
        try:
            ban_entry = await interaction.guild.fetch_ban(discord.Object(id=uid))
        except discord.NotFound:
            ban_entry = None
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"Failed to look up ban: {e}", ephemeral=True
            )
            return

    if ban_entry is None:
        search_term = user.lstrip("@").lower()
        matches = []
        try:
            async for entry in interaction.guild.bans():
                banned_user = entry.user
                if (
                    banned_user.name.lower() == search_term
                    or (banned_user.global_name or "").lower() == search_term
                    or str(banned_user).lower() == search_term
                ):
                    matches.append(entry)
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"Failed to fetch ban list: {e}", ephemeral=True
            )
            return

        if len(matches) == 1:
            ban_entry = matches[0]
        elif len(matches) > 1:
            listing = "\n".join(
                f"- {entry.user} (ID: {entry.user.id})" for entry in matches[:10]
            )
            await interaction.followup.send(
                f"Multiple banned users match `{user}`. Please rerun with a specific user ID:\n{listing}",
                ephemeral=True,
            )
            return
        else:
            await interaction.followup.send(
                f"Couldn't find a banned user matching `{user}` by name. "
                f"Please provide their exact user ID instead (check the server's ban list if unsure).",
                ephemeral=True,
            )
            return

    try:
        await interaction.guild.unban(ban_entry.user, reason=reason)
    except discord.NotFound:
        await interaction.followup.send(
            "That user isn't banned or doesn't exist.", ephemeral=True
        )
        return
    except discord.HTTPException as e:
        await interaction.followup.send(f"Failed to unban user: {e}", ephemeral=True)
        return

    await interaction.followup.send(
        f"🕊️ User `{ban_entry.user}` (ID: {ban_entry.user.id}) has been unbanned. Reason: {reason}"
    )

    embed = build_action_embed(
        "Member Unbanned",
        discord.Color.green(),
        interaction.user,
        f"{ban_entry.user} ({ban_entry.user.id})",
        reason,
    )
    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(kick_members=True)
@app_commands.checks.bot_has_permissions(kick_members=True)
@tree.command(name="kick", description="Kicks a user from the server with a reason")
async def kick(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
):
    await member.kick(reason=reason)
    await interaction.response.send_message(
        f"👢 {member.mention} has been kicked. Reason: {reason}"
    )

    embed = build_action_embed(
        "Member Kicked",
        discord.Color.orange(),
        interaction.user,
        f"{member.mention} ({member.id})",
        reason,
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)


@app_commands.default_permissions(moderate_members=True)
@app_commands.checks.bot_has_permissions(moderate_members=True)
@tree.command(
    name="timeout",
    description="Times out a user for a set number of days, hours, and/or minutes",
)
@app_commands.describe(
    member="The member to time out",
    days="Number of days for the timeout",
    hours="Number of hours for the timeout",
    minutes="Number of minutes for the timeout",
    reason="Reason for the timeout",
)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    reason: str = "No reason provided",
):
    total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)

    if total_seconds <= 0:
        await interaction.response.send_message(
            "Please provide a duration greater than 0 (days, hours, and/or minutes).",
            ephemeral=True,
        )
        return

    duration = datetime.timedelta(seconds=total_seconds)

    if duration > datetime.timedelta(days=28):
        await interaction.response.send_message(
            "Timeouts cannot exceed 28 days.", ephemeral=True
        )
        return

    until = discord.utils.utcnow() + duration
    await member.timeout(until, reason=reason)

    duration_parts = []
    if days:
        duration_parts.append(f"{days}d")
    if hours:
        duration_parts.append(f"{hours}h")
    if minutes:
        duration_parts.append(f"{minutes}m")
    duration_str = " ".join(duration_parts)

    unban_timestamp = int(until.timestamp())
    await interaction.response.send_message(
        f"🔇 {member.mention} has been timed out for {duration_str}. "
        f"Reason: {reason}\n"
        f"Timeout ends <t:{unban_timestamp}:R> (<t:{unban_timestamp}:f>)."
    )

    embed = build_action_embed(
        "Member Timed Out",
        discord.Color.orange(),
        interaction.user,
        f"{member.mention} ({member.id})",
        reason,
        extra_fields=[
            ("⏱️ Duration", duration_str),
            ("⏰ Ends", f"<t:{unban_timestamp}:R>\n(<t:{unban_timestamp}:f>)"),
        ],
        target_member=member,
    )
    await send_modlog(interaction.guild, embed)



try:
    token = os.getenv("TOKEN") or "Place Your Token Here"
    if token == "":
        raise Exception("Please add your token to the Secrets pane.")
    client.run(token)
except discord.HTTPException as e:
    if e.status == 429:
        print("The Discord servers denied the connection for making too many requests")
        print("")
    else:
        raise e
