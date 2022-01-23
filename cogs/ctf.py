import datetime
import json
import os
import time

import discord
from discord.ext import commands
import mysql.connector
import regex
import requests

import config


class CTF(commands.Cog):
    """ CTFs are managed here. With signup, you can register a CTF to take \
    part in, and never miss another CTF again with automatic Discord event \
    scheduling! To view details about a CTF, use the details command."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.command(
        brief="View details about an event, in a nicely formatted embed",
        description="This command allows you to view relevant information about"
                    "an event on CTFtime. Use this command with a CTFtime url "
                    "to the event, or just the event id.",
        usage="<ctftime event link>"
    )
    async def details(self, ctx, link):
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", link
        )
        if p is None and regex.match("[0-9]+", link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            # Search for the ID in link
            event = regex.search("[0-9]+", link)
            event_id = event.group()
            # Required, if not CTFtime will 403
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0",
            }
            # Get JSON via API
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                # ID is incorrect - got 404
                embed = discord.Embed(
                    title="Error!",
                    description="Sorry, this isn't a valid CTFtime event link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                # Parse the JSON
                event_json = req.content
                event_info = json.loads(event_json)
                title = event_info["title"]
                desc = event_info["description"]
                participants = event_info["participants"]
                # Timings are in ISO format - convert to datetime.datetime object
                start = datetime.datetime.fromisoformat(event_info["start"])
                finish = datetime.datetime.fromisoformat(event_info["finish"])
                # Refers to the event CTF url
                url = event_info["url"]
                logo_url = event_info["logo"]
                # Format embed
                embed = discord.Embed(title=title, description=desc, colour=discord.Colour.blurple())
                embed.set_thumbnail(url=logo_url)
                embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
                embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
                embed.add_field(name="CTFtime", value=f"<https://ctftime.org/event/{event_id}>")
                embed.set_footer(
                        text=f"{participants} participants"
                )
                embed.url = url
                # walrus kool :)
                if discord_inv := regex.search(
                    "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                    desc,
                ):
                    # Discord invite link found
                    embed.add_field(
                        name="Discord Server",
                        value=f"[Click here to join]({discord_inv.group()})",
                    )
        await ctx.send(embed=embed)

    @commands.command(
        brief="Sign up for an upcoming CTF",
        description="Registers an upcoming CTF to the bot. The bot will send a" \
                    "ping to all relevant team members when the CTF starts. "   \
                    "Note: this command does not actually sign you up for the"  \
                    "event, either on CTFtime or on the actual platform itself.",
        usage="<ctftime event link>"
    )
    async def signup(self, ctx, link):
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", link
        )
        if p is None and regex.match("[0-9]+", link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            # Try to grab the event ID from the link
            event = regex.search("[0-9]+", link)
            event_id = event.group()
            # Required, if not CTFtime will 403
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0)" \
                                "Gecko/20100101 Firefox/61.0",
            }
            # Get JSON via API
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                # Invalid event ID
                embed = discord.Embed(
                    title="Error!",
                    description="Sorry, this isn't a valid CTFtime event " \
                                "link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                # Parse JSON
                event_json = req.content
                event_info = json.loads(event_json)
                title = event_info["title"]
                desc = event_info["description"]
                if len(desc) > 4096:
                    desc = desc[:4092] + '...'
                participants = event_info["participants"]
                start = datetime.datetime.fromisoformat(event_info["start"])
                finish = datetime.datetime.fromisoformat(event_info["finish"])
                # Refers to the CTF link
                url = event_info["url"]
                logo_url = event_info["logo"]
                # Format embed
                embed = discord.Embed(title=title, description=desc)
                embed.set_thumbnail(url=logo_url)
                embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
                embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
                embed.add_field(name="CTFtime", value=f"https://ctftime.org/event/{event_id}")
                embed.set_footer(
                    text=f"{participants} participants"
                )
                embed.url = url
                if discord_inv := regex.search(
                    "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                    desc,
                ):
                    # Discord invite found
                    embed.add_field(
                        name="Discord Server",
                        value=f"[Click here to join]({discord_inv.group()})",
                    )
                # Add the ctf to the database
                with mysql.connector.connect(
                    host="127.0.0.1",
                    port=3306,
                    username="root",
                    database="ctfcord",
                    password=config.MYSQL_PW,
                ) as cnx:
                    cursor = cnx.cursor()
                    # Check if the user's team has registered this CTF already
                    cursor.execute(
                        "SELECT m.id FROM ctf AS c " \
                        "INNER JOIN team_members AS m ON c.team = m.id " \
                        "INNER JOIN teams AS t ON m.id = t.id " \
                        "WHERE t.guild = %s AND m.member = %s ",
                        (ctx.guild.id, ctx.author.id)
                    ) 
                    if (team_id := cursor.fetchone()) is None:
                        # CTF is already registered
                        # Update the relevant information in case it has changed
                        embed.colour = discord.Colour.blurple()
                        cursor.execute(
                            "UPDATE ctf AS c " \
                            "INNER JOIN team_members AS m ON c.team = m.id " \
                            "INNER JOIN teams AS t ON m.id = t.id " \
                            "SET c.description = %s, c.start = %s, c.finish = %s, c.discord = %s " \
                            "WHERE m.member = %s",
                            (
                                ctx.author.id,
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                discord_inv.group(),
                            )
                        )
                        await ctx.guild.create_scheduled_event(
                                name=title,
                                description=desc + f'\nCTFtime:\nhttps://ctftime.org/event/{event_id}',
                                start_time=start,
                                end_time=finish,
                                location=url
                        )
                    else:
                        # CTF not registered yet
                        embed.colour = discord.Colour.green()
                        cursor.execute(
                            "INSERT INTO ctf (id, title, description, start, finish, discord, team)" \
                            "SELECT %s, %s, %s, %s, %s, %s, id FROM team_members " \
                            "WHERE member = %s",
                            (
                                event_id,
                                title,
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                discord_inv.group(),
                                ctx.author.id
                            ),
                        ) 
                    # Commit changes
                    cnx.commit()
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(CTF(bot))
