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

token = os.environ.get("CTFLITE_BOT_TOKEN")
MYSQL_PW = os.getenv("MYSQL_PW")
default_prefix = ";"
logging.basicConfig(level=logging.INFO)

# Get prefix for current guild
async def get_prefix(bot, message):
    if message.guild:
        with mysql.connector.connect(
            host="127.0.0.1",
            port=3306,
            username="root",
            database="CTFlite",
            password=MYSQL_PW,
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
    description="8059blank.tk on Discord.",
)


@bot.event
async def on_ready():
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


# Help command implementation
class Help(commands.HelpCommand):
    def __config__(self):
        super().__config__()

    # Shown as default help
    async def send_bot_help(self, mapping):
        embed = discord.Embed(title="halp", colour=discord.Colour.blurple())
        embed.add_field(
            name=f"To find out more about a command, use {config.prefix}help <command>. eg:",
            value=f"```{config.prefix}help flag```",
        )
        for cog in mapping:
            if cog is not None:
                value = ""
                for command in mapping[cog]:
                    try:  # TODO: change from try to if
                        await command.can_run(self.context)
                    except:
                        value += f"❌ `{config.prefix}{command.name}`\n"
                    else:
                        value += f"✅ `{config.prefix}{command.name}`\n"
                embed.add_field(name=cog.qualified_name, value=value, inline=False)
        embed.set_footer(
            text="✅ indicates commands that you can run, while ❌ indicates commands that you cannot run in this context."
        )
        await self.get_destination().send(embed=embed)

    # Shown when user specfies a cog
    async def send_cog_help(self, cog):
        embed = discord.Embed(
            title=cog.qualified_name,
            description=cog.description,
            colour=discord.Colour.blurple(),
        )
        for command in cog.walk_commands():
            embed.add_field(
                name=f"{config.prefix}{command.name}", value=command.brief, inline=False
            )
        await self.get_destination().send(embed=embed)

    # Shown when user specifies a command
    async def send_command_help(self, command):
        embed = discord.Embed(
            title=command.name,
            description=command.description,
            colour=discord.Colour.blurple(),
        )
        embed.add_field(
            name="Usage",
            value=f"```{config.prefix}{command.name} {command.usage}```",
            inline=False,
        )
        await self.get_destination().send(embed=embed)


if __name__ == "__main__":
    bot.load_extension("cogs.ctf")
    bot.help_command = Help()
    bot.run(token)
