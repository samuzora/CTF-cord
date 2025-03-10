import discord
from discord.ext import pages
from sqlalchemy import select

from util.db import get_conn, Challenge

async def get_challenge_paginator(ctx: discord.ApplicationContext, channel_id: int) -> pages.Paginator:
    with get_conn() as conn:
        challenges = conn.scalars(
            select(Challenge).where(Challenge.ctf.has(channel_id=channel_id)).order_by(Challenge.category)
        ).all()

        out: list[str] = [""]
        index = 0

        cur_cat = ""
        for c in challenges:
            if c.category != cur_cat:
                cur_cat = c.category
                out[index] += f"\n**{c.category}**\n"
            elif len(out[index]) > 3000:  # only if not new category - we don't want double headers
                index += 1
                out.append(f"\n**{c.category}**\n")

            # if thread exists, use the jump_url as title
            thread = ctx.bot.get_channel(c.thread_id)
            if not thread or type(thread) is not discord.Thread:
                if c.solved:
                    label = f"`{c.category}/{c.name} [SOLVED]`"
                else:
                    label = f"`{c.category}/{c.name}`"
            else:
                label = thread.jump_url

            user_list = "+".join([f"<@{user.id}>" for user in c.worked_on])

            if c.solved:
                out[index] += f"{label} ({user_list})\n"
            else:
                out[index] += f"{label} ({user_list})\n"

        paginator = pages.Paginator(pages=[discord.Embed(title="Challenges", description=c) for c in out])
        return paginator
