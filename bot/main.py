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
default_prefix = ";"
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.members = True

# Get prefix for current guild
async def get_prefix(bot, message):
    if message.guild:
        with mysql.connector.connect(
            host=config.MYSQL_DB,
            port=3306,
            username="root",
            database="ctfcord",
            password=config.MYSQL_PW,
        ) as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                "SELECT prefix FROM guilds WHERE id = %s", (message.guild.id,)
            )
            config.prefix = cursor.fetchone()
            if config.prefix is None:
                config.prefix = default_prefix
            else:
                config.prefix = config.prefix[0]
    else:
        config.prefix = default_prefix
    return config.prefix


# config
bot = commands.Bot(
    command_prefix=get_prefix,
    case_insensitive=True,
    description="CTF-cord - the one-stop bot for CTF management!",
    intents=intents
)


@bot.event
async def on_ready():
    await bot.user.edit(username='CTF-cord')
    print("Bot is ready.")


# Error handler
@bot.event
async def on_command_error(ctx, e):
    if isinstance(e, commands.errors.PrivateMessageOnly):
        embed = discord.Embed(
            title="Usage error",
            description="This command can only be used in a DMChannel.",
            colour=discord.Colour.red(),
        )
    elif isinstance(e, commands.errors.MissingRequiredArgument):
        embed = discord.Embed(
            title="Missing arguments",
            description=f"You are missing some arguments, please use {config.prefix}help <command> to view the syntax.",
            colour=discord.Colour.red(),
        )
    elif isinstance(e, commands.errors.NoPrivateMessage):
        embed = discord.Embed(
            title="Usage error",
            description="This command can only be used in a guild.",
            colour=discord.Colour.red(),
        )
    elif isinstance(e, commands.errors.CheckFailure):
        embed = discord.Embed(
            title="Insufficient permissions!",
            description=f"Sorry, you don't have the proper administrative rights to run this command. This could be because you are not an admin and are trying to use an admin command, or you haven't bound your account to the bot yet. To do so, check `{config.prefix}help bind`.",
            colour=discord.Colour.red(),
        )
    elif isinstance(e, mysql.connector.Error):
        embed = discord.Embed(
            title="SQL Exception",
            description="Sorry, an SQL exception occured.",
            colour=discord.Colour.red(),
        )
    elif isinstance(e, commands.CommandNotFound):
        return
    else:
        embed = discord.Embed(
            title="Error!",
            description="Sorry, something went wrong. Please contact an admin for assistance.",
            colour=discord.Colour.red(),
        )
        print(
            f'ERROR!\n----------\n{ctx.author.id} aka {ctx.author.name} at {time.strftime("%H%M")}:\n{ctx.message.content}\n'
        )
        traceback.print_exception(type(e), e, e.__traceback__)
        print("----------")
    await ctx.send(embed=embed)


if __name__ == "__main__":
    bot.load_extension("cogs.ctf")
    bot.load_extension("cogs.teams")
    bot.load_extension("cogs.chall")
    bot.run(token)
