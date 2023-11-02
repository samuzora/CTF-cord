import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands

from util.db import get_conn, Ctf


class Dev(commands.Cog):
    """
    Dev commands
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = get_conn()

    dev_group = SlashCommandGroup(
        "dev", "Dev commands", guild_ids=[946756291559301151, 801425873017503756, 877477283655450654]
    )

    @dev_group.command(description="Manually add a ctf channel")
    @discord.option("channel_id", type=discord.SlashCommandOptionType.integer, description="Channel ID")
    @discord.option("join_message_id", type=discord.SlashCommandOptionType.integer, description="Join message ID")
    async def add_channel(
        self,
        ctx: discord.ApplicationContext,
        channel_id: str,
        join_message_id: str,
    ):
        if not ctx.author.id == self.bot.owner_id:
            return await ctx.respond("Unauthorized", ephemeral=True)
        with get_conn() as conn:
            ctf = Ctf(channel_id=channel_id, join_message_id=join_message_id)
            conn.add(ctf)
            conn.commit()
            await ctx.respond("Added ctf", ephemeral=True)


def setup(bot):
    bot.add_cog(Dev(bot))
