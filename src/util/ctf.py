from datetime import datetime
import json
import secrets
from typing import TypedDict

import discord
import regex
import requests

class TempEventInfo(TypedDict):
    id: int
    title: str
    description: str
    url: str
    logo: str
    start: str
    finish: str

class EventInfo(TypedDict):
    id: int
    title: str
    description: str
    url: str
    logo: str
    start: datetime
    finish: datetime
    discord_inv: str | None


# --- get CTF details ---
async def get_details(ctftime_link: str) -> EventInfo | bool:
    # Check whether the link is valid
    check = regex.search("[0-9]+", ctftime_link)
    if check is None:
        # The link is not valid
        return False
    else:
        event_id = check.group()

    # Grab data via API
    req = requests.get(
        f"https://ctftime.org/api/v1/events/{event_id}/",
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"
        },  # CTFtime will 403 if this is not added
    )
    if req.status_code == 404:
        # CTFtime returned 404
        return False

    # ID is valid
    temp_event_info: TempEventInfo = json.loads(req.content)
    event_info: EventInfo = {
        "id": temp_event_info["id"],
        "title": temp_event_info["title"],
        "description": temp_event_info["description"] if len(temp_event_info["description"]) <= 1000 else temp_event_info["description"][:997] + "...",
        "url": temp_event_info["url"],
        "logo": temp_event_info["logo"],
        "start": datetime.fromisoformat(temp_event_info["start"]),
        "finish": datetime.fromisoformat(temp_event_info["finish"]),
        "discord_inv": None,
    }
    if (
        a := regex.search(
            "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
            event_info["description"],
        )
    ) is not None:
        event_info["discord_inv"] = a.group(0)
    else:
        event_info["discord_inv"] = None
    return event_info


# --- format event details into embed ---
async def details_to_embed(event_info: EventInfo) -> discord.Embed:
    embed = discord.Embed(
        title=event_info["title"],
        description=event_info["description"],
        colour=discord.Colour.blurple(),
    )
    embed.set_thumbnail(url=event_info["logo"])
    embed.add_field(
        name="Starts at",
        value=discord.utils.format_dt(event_info["start"]),
    )
    embed.add_field(
        name="Ends at",
        value=discord.utils.format_dt(event_info["finish"]),
    )
    embed.add_field(
        name="CTFtime",
        value=f'<https://ctftime.org/event/{event_info["id"]}>',
    )
    embed.url = event_info["url"]
    if event_info.get("discord_inv") is not None:
        embed.add_field(
            name="Discord Server",
            value=f"<{event_info['discord_inv']}>",
        )
    embed.set_footer(text="React with ✋ to join the channel.")
    return embed


async def generate_creds() -> str:
    return secrets.token_urlsafe(20)


# --- create Discord channel ---
async def create_channel(ctx: discord.ApplicationContext, event_info: EventInfo) -> discord.TextChannel:
    # create channel and assign perms
    perms = {
        ctx.guild.default_role: discord.PermissionOverwrite(view_channel=False),
        ctx.guild.me: discord.PermissionOverwrite(view_channel=True),
        # don't add the author - react to the message to join
        # ctx.author: discord.PermissionOverwrite(view_channel=True),
    }

    # Create channel
    ctf_channel = await ctx.guild.create_text_channel(
        event_info["title"],
        topic=event_info["url"],
        overwrites=perms,
    )

    return ctf_channel
