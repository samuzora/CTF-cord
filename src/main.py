import logging
import os
import time
import traceback

import discord
from discord import guild_only
from discord.ext import commands
from sqlalchemy import select

from util.db import get_conn, Ctf


username = os.environ.get("BOT_NAME", "CTF-cord v2")
token = os.environ.get("BOT_TOKEN")
dev_guild = os.environ.get("BOT_DEV_GUILD", None)
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(
    case_insensitive=True,
    description="CTF management Discord bot",
    intents=intents,
)

@bot.event
async def on_ready():
    assert bot.user is not None
    await bot.user.edit(username=username)
    logging.info("Bot is running")

# error fallback
@bot.event
async def on_application_command_error(ctx, e):
    message = "Sorry, something went wrong."
    print(f'ERROR!\n----------\n{ctx.author.name} ({ctx.author.id}) at {time.strftime("%H%M")}:\n')
    traceback.print_exception(type(e), e, e.__traceback__)
    print("----------")
    await ctx.respond(message, ephemeral=True)

@guild_only()
@bot.slash_command(description="Usage instructions", guild_ids=[int(dev_guild)] if dev_guild else None)
async def help(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="Usage",
        colour=discord.Colour.blurple()
    )

    if type(ctx.channel) is discord.Thread:
        channel = ctx.channel.parent
    else:
        channel = ctx.channel

    if channel is None:
        return await ctx.respond("Invalid channel!")

    with get_conn() as conn:
        ctf = conn.scalar(select(Ctf).where(Ctf.channel_id == channel.id))
        value = ""
        if not ctf:
            ctf_cog = ctx.bot.get_cog("ctf")
            assert ctf_cog is not None

            ctf_group = ctf_cog.get_commands()[0]
            assert type(ctf_group) is discord.SlashCommandGroup
            [ctf_details, ctf_add] = ctf_group.walk_commands()
            assert type(ctf_add) is discord.SlashCommand
            assert type(ctf_details) is discord.SlashCommand

            value += f"**Adding CTFs**\n"

            value += f"{ctf_details.mention}\n"
            value += "Scrape details from CTFtime and display in the channel."
            value += "\n\n"

            value += f"{ctf_add.mention}\n"
            value += "Create a private channel which participating members can opt-in to join, and a scheduled Discord \
            event based on the start and end time stated in CTFtime. Auto-generated credentials will be provided in \
            the private channel. Can only be invoked on CTFs that are not yet over."
        else:
            chall_cog = ctx.bot.get_cog("chall")
            assert chall_cog is not None

            chall_group = chall_cog.get_commands()[0]
            assert type(chall_group) is discord.SlashCommandGroup

            [chall_add, chall_remove, chall_solve, chall_lst] = chall_group.walk_commands()

            assert type(chall_add) is discord.SlashCommand
            assert type(chall_remove) is discord.SlashCommand
            assert type(chall_solve) is discord.SlashCommand
            assert type(chall_lst) is discord.SlashCommand

            value += "**Managing challenges**\n"
            value += "*In this channel and within challenge threads, you can invoke commands to manage challenges*"
            value += "\n\n"

            value += f"{chall_add.mention}\n"
            value += "Indicate yourself as working on a new challenge, and create a thread for it. If the challenge \
            has already been added, the `category` parameter can be omitted, and you will be added to the list of \
            people working on the challenge."
            value += "\n\n"

            value += f"{chall_solve.mention}\n"
            value += "Mark a challenge as solved. If the challenge has already been solved, you will be added to the \
            list of people who solved the challenge. If invoked in the challenge's thread, the `name` parameter is \
            optional. If the challenge has not been added before, the `category` parameter is required."
            value += "\n\n"

            value += f"{chall_lst.mention}\n"
            value += "View the current list of challenges in progress and challenges solved by category."
            value += "\n\n"

            value += f"{chall_remove.mention}\n"
            value += "Remove a challenge and delete its thread."

        embed.description = value

        await ctx.respond(embed=embed)

def cmd(cog: commands.Cog, command: str) -> discord.ApplicationCommand:
    available_commands = cog.get_commands()
    return [c for c in available_commands if c.qualified_name.split(" ")[-1] == command]

if __name__ == "__main__":
    bot.load_extension("cogs.ctf")
    bot.load_extension("cogs.dev")
    bot.load_extension("cogs.chall")

    bot.run(token)
