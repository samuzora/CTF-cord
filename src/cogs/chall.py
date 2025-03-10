import os
import random

import discord
from discord import guild_only
from discord.commands import SlashCommandGroup
from discord.ext import commands
from sqlalchemy import and_, select

from util.chall import get_challenge_paginator
from util.db import Ctf, User, get_all_challs_from_ctx, get_conn, Challenge, get_unsolved_challs_from_ctx

dev_guild = os.environ.get("BOT_DEV_GUILD", None)

class chall(commands.Cog):
    """
    Commands related to challenges
    """

    def __init__(self, bot):
        self.bot = bot

    chall_group = SlashCommandGroup(
        "chall",
        "Commands related to challenges",
        guild_ids=[int(dev_guild)] if dev_guild else None,
    )

    @chall_group.command(description="Add a new challenge, or work with someone else on an existing challenge")
    @discord.option("name", type=str, description="Challenge name")
    @discord.option(
        "category", type=str, description="Challenge category (required when adding new challenge)", default=None
    )
    @guild_only()
    async def add(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        category: str | None,
    ):
        with get_conn() as conn:
            ctf = conn.scalar(select(Ctf).where(Ctf.channel_id == ctx.channel_id))
            if not ctf:
                return await ctx.respond("Invalid channel!", ephemeral=True)

            challenge = conn.scalar(
                select(Challenge).join(Ctf).where(and_(Challenge.name == name, Ctf.channel_id == ctx.channel_id))
            )

            if challenge:
                if challenge.solved:
                    return await ctx.respond("Challenge already solved", ephemeral=True)

                # check if challenge.members is unchanged
                # if unchanged, inform the user that the challenge is already added
                # if changed, append the user to workon
                user = conn.scalar(select(User).where(User.id == ctx.author.id))
                if not user:
                    user = User(id=ctx.author.id)
                    conn.add(user)

                if ctx.author.id not in [user.id for user in challenge.members]:
                    # add to thread if thread exists
                    thread = ctx.bot.get_channel(challenge.thread_id)
                    if thread and type(thread) is discord.Thread:
                        await thread.add_user(ctx.author)

                    # append to members list
                    user = conn.scalar(select(User).where(User.id == ctx.author.id))
                    if not user:
                        user = User(id=ctx.author.id)
                        conn.add(user)
                    old_members_list = challenge.members[:]  # pass by value
                    challenge.members.append(user)
                    conn.commit()
                    user_list = "+".join([f"<@{user.id}>" for user in old_members_list])
                    await ctx.send(f"{ctx.author.mention} is working on `{name}` together with {user_list}")

                    paginator = await get_challenge_paginator(ctx, ctx.channel_id)
                    return await paginator.respond(ctx.interaction)

                # unchanged, return error
                return await ctx.respond("Challenge already added", ephemeral=True)
            else:
                if not category:
                    await ctx.respond("Category required for new challenge", ephemeral=True)
                    return

                user = conn.scalar(select(User).where(User.id == ctx.author.id))
                if not user:
                    user = User(id=ctx.author.id)
                    conn.add(user)

                _category = category.lower()

                thread_name = f"{_category}/{name}"
                message = await ctx.send(f"`{thread_name}`")
                thread = await message.create_thread(name=thread_name)
                await thread.add_user(ctx.author)

                challenge = Challenge(name=name, category=_category, ctf=ctf, members=[user], thread_id=thread.id)

                conn.add(challenge)
                conn.commit()

                return await ctx.respond(f"Challenge `{_category}/{name}` added", ephemeral=True)

    @chall_group.command(desription="Remove a challenge")
    @discord.option("name", type=str, autocomplete=get_all_challs_from_ctx)
    @guild_only()
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        name: str,
    ):
        with get_conn() as conn:
            if type(ctx.channel) is discord.Thread:
                channel = ctx.channel.parent
            else:
                channel = ctx.channel
            if type(channel) is not discord.TextChannel:
                return await ctx.respond("Invalid channel!")

            challenge = conn.scalar(
                select(Challenge)
                .join(Challenge.ctf)
                .where(Challenge.name == name)
                .where(Ctf.channel_id == channel.id)
            )
            if not challenge:
                return await ctx.respond(f"Challenge `{name}` not found", ephemeral=True)

            thread = ctx.bot.get_channel(challenge.thread_id)
            if thread and type(thread) == discord.Thread:
                await thread.delete()

            conn.delete(challenge)
            conn.commit()
            await ctx.respond(f"Challenge `{challenge.name}` removed", ephemeral=True)

            paginator = await get_challenge_paginator(ctx, ctf)
            return await paginator.respond(ctx.interaction, target=channel)

    @chall_group.command(description="Mark challenge as solved, or add yourself to the list of solvers")
    @discord.option(
        "name",
        type=str,
        autocomplete=get_unsolved_challs_from_ctx,
        description="Challenge name (if unspecified, inferred from the current challenge thread)",
        default=None,
    )
    @discord.option(
        "category", type=str, description="Category (required for new challenge, else ignored)", default=None
    )
    @guild_only()
    async def solve(
        self,
        ctx: discord.ApplicationContext,
        name: str | None,
        category: str | None,
    ):
        with get_conn() as conn:
            if type(ctx.channel) is discord.Thread:
                channel = ctx.channel.parent
                thread = ctx.channel
            elif type(ctx.channel) is discord.TextChannel:
                channel = ctx.channel
                thread = None
            else:
                return await ctx.respond("Invalid channel!", ephemeral=True)
            if type(channel) is not discord.TextChannel:
                return await ctx.respond("Invalid channel!")

            ctf = conn.scalar(select(Ctf).where(Ctf.channel_id == channel.id))
            if not ctf:
                return await ctx.respond("Invalid channel!", ephemeral=True)

            user = conn.scalar(select(User).where(User.id == ctx.author.id))
            if not user:
                user = User(id=ctx.author.id)
                conn.add(user)

            if name:
                challenge = conn.scalar(
                    select(Challenge).join(Ctf).where(Challenge.name == name).where(Ctf.channel_id == ctx.channel_id)
                )
            elif thread is not None:
                challenge = conn.scalar(
                    select(Challenge)
                    .join(Ctf)
                    .where(Challenge.thread_id == thread.id)
                    .where(Ctf.channel_id == channel.id)
                )
            else:
                return await ctx.respond(
                    "Challenge name required since command not invoked from challenge thread", ephemeral=True
                )

            if not challenge:
                if not category:
                    return await ctx.respond("Category required for new challenge", ephemeral=True)
                challenge = Challenge(name=name, members=[user], ctf=ctf, category=category.lower(), thread_id=0)
                conn.add(challenge)
            elif not challenge.solved:
                thread = ctx.bot.get_channel(challenge.thread_id)
                if thread and type(thread) is discord.Thread:
                    await thread.edit(name=f"{challenge.category}/{challenge.name} [SOLVED]")

                challenge.solved_by = list(set(challenge.members + [user])) # uniq
                challenge.solved = True
                conn.commit()

                emoji = random.choice([":partying_face:", ":fire:", ":tada:", ":confetti_ball:"])
                user_list = "+".join([f"<@{user.id}>" for user in challenge.solved_by])
                content = f"{emoji * 3} {user_list} solved `{challenge.category}/{challenge.name}`!"
                await ctx.send(content)
                # send the same message in the main ctf channel if currently in thread
                if thread is not None and type(channel) is discord.TextChannel:
                    await channel.send(content)

                # whether in thread or main channel, always send the chall list to the main channel
                paginator = await get_challenge_paginator(ctx, ctf)
                return await paginator.respond(ctx.interaction, target=channel)
            else:
                if user.id not in challenge.solved_by:
                    challenge.solved_by = challenge.solved_by + [user]
                    conn.commit()

                    emoji = random.choice([":partying_face:", ":fire:", ":tada:", ":confetti_ball:"])

                    user_list = "+".join([f"<@{user.id}>" for user in challenge.solved_by])
                    await ctx.send(f"{emoji * 3} {user_list} solved `{challenge.category}/{challenge.name}`!")
                    paginator = await get_challenge_paginator(ctx, channel.id)
                    return await paginator.respond(ctx.interaction, target=channel)
                else:
                    return await ctx.respond("You have already solved this challenge!", ephemeral=True)

    @chall_group.command(description="List challenges")
    @guild_only()
    async def list(self, ctx: discord.ApplicationContext):
        with get_conn() as conn:
            if type(ctx.channel) is discord.Thread:
                channel = ctx.channel.parent
            else:
                channel = ctx.channel
            if type(channel) is not discord.TextChannel:
                return await ctx.respond("Invalid channel!", ephemeral=True)

            ctf = conn.scalar(select(Ctf).where(Ctf.channel_id == channel.id))
            if not ctf:
                return await ctx.respond("Invalid channel!", ephemeral=True)

            paginator = await get_challenge_paginator(ctx, channel.id)
            await paginator.respond(ctx.interaction)


def setup(bot):
    bot.add_cog(chall(bot))
