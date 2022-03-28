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
    You can mark challenges as solved, which allocates points to you and \
    tracks your contribution to the team. """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot


    # --- /chall ---
    chall = SlashCommandGroup('chall', 'Group of commands relating to challenges', guild_ids=config.beta_guilds)
    

    # --- /chall solved ---
    @chall.command(description="Mark a challenge solved.")
    async def solved(self, ctx, chall_name: str, points: int=0):
        team = await config.get_user_team(ctx.author, ctx.guild)
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                    'SELECT id, start, finish FROM ctf WHERE channel = %s',
                    (ctx.channel.id,)
            )
            if (ctf := cursor.fetchone()) == None:
                # Not invoked in a CTF's channel
                await ctx.respond(
                        'You can only invoke this command in a channel registered via /ctf signup.', 
                        ephemeral=True,
                )
                return
            elif datetime.datetime.now() < datetime.datetime.fromtimestamp(ctf[1]) or datetime.datetime.now() > datetime.datetime.fromtimestamp(ctf[2]):
                # CTF timing not valid
                await ctx.respond('This CTF has already ended/not started yet', ephemeral=True)
                return

            # Insert chall into db
            cursor.execute(
                    'REPLACE INTO challenges (name, points, ctf, solver, team, solved) '\
                    'VALUES (%s, %s, %s, %s, %s, 1)',
                    (chall_name, points, ctf[0], ctx.author.id, team),
            )

            # Get list of challs the user solved
            cursor.execute(
                    'SELECT name, points FROM challenges '\
                    'WHERE team = %s AND solver = %s AND solved = 1 AND ctf = %s',
                    (team, ctx.author.id, ctf[0]),
            )
            solved = cursor.fetchall()

            # Format embed
            embed = discord.Embed(
                    title='Congrats',
                    description=f'<@!{ctx.author.id}> solved **{chall_name}**!',
                    colour=discord.Colour.green()
            )

            # Add list of challs into embed
            embed.add_field(
                    name=f'<@!{ctx.author.id}> solved',
                    value='\n'.join([f'**{chall[0]}**' if chall[1] == 0 else f'**{chall[0]}** ({chall[1]} points)' for chall in solved]) 
            )
            cnx.commit()
        await ctx.respond(embed=embed)

    # --- /chall solving ---
    @chall.command(description="Create thread for the challenge.")
    async def solving(self, ctx, category: str, name: str):
        team = await config.get_user_team(ctx.author, ctx.guild)
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                    'SELECT id, start, finish FROM ctf WHERE channel = %s',
                    (ctx.channel.id,)
            )
            if (ctf := cursor.fetchone()) == None:
                # Not invoked in a CTF's channel
                await ctx.respond(
                        'You can only invoke this command in a channel registered via /ctf signup.', 
                        ephemeral=True,
                )
                return
            elif datetime.datetime.now() < datetime.datetime.fromtimestamp(ctf[1]) or datetime.datetime.now() > datetime.datetime.fromtimestamp(ctf[2]):
                # CTF timing not valid
                await ctx.respond('This CTF has already ended/not started yet', ephemeral=True)
                return

        # Format embed
        embed = discord.Embed(
                title=f'{category} - {name}',
                description=f'Created by {ctx.author.mention}',
                colour=discord.Colour.blurple(),
        )

        # Send embed to create thread under
        interaction = await ctx.respond(embed=embed)
        message = await interaction.original_message()

        # Create thread
        await message.create_thread(name=f'{category}-{name}')
        return

    
def setup(bot):
    bot.add_cog(Challenges(bot))
