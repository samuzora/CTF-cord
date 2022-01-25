import datetime
import json
import os
import time

import discord
from discord.commands import slash_command
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

    @slash_command(
            guild_ids=config.beta_guilds,
            description="View details about an event in a nicely formatted embed."
    )
    async def details(self, ctx, ctftime_link: str):
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", ctftime_link
        )
        if p is None and regex.match("[0-9]+", ctftime_link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            # Search for the ID in link
            event = regex.search("[0-9]+", ctftime_link)
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
        await ctx.respond(embed=embed)

    @slash_command(
            guild_ids=config.beta_guilds,
            description="Sign up for an upcoming CTF, and register it to the bot."
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
                        "SELECT t.id FROM ctf AS c " \
                        "INNER JOIN team_members AS m ON c.team = m.team " \
                        "INNER JOIN teams AS t ON m.team = t.id " \
                        "WHERE c.id = %s AND t.guild = %s AND m.member = %s",
                        (event_id, ctx.guild.id, ctx.author.id)
                    ) 
                    if (team_id := cursor.fetchone()) is not None:
                        # CTF is already registered
                        # Change embed colour to blurple as a hint to the user. Does not create a new field in the embed as this is non-essential
                        embed.colour = discord.Colour.blurple()
                        # Update the relevant information in case it has changed
                        cursor.execute(
                            "UPDATE ctf AS c " \
                            "INNER JOIN team_members AS m ON c.team = m.team " \
                            "INNER JOIN teams AS t ON m.team = t.id " \
                            "SET c.description = %s, c.start = %s, c.finish = %s, c.discord = %s " \
                            "WHERE m.member = %s",
                            (
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                discord_inv.group(),
                                ctx.author.id
                            )
                        )
                    else:
                        # CTF not registered yet
                        # Green to inform the user that the CTF has been added successfully
                        embed.colour = discord.Colour.green()
                        # Create scheduled event
                        scheduled_event = await ctx.guild.create_scheduled_event(
                                name=title,
                                description=desc + f'\nCTFtime:\nhttps://ctftime.org/event/{event_id}',
                                start_time=start,
                                end_time=finish,
                                location=url
                        )
                        # Add CTF into db
                        cursor.execute(
                                "INSERT INTO ctf (id, title, description, start, " \
                                    "finish, discord, team, scheduled_event) " \
                                "SELECT %s, %s, %s, %s, %s, %s, t.id, %s FROM teams AS t " \
                                "INNER JOIN team_members AS m ON m.team = t.id " \
                                "WHERE m.member = %s ",
                            (
                                event_id,
                                title,
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                discord_inv.group(),
                                scheduled_event.id,
                                ctx.author.id
                            )
                        ) 
                        # Create new text channel for the CTF
                        # Get list of members to update perms for channel
                        # Default perms to view_channel = False
                        perms = {
                                ctx.guild.default_role: \
                                        discord.PermissionOverwrite(view_channel=False),
                                ctx.guild.me: \
                                        discord.PermissionOverwrite(view_channel=True)

                        }
                        # Get user's team
                        cursor.execute(
                                'SELECT t.id FROM team_members AS m '\
                                'INNER JOIN teams AS t ON t.id = m.team '\
                                'WHERE t.guild = %s AND m.member = %s',
                                (ctx.guild.id, ctx.author.id)
                        )
                        team_id = cursor.fetchone()[0]
                        # Get all members in team
                        cursor.execute(
                                'SELECT member FROM team_members '\
                                'WHERE team = %s',
                                (team_id,)
                        )
                        members = cursor.fetchall()
                        for member in members:
                            member_id = member[0]
                            perms[ctx.guild.get_member(member_id)] = \
                                    discord.PermissionOverwrite(view_channel=True)
                        # Check if CTF category exists
                        cursor.execute(
                                'SELECT t.ctf_category FROM teams AS t ' \
                                'INNER JOIN team_members AS m ON t.id = m.team ' \
                                'WHERE m.member = %s',
                                (ctx.author.id,)
                        )
                        if (ctf_category := cursor.fetchone()) is None \
                                or ctx.guild.get_channel(ctf_category[0]) not in ctx.guild.categories:
                            # Category does not exist, create it first
                            ctf_category = await ctx.guild.create_category_channel('CTFs')          
                            cursor.execute(
                                    'UPDATE teams SET ctf_category = %s '\
                                    'WHERE id = %s',
                                    (ctf_category.id, team_id)
                            )
                        else:
                            ctf_category = ctx.guild.get_channel(ctf_category[0])
                        # Create channel
                        ctf_channel = await ctx.guild.create_text_channel(
                                title,
                                overwrites=perms,
                                category=ctf_category
                        ) 
                        # Save channel in db
                        cursor.execute(
                                'UPDATE ctf SET channel = %s '\
                                'WHERE id = %s',
                                (ctf_channel.id, event_id)
                        )
                    # Commit changes
                    cnx.commit()
        await ctx.respond(embed=embed)

    @slash_command(
            guild_ids=config.beta_guilds,
            description="Un-signup for a CTF, unregistering it from the bot."
    )
    async def unsignup(self, ctx, ctftime_link: str):
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", ctftime_link
        )
        if p is None and regex.match("[0-9]+", ctftime_link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            # Try to grab the event ID from the link
            event = regex.search("[0-9]+", ctftime_link)
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
                with mysql.connector.connect(
                        host='127.0.0.1',
                        port=3306,
                        database='ctfcord',
                        username='root',
                        password=config.MYSQL_PW
                ) as cnx:
                    cursor = cnx.cursor()
                    # Check if the team has registered this CTF
                    cursor.execute(
                            'SELECT t.id FROM ctf AS c ' \
                            'INNER JOIN teams AS t ON c.team = t.id ' \
                            'INNER JOIN team_members AS m ON t.id = m.team ' \
                            'WHERE c.id = %s AND t.guild = %s AND m.member = %s',
                            (event_id, ctx.guild.id, ctx.author.id)
                    )
                    if (team_id := cursor.fetchone()) is not None:
                        # Team has registered this CTF
                        # Parse JSON
                        event_json = req.content
                        event_info = json.loads(event_json)
                        title = event_info["title"]
                        desc = event_info["description"]
                        if len(desc) > 4096:
                            desc = desc[:4093] + '...'
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
                            desc
                        ):
                            # Discord invite found
                            embed.add_field(
                                name="Discord Server",
                                value=f"[Click here to join]({discord_inv.group()})"
                            )
                        # Delete scheduled event
                        cursor.execute(
                                'SELECT c.scheduled_event FROM ctf AS c ' \
                                'INNER JOIN teams AS t ON c.team = t.id ' \
                                'WHERE c.id = %s',
                                (event_id,)
                        )
                        scheduled_event = ctx.guild.get_scheduled_event(cursor.fetchone()[0])
                        try:
                            await scheduled_event.delete()
                        except:
                            embed.add_field(
                                name="Scheduled Discord event",
                                value="The event could not be found, please try deleting it manually."
                            )
                            embed.colour = discord.Colour.blurple()
                        else:
                            embed.colour = discord.Colour.green()
                        # Delete CTF channel
                        cursor.execute(
                                'SELECT channel FROM ctf '\
                                'WHERE team = %s AND id = %s',
                                (team_id[0], event_id)
                        )
                        channel = ctx.guild.get_channel(cursor.fetchone()[0])
                        try:
                            await channel.delete()
                        except NotFound:
                            pass
                        # Delete CTF from db
                        cursor.execute(
                                'DELETE FROM ctf WHERE team = %s AND id = %s',
                                (team_id[0], event_id)
                        )
                        cnx.commit()
                    else:
                        embed = discord.Embed(
                                title="Error!",
                                description="Sorry, you have not signed up " \
                                            "for this event.",
                                colour=discord.Colour.red()
                                )

            await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(CTF(bot))
