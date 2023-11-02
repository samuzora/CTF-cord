import logging
from typing import Literal
import discord
from discord import guild_only
from discord.commands import SlashCommandGroup
from discord.ext import commands, pages
from sqlalchemy import and_, func, insert, select, update

from util.db import Ctf, User, get_all_challs_from_ctx, get_conn, Challenge, get_unsolved_challs_from_ctx


class Chall(commands.Cog):
    """
    Commands related to challenges
    """

    def __init__(self, bot):
        self.bot = bot

    chall_group = SlashCommandGroup(
        "chall",
        "Commands related to challenges",
        guild_ids=[946756291559301151, 801425873017503756, 877477283655450654],
    )

    @chall_group.command(description="Add members working on a challenge")
    @discord.option("member", type=discord.Member, description="Person working on challenge", default=None)
    @discord.option("overwrite", type=discord.SlashCommandOptionType.boolean, description="Replace all users working on the challenge with the specified member", default=False)
    @guild_only()
    async def workon(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        member: discord.Member | None,
        overwrite: bool = False,
    ):
        with get_conn() as conn:
            ctf = conn.scalar(
                select(Ctf)
                .where(Ctf.channel_id == ctx.channel_id)
            )
            if not ctf:
                return await ctx.respond("Channel not found", ephemeral=True)

            challenge = conn.scalar(
                select(Challenge)
                .join(Ctf)
                .where(and_(
                    Challenge.name == name, 
                    Ctf.channel_id == ctx.channel_id
                ))
            )

            if challenge:
                if challenge.solved:
                    return await ctx.respond("Challenge already solved", ephemeral=True)

                # check if challenge.worked_on is unchanged 
                # if unchanged, inform the user that the challenge is already added
                # if changed, append the user to workon (if overwrite then replace)
                member_id = member.id if member else ctx.author.id
                user = conn.scalar(
                    select(User).where(User.id == member_id)
                )
                if not user:
                    user = User(id=member_id)
                    conn.add(user)

                if overwrite:
                    # overwrite worked_on
                    challenge.worked_on = [user]
                    conn.commit()
                    return await ctx.respond(f"<@{member_id}> is working on `{name}`")
                elif member_id not in [user.id for user in challenge.worked_on]:
                    # append to worked_on
                    user = conn.scalar(
                        select(User).where(User.id == member_id)
                    )
                    if not user:
                        user = User(id=member_id)
                        conn.add(user)
                    old_worked_on = challenge.worked_on[:] # pass by value
                    challenge.worked_on.append(user)
                    conn.commit()
                    return await ctx.respond(f"<@{member_id}> is working on `{name}` together with {', '.join([f'<@{user.id}>' for user in old_worked_on])}")

                # unchanged, return error
                return await ctx.respond("Challenge already added", ephemeral=True)
            else:
                member_id = member.id if member else ctx.author.id
                user = conn.scalar(
                    select(User).where(User.id == member_id)
                )
                if not user:
                    user = User(id=member_id)
                    conn.add(user)

                challenge = Challenge(name=name, ctf=ctf, worked_on=[user])

                conn.add(challenge)
                conn.commit()
                await ctx.respond(f"<@{member_id}> is working on `{name}`")


    @chall_group.command(desription="Remove a challenge")
    @discord.option("name", type=str, autocomplete=get_all_challs_from_ctx)
    @guild_only()
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        name: str,
    ):
        with get_conn() as conn:
            challenge = conn.scalar(
                select(Challenge)
                .join(Challenge.ctf)
                .where(Challenge.name == name)
                .where(Ctf.channel_id == ctx.channel_id)
            )
            if not challenge:
                return await ctx.respond("Challenge not found", ephemeral=True)

            conn.delete(challenge)
            conn.commit()
            await ctx.respond(f"Challenge {challenge.name} removed")

    @chall_group.command(description="Solve challenge")
    @discord.option("name", type=str, autocomplete=get_unsolved_challs_from_ctx)
    @discord.option("member", type=discord.Member, description="Person who solved the challenge", default=None)
    @discord.option("overwrite", type=discord.SlashCommandOptionType.boolean, description="Replace all users working on the challenge with the specified member", default=False)
    @guild_only()
    async def solve(
        self,
        ctx: discord.ApplicationContext,
        name: str,
        flag: str,
        member: discord.Member | None,
        overwrite: bool = False,
    ):
        with get_conn() as conn:
            ctf = conn.scalar(
                select(Ctf)
                .where(Ctf.channel_id == ctx.channel_id)
           )
            if not ctf:
                return await ctx.respond("Channel not found", ephemeral=True)

            member_id = member.id if member else ctx.author.id
            user = conn.scalar(
                select(User).where(User.id == member_id)
            )
            if not user:
                user = User(id=member_id)
                conn.add(user)

            challenge = conn.scalar(
                select(Challenge)
                .join(Ctf)
                .where(Challenge.name == name)
                .where(Ctf.channel_id == ctx.channel_id)
            )
            if not challenge:
                challenge = Challenge(name=name, worked_on=[user], ctf=ctf)
                conn.add(challenge)
            if overwrite:
                challenge.solved_by = [user]
            else:
                challenge.solved_by = list(set([*challenge.worked_on, user])) # uniq
            challenge.solved = True
            challenge.flag = flag
            conn.commit()

            await ctx.respond(f"Challenge `{name}` solved by {', '.join([f'<@{user.id}>' for user in challenge.solved_by])}!")


    @chall_group.command(description="List challenges")
    @guild_only()
    async def list(self, ctx: discord.ApplicationContext):
        with get_conn() as conn:
            ctf = conn.scalar(
                select(Ctf)
                .where(Ctf.channel_id == ctx.channel_id)
            )
            if not ctf:
                return await ctx.respond("Channel not found", ephemeral=True)

            out: list[str] = [""]
            count = 0
            index = 0
            for c in ctf.challenges:
                count += 1
                if len(out[index]) > 3000:
                    index += 1
                    out.append("")

                if c.solved_by:
                    out[index] += f"{count}. {c.name}: `{c.flag}` (solved by {', '.join([f'<@{user.id}>' for user in c.solved_by])})\n"
                else:
                    out[index] += f"{count}. {c.name} ({', '.join([f'<@{user.id}>' for user in c.worked_on])} is working on)\n"

            paginator = pages.Paginator(pages=[discord.Embed(title="Challenges", description=c) for c in out])
            await paginator.respond(ctx.interaction, ephemeral=False)


def setup(bot):
    bot.add_cog(Chall(bot))
