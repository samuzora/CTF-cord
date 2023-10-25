import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands 

from util.db import get_conn, Ctf

class Dev(commands.Cog):
    """
    Dev commands
    """

    def __init__(self, bot):
        self.bot = bot
        self.db = get_conn()

    dev_group = SlashCommandGroup("dev", "Dev commands", guild_ids=[946756291559301151, 801425873017503756, 877477283655450654])

    @dev_group.command(description="Manually add a ctf channel")
    async def add_channel(
        self, ctx: discord.ApplicationContext,
        channel_id: str,
        join_message_id: str,
    ):
        __channel_id = int(channel_id)
        __join_message_id = int(join_message_id)
        if not ctx.author.id == 638306658858172416:
            return await ctx.respond("You are not allowed to do that", ephemeral=True)
        with self.db.transaction() as tx:
            root = tx.root()
            ctf = Ctf(channel_id=__channel_id, join_message_id=__join_message_id)
            root.ctfs[__channel_id] = ctf
        await ctx.respond("Added ctf", ephemeral=True)

def setup(bot):
    bot.add_cog(Dev(bot))
