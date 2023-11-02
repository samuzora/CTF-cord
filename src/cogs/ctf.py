from datetime import datetime, timezone

import discord
from discord import guild_only
from discord.commands import SlashCommandGroup
from discord.ext import commands
from sqlalchemy import select

import util.ctf
from util.db import get_conn, Ctf


class CTF(commands.Cog):
    """
    Commands related to CTFs. Use /ctf register to register a new CTF.
    """

    def __init__(self, bot):
        self.bot = bot

    # --- slash command group ---
    ctf_group = SlashCommandGroup(
        "ctf",
        "Commands related to CTFs",
        guild_ids=[946756291559301151, 801425873017503756, 877477283655450654],
    )

    # --- add user to channel ---
    @commands.Cog.listener()
    @guild_only()
    async def on_raw_reaction_add(self, reaction: discord.RawReactionActionEvent):
        user = self.bot.get_user(reaction.user_id)
        if user.bot:
            return

        with get_conn() as conn:
            ctf = conn.scalar(select(Ctf).where(Ctf.join_message_id == reaction.message_id))
            if ctf is None:
                return

            channel = await self.bot.fetch_channel(ctf.channel_id)
            if channel is None:
                conn.delete(ctf)
            else:
                await channel.set_permissions(user, view_channel=True)

    # --- remove user from channel ---
    @commands.Cog.listener()
    @guild_only()
    async def on_raw_reaction_remove(self, reaction: discord.RawReactionActionEvent):
        user = self.bot.get_user(reaction.user_id)
        if user.bot:
            return

        with get_conn() as conn:
            ctf = conn.scalar(select(Ctf).where(Ctf.join_message_id == reaction.message_id))
            if ctf is None:
                return

            channel = await self.bot.fetch_channel(ctf.channel_id)
            if channel is None:
                conn.delete(ctf)
            else:
                await channel.set_permissions(user, view_channel=False)

    # --- /ctf register ---
    @ctf_group.command(description="Register for an upcoming CTF.")
    @discord.option(name="team_name", type=str, description="Your team name")
    @discord.option(name="ctftime_link", type=str, description="CTFtime link of CTF")
    @guild_only()
    async def register(
        self, ctx: discord.ApplicationContext,
        team_name: str, ctftime_link: str
   ):
        # get ctf details
        event_info = await util.ctf.get_details(ctftime_link)
        if event_info is False:
            # ctf doesn't exist
            await ctx.respond("Invalid CTFtime event link/id", ephemeral=True)
            return

        # Check if timing is valid
        if datetime.now(timezone.utc) > event_info["finish"]:
            # ctf has already ended
            await ctx.respond("CTF is over", ephemeral=True)
            return

        # create text channel for CTF
        with get_conn() as conn:
            channel = await util.ctf.create_channel(ctx, event_info)

            if channel is None:
                await ctx.respond("Error creating channel", ephemeral=True)
                return

            embed = await util.ctf.details_to_embed(event_info)
            join_interaction = await ctx.send_response(embed=embed)
            join_msg = await join_interaction.original_response()
            await join_msg.add_reaction("✋")

            ctf = Ctf(channel_id=channel.id, join_message_id=join_msg.id)
            conn.add(ctf)

            # edit embed to include creds
            password = await util.ctf.generate_creds()
            embed.add_field(
                name="Credentials",
                value=f"Team name: `{team_name}`\nPassword: `{password}`",
            )
            private_msg = await channel.send(embed=embed)
            await private_msg.pin()

            conn.commit()


# --- load cog ---
def setup(bot):
    bot.add_cog(CTF(bot))
