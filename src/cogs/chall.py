import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands 

from util.db import get_conn, Challenge

class Chall(commands.Cog):
    """
    Commands related to challenges.
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = get_conn()

    chall_group = SlashCommandGroup("chall", "Commands related to challenges", guild_ids=[946756291559301151, 801425873017503756, 877477283655450654])

    @chall_group.command(description="Add a challenge")
    async def add(
        self, ctx: discord.ApplicationContext,
        name: str,
        solved_by: discord.Option(discord.Member, "The user who solved this challenge", default=False),
    ):
        with self.db.transaction() as tx:
            root = tx.root()
            chall = Challenge(name=name, solved_by=solved_by)
            root.challs.append(chall)
            await ctx.send(f"Added challenge {name}.")
