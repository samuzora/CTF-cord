import datetime
import json
import os
import time

import discord
from discord.commands import slash_command, SlashCommandGroup
from discord.ext import commands, tasks
import mysql.connector
import regex
import requests

import config

class Challenges(commands.Cog):
    """ This group of commands allows you to manage challenges during a CTF. \
    Not only can you keep track of challenges in progress, you can also mark \
    them as solved, which allocates points to you and tracks your contribution \
    to the team. """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    chall = SlashCommandGroup('chall', 'Group of commands relating to challenges', guild_ids=config.beta_guilds)
    
    @chall.command(
            description="Mark a challenge as in progress."
    )
    async def solving(self, ctx, chall_name: str):
        embed = discord.Embed(
                title=chall_name,
                description=f'{ctx.author.mention} is working on {chall_name}!'
                )
        r = await ctx.respond(embed=embed)
        thread = await r.message.create_thread(name=chall_name)

    @chall.command(
            description="Mark a challenge solved."
    )
    async def solved(self, ctx, chall_name: str, points: int=0):
        with mysql.connector.connect(
                host=config.MYSQL_DB,
                port=3306,
                database='ctfcord',
                user='root',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                    'SELECT id, start, finish FROM ctf WHERE channel = %s',
                    (ctx.channel.id,)
            )
            if (ctf := cursor.fetchone()) == None:
                # Not invoked in a CTF's channel
                embed = discord.Embed(
                        title='Failed',
                        description='You can only invoke this command in a channel registered via /ctf signup.',
                        colour=discord.Colour.red()
                        )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            elif datetime.datetime.now() < datetime.datetime.fromtimestamp(ctf[1]) or datetime.datetime.now() > datetime.datetime.fromtimestamp(ctf[2]):
                embed = discord.Embed(
                        title='Failed',
                        description='The CTF has not started yet/has already ended.',
                        colour=discord.Colour.red()
                        )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            else:
                ctf = ctf[0]
            cursor.execute(
                    'REPLACE INTO challenges (name, points, ctf, solver, team, solved) '\
                    'SELECT %s, %s, %s, m.member, t.id, 1 FROM teams AS t '\
                    'INNER JOIN team_members AS m ON m.team = t.id '\
                    'WHERE m.member = %s AND t.guild = %s',
                    (chall_name, points, ctf, ctx.author.id, ctx.guild.id)
            )
            embed = discord.Embed(
                    title='Congrats',
                    description=f'<@!{ctx.author.id}> solved **{chall_name}**!',
                    colour=discord.Colour.green()
            )
            cursor.execute(
                    'SELECT name, points FROM challenges '\
                    'WHERE solver = %s AND solved = 1',
                    (ctx.author.id,)
            )
            solved = cursor.fetchall()
            embed.add_field(
                    name=f'You have solved:',
                    value='\n'.join([f'**{chall[0]}**' if chall[1] == 0 else f'**{chall[0]}** ({chall[1]} points)' for chall in solved])
            )
            cnx.commit()
        await ctx.respond(embed=embed)
    
def setup(bot):
    bot.add_cog(Challenges(bot))
