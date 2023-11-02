import logging
import os
import time
import traceback

import discord
from discord.ext import commands


token = os.environ.get("BOT_TOKEN")
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
    await bot.user.edit(username="CTF-cord")
    logging.info("Bot is running")


# Error handler
@bot.event
async def on_application_command_error(ctx, e):
    message = "Sorry, something went wrong."
    print(f'ERROR!\n----------\n{ctx.author.name} ({ctx.author.id}) at {time.strftime("%H%M")}:\n')
    traceback.print_exception(type(e), e, e.__traceback__)
    print("----------")
    await ctx.respond(message, ephemeral=True)


if __name__ == "__main__":
    bot.load_extension("cogs.ctf")
    bot.load_extension("cogs.dev")
    bot.load_extension("cogs.chall")
    # bot.load_extension("cogs.settings")
    bot.run(token)
