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

MYSQL_PW = os.getenv("MYSQL_PW")


class CTF(commands.Cog):
    """Commands to manage CTFs, useful for team organization"""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    @commands.command(
        brief="View details about an event, in a nicely formatted embed",
        description="This command allows you to view relevant information about an event on CTFtime. Use this command with a CTFtime url to the event, or just the event id.",
        usage="<ctftime event link>"
    )
    async def details(self, ctx, link):
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", link
        )
        if p is None and regex.match("[0-9]+", link) is None:
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            event = regex.search("[0-9]+", link)
            event_id = event.group()
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0",
            }
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                embed = discord.Embed(
                    title="Error!",
                    description="Sorry, this isn't a valid CTFtime event link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                event_json = req.content
                event_info = json.loads(event_json)
                title = event_info["title"]
                desc = event_info["description"]
                start = datetime.datetime.fromisoformat(event_info["start"])
                finish = datetime.datetime.fromisoformat(event_info["finish"])
                url = event_info["url"]
                logo_url = event_info["logo"]
                embed = discord.Embed(title=title, description=desc, colour=discord.Colour.blurple())
                embed.set_thumbnail(url=logo_url)
                embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
                embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
                embed.set_footer(
                    text="Click on the event title to go to the event site!"
                )
                embed.url = url
                if discord_inv := regex.search(
                    "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                    desc,
                ):
                    embed.add_field(
                        name="Discord Server",
                        value=f"[Click here to join]({discord_inv.group()})",
                    )
        await ctx.send(embed=embed)

    @commands.command(
        brief="Sign up for an upcoming CTF",
        description="Registers an upcoming CTF to the bot. The bot will send a ping to all relevant team members when the CTF starts. Note: this command does not actually sign you up for the event, either on CTFtime or on the actual platform itself.",
        usage="<ctftime event link>"
    )
    async def signup(self, ctx, link):
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", link
        )
        if p is None and regex.match("[0-9]+", link) is None:
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            event = regex.search("[0-9]+", link)
            event_id = event.group()
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0",
            }
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                embed = discord.Embed(
                    title="Error!",
                    description="Sorry, this isn't a valid CTFtime event link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                event_json = req.content
                event_info = json.loads(event_json)
                title = event_info["title"]
                desc = event_info["description"]
                start = datetime.datetime.fromisoformat(event_info["start"])
                finish = datetime.datetime.fromisoformat(event_info["finish"])
                url = event_info["url"]
                logo_url = event_info["logo"]
                embed = discord.Embed(title=title, description=desc)
                embed.set_thumbnail(url=logo_url)
                embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
                embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
                embed.set_footer(
                    text="Click on the event title to go to the event site!"
                )
                embed.url = url
                if discord_inv := regex.search(
                    "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                    desc,
                ):
                    embed.add_field(
                        name="Discord Server",
                        value=f"[Click here to join]({discord_inv.group()})",
                    )
                with mysql.connector.connect(
                    host="127.0.0.1",
                    port=3306,
                    username="root",
                    database="ctflite",
                    password=MYSQL_PW,
                ) as cnx:
                    cursor = cnx.cursor()
                    cursor.execute(
                        "SELECT 1 FROM ctf WHERE id = %s AND team = %s",
                        (event_id, ctx.author.id),
                    )  # TODO: implement teams
                    if cursor.fetchone() is not None:
                        cursor.execute(
                            "UPDATE ctf SET description = %s, start = %s, finish = %s, discord = %s",
                            (
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                ctx.author.id,
                            ),
                        )  # TODO: implement teams
                        embed.colour = discord.Colour.blurple()
                    else:
                        cursor.execute(
                            "INSERT INTO ctf VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (
                                event_id,
                                title,
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                discord_inv.group(),
                                ctx.author.id,
                            ),
                        )  # TODO: implement teams
                        embed.colour = discord.Colour.green()
                    cnx.commit()
        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(CTF(bot))
