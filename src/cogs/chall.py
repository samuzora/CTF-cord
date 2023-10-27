from typing import Literal
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands

from util.db import get_conn, Challenge


class Chall(commands.Cog):
    """
    Commands related to challenges
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = get_conn()

    chall_group = SlashCommandGroup(
        "chall",
        "Commands related to challenges",
        guild_ids=[946756291559301151, 801425873017503756, 877477283655450654],
    )

    @chall_group.command(description="Add a challenge")
    async def workon(
        self,
        ctx: discord.ApplicationContext,
        name: str,
    ):
        with self.db.transaction() as tx:
            root = tx.root()
            ctf = root.ctfs.get(ctx.channel_id)
            if not ctf:
                await ctx.respond("Channel not found", ephemeral=True)
                return

            if any(c.name == name for c in ctf.challenges):
                await ctx.respond("Challenge already added", ephemeral=True)
                return

            chall = Challenge(name=name, worked_on=ctx.author.id, solved_by=0)

            root.ctfs[ctx.channel_id].challenges.append(chall)
            await ctx.respond(f"{ctx.author.mention} is working on {name}")

    @chall_group.command(description="Solve challenge")
    async def solve(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        solved_by: discord.Member,
    ):
        with self.db.transaction() as tx:
            root = tx.root()
            ctf = root.ctfs.get(ctx.channel_id)
            if not ctf:
                await ctx.respond("Channel not found", ephemeral=True)
                return

            workon_id = 0
            chall = next((c for c in ctf.challenges if c.name == name), None)
            if not chall:
                workon_id = ctx.author.id
                chall = Challenge(name=name, worked_on=workon_id, solved_by=solved_by.id)
                ctf.challenges.append(chall)
            else:
                workon_id = chall.worked_on

            chall.solved_by = solved_by.id
            await ctx.respond(f"Challenge {name} solved by {solved_by.mention}!")

    @chall_group.command(description="List challenges")
    async def list(self, ctx: discord.ApplicationContext):
        with self.db.transaction() as tx:
            root = tx.root()
            ctf = root.ctfs.get(ctx.channel_id)
            if not ctf:
                await ctx.respond("Channel not found", ephemeral=True)
                return

            challs = ""
            for c in ctf.challenges:
                if c.solved_by:
                    challs += f"- {c.name} (solved by <@{c.solved_by}>)\n"
                else:
                    challs += f"- {c.name} (<@{c.worked_on}> is working on)\n"
            embed = discord.Embed(title="Challenges", description=challs)
            await ctx.respond(embed=embed)

def setup(bot):
    bot.add_cog(Chall(bot))
