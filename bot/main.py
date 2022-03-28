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
    # TODO: Change to dynamic (get info from cogs)
    command_list = \
    """`/ctf details <ctftime_link>` : View details about a CTF on CTFtime
    `/ctf signup <ctftime_link:optional>` : Register for a CTF and let the bot handle the rest. If ctftime_link not provided, a custom CTF event can be created.
    `/ctf unsignup <ctftime_link:optional>` : Un-register for a CTF. If ctftime_link not provided, the bot will try to infer the CTF if the command is invoked in the CTF channel. This is also the only way to delete custom CTFs.
    
    `/chall solved <chall_name> <chall_points:optional>` : Mark a challenge as solved and optionally specify the points the challenge is worth. 
    `/chall solving <chall_category> <chall_name>` : Create a thread for the challenge.

    `/team create <team_name>` : Create a team and assign a role to the team. To add others to your team, give them the same role. For now, you can only have 1 team per Discord Server.
    `/team delete` : Delete the team you are currently in. 
    """

    # Format embed
    embed = discord.Embed(
            title="CTF-cord",
            description=command_list,
            colour=discord.Colour.blurple(),
    )
    embed.url = "https://github.com/samuzora/CTF-cord"
    await ctx.respond(embed=embed)

# Error handler
@bot.event
async def on_application_command_error(ctx, e):
    if isinstance(e, mysql.connector.Error):
        message = f"Sorry, a MySQL exception occured. Please try again."
    else:
        message = f"Sorry, something went wrong. Please contact {(await bot.application_info()).owner.mention} for assistance."
        print(f'ERROR!\n----------\n{ctx.author.id} aka {ctx.author.name} at {time.strftime("%H%M")}:\n{(await ctx.interaction.original_message()).content}\n')
        traceback.print_exception(type(e), e, e.__traceback__)
        print("----------")
    await ctx.respond(message, ephemeral=True)


if __name__ == "__main__":
    bot.load_extension("cogs.ctf")
    bot.load_extension("cogs.teams")
    bot.load_extension("cogs.chall")
    bot.run(token)
