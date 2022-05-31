import asyncio
import datetime
import json
import logging
import os
import time
import traceback

import discord
from discord.ext import commands, tasks
import mysql.connector

import config

token = os.environ.get("CTFCORD_BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.members = True


# config
bot = commands.Bot(
    case_insensitive=True,
    description="CTF-cord - the one-stop bot for CTF management!",
    intents=intents,
)


@bot.event
async def on_ready():
    await bot.user.edit(username='CTF-cord')
    print("Bot is ready.")

@bot.slash_command(description="Help command")
async def help(ctx):
    # Command list 
    description = \
"""Thank you for using CTF-cord! CTF-cord will help you to manage you and your team's CTF needs, as well as provide some utility helper functions.
With CTF-cord, you can pull data from CTFtime, automatically create Discord text channels and roles for each CTF (with appropriate perms), track challenge solves and more!

Here's a quickstart guide:
```
/ctf details ctftime_link:1616
```
This command will pull data from CTFtime and display it in an embed.
```
/ctf signup team_name:test ctftime_link:<whatever new ctfs are on ctftime>
```
This will pull the relevant info from CTFtime, and use it to send embeds and automatically create a Discord text channel, alongside a team role with access to this channel, and a scheduled Event in Discord.
```
/ctf unsignup
```
Invoke this in the created channel to delete the CTF.

There are some other features that are still under development.

Please please send me a PM on Discord or create an issue on Github if you find any bugs, it would help me a lot!

Have fun ~~reading documentation~~ using CTF-cord~
"""
    # Format embed
    embed = discord.Embed(
            title="CTF-cord",
            description=description,
            colour=discord.Colour.blurple(),
    )
    embed.url = "https://github.com/samuzora/CTF-cord"
    embed.set_footer(text="Click on the embed title to view the full list of commands!")
    await ctx.respond(embed=embed)

# Error handler
@bot.event
async def on_application_command_error(ctx, e):
    if isinstance(e, mysql.connector.Error):
        message = f"Sorry, a MySQL exception occurred. Please try again."
    else:
        message = f"Sorry, something went wrong. Please contact {(await bot.application_info()).owner.mention} for assistance."
        print(f'ERROR!\n----------\n{ctx.author.id} aka {ctx.author.name} at {time.strftime("%H%M")}:\n')
        traceback.print_exception(type(e), e, e.__traceback__)
        print("----------")
    await ctx.respond(message, ephemeral=True)


if __name__ == "__main__":
    bot.load_extension("cogs.ctf")
    bot.load_extension("cogs.chall")
    bot.load_extension("cogs.dev")
    bot.load_extension("cogs.settings")
    bot.run(token)
