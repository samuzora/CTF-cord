from typing import Literal
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, pages

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
    @discord.option("member", type=discord.Member, description="Member working on challenge", default=None)
    async def workon(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        member: discord.Member | None,
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

            worked_on = member.id if member else ctx.author.id
            chall = Challenge(name=name, worked_on=worked_on)

            root.ctfs[ctx.channel_id].challenges.append(chall)
            await ctx.respond(f"<@{worked_on}> is working on {name}")

    @chall_group.command(description="Solve challenge")
    async def solve(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        flag: str,
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
                chall = Challenge(name=name, worked_on=workon_id)
                chall.solve(solved_by=workon_id, flag=flag)
                ctf.challenges.append(chall)
            else:
                chall.solve(solved_by=chall.worked_on, flag=flag)

            await ctx.respond(f"Challenge {name} solved by <@{chall.solved_by}>!")

    @chall_group.command(description="List challenges")
    async def list(self, ctx: discord.ApplicationContext):
        with self.db.transaction() as tx:
            root = tx.root()
            ctf = root.ctfs.get(ctx.channel_id)
            if not ctf:
                await ctx.respond("Channel not found", ephemeral=True)
                return

            challs = [""]
            page = 0
            for c in ctf.challenges:
                if len(challs[page]) > 3000:
                    page += 1
                    challs[page] = ""
                if c.solved_by:
                    challs[page] += f"- {c.name}: `{c.flag}` (solved by <@{c.solved_by}>)\n"
                else:
                    challs[page] += f"- {c.name} (<@{c.worked_on}> is working on)\n"

            paginator = pages.Paginator(pages=[discord.Embed(title="Challenges", description=c) for c in challs])
            await paginator.respond(ctx.interaction, ephemeral=False)

def setup(bot):
    bot.add_cog(Chall(bot))
