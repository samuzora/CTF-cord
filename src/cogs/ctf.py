from dateutil import parser
from datetime import datetime, timezone, timedelta
import pytz
import os

import discord
from discord import guild_only
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
from sqlalchemy import select

import util.ctf
from util.db import get_conn, Ctf

dev_guild = os.environ.get("DEV_GUILD", None)

class HumanReadableTime_to_Datetime(commands.Converter):
    async def convert(self, ctx, argument):
        date = parser.parse(argument)
        tz = pytz.timezone("Asia/Singapore")
        return tz.localize(date, is_dst=None)



class ctf(commands.Cog):
    """
    Commands related to CTFs.
    """

    timers = []

    def __init__(self, bot):
        self.bot = bot

    ctf_group = SlashCommandGroup(
        "ctf",
        "Commands related to CTFs",
        guild_ids=[int(dev_guild)] if dev_guild else None,
    )

    # TODO: rate limit this
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
                await channel.send(f"{user.mention} is joining the channel")
                await channel.set_permissions(user, view_channel=True)

    # TODO: rate limit this
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
                await channel.send(f"{user.mention} is leaving the channel")
                await channel.set_permissions(user, view_channel=False)

    # TODO: enumerate and show upcoming events
    @ctf_group.command(description="View details of a specific CTF")
    @discord.option(name="ctftime_link", type=str, description="CTFtime link of CTF")
    @guild_only()
    async def details(
        self, ctx: discord.ApplicationContext,
        ctftime_link: str
   ):
        # get ctf details
        event_info = await util.ctf.get_details(ctftime_link)
        if event_info is False:
            # ctf doesn't exist
            await ctx.respond("Invalid CTFtime event link/id", ephemeral=True)
            return

        embed = await util.ctf.details_to_embed(event_info)

        await ctx.respond(embed=embed)

    @ctf_group.command(description="Create channel for a CTF. The CTF end time must be in the future.")
    @discord.option(name="team_name", type=str, description="Team name")
    @discord.option(name="ctftime_link", type=str, description="CTFtime link or numeric ID")
    @guild_only()
    async def add(
        self, ctx: discord.ApplicationContext,
        team_name: str, ctftime_link: str
   ):
        # get ctf details
        event_info = await util.ctf.get_details(ctftime_link)
        if event_info is False:
            # ctf doesn't exist
            await ctx.respond("Invalid CTFtime event link/id", ephemeral=True)
            return

        now = datetime.now(timezone.utc) + timedelta(0, 10)

        # Check if timing is valid
        if now > event_info["finish"]:
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
            join_interaction = await ctx.send_response(embed=embed.set_footer(text="React with ✋ to join the channel."))
            join_msg = await join_interaction.original_response()
            await join_msg.add_reaction("✋")

            # create scheduled event
            start_time = event_info["start"]
            if event_info["start"] < now:
                start_time = now

            assert ctx.interaction.guild is not None
            await ctx.interaction.guild.create_scheduled_event(
                name=event_info["title"],
                start_time=start_time,
                end_time=event_info["finish"],
                location=join_msg.jump_url
            )

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


    @tasks.loop(seconds=1)
    async def timecheck_task(self):
        interval = timedelta(minutes=30)
        print(self.timers)

        self.timers = [i for i in self.timers if not i["expired"]]

        tz = pytz.timezone("Asia/Singapore")
        for event in self.timers:
            now = datetime.now(tz)

            if now >= event["end"]:
                await event["channel"].send("CTF has ended!")
                event["expired"] = True
                continue
            elif now >= event["start"] and event["last_pinged"] and now - event["last_pinged"] >= interval:
                event["last_pinged"] = now
                await event["channel"].send(f"CTF ends <t:{int(event["end"].timestamp())}:R>")
                continue
            # elif now >= event["start"] and event["last_pinged"] <= event["start"]:
            #     await event["channel"].send("CTF has started")
            #     continue


    @ctf_group.command(description="Set a recurring time check for an ongoing event.")
    async def timecheck(
        self, ctx: discord.ApplicationContext,
        start_time: HumanReadableTime_to_Datetime,
        end_time: HumanReadableTime_to_Datetime,
    ):
        tz = pytz.timezone("Asia/Singapore")
        self.timers.append({
            "start": start_time,
            "end": end_time,
            "channel": ctx.channel,
            "expired": False,
            "last_pinged": datetime.now(tz)
        })
        return await ctx.respond("Time check added", ephemeral=True)


def setup(bot):
    cog = ctf(bot)
    cog.timecheck_task.start()
    bot.add_cog(cog)
