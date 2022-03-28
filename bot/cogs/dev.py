import asyncio
import datetime
import os

import discord
from discord.commands import slash_command, SlashCommandGroup
from discord.ext import commands
import mysql.connector

import config

# TODO: Hand over team management to roles. Keep /team add and /team remove, but don't get teams based on database.  (BIG REWORK!!)

class Dev(commands.Cog):
    """ Development convieniences """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    dev = SlashCommandGroup(
            'Dev stuff',
            guild_ids=config.beta_guilds
    )
    @dev.command(
            description="Reload the database with the new schema. Will clear all data."
    )
    async def reload(self, ctx, name: str, role:discord.Role=None):
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            if role == None:
                # No role was provided - create our own role for this team
                # Check if the name is valid
                cursor.execute(
                        'SELECT COUNT(1) FROM teams WHERE title = %s AND guild = %s',
                        (name, ctx.guild.id,)
                )
                if cursor.fetchall()[0][0] != 0:
                    # Can't use this name
                    await ctx.respond(
                            'A team with this name exists in this guild.',
                            ephemeral=True,
                    )
                    return
                # Name is available
                role = await ctx.guild.create_role(
                        name=name, 
                ) 
            else:
                # Role provided
                # Check if role is already used in another team
                # TODO: actually implement
                pass
            await ctx.author.add_roles(role)
            cursor.execute(
                    'INSERT INTO teams (title, role, guild) '\
                    'VALUES (%s, %s, %s)',
                    (name, role.id, ctx.guild.id)
            )
            cnx.commit()

    @team_group.command(
            description="Deletes a team. This is irrversible."
    )
    async def delete(self, ctx):
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                    'SELECT m.team FROM team_members AS m ' \
                    'INNER JOIN teams AS t ON m.team = t.id ' \
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            if (team_id := cursor.fetchone()) is not None:
                # TODO: possibly remove this feature and instead only 
                # allow users to leave a team, which is deleted when
                # there are no users left
                cursor.execute('DELETE FROM team_members WHERE team = %s',
                        (team_id[0],)
                )
                cursor.execute('DELETE FROM teams WHERE id = %s',
                        (team_id[0],)
                )
                cnx.commit()
                embed = discord.Embed(
                        title="Success!",
                        description="Your team has been successfully deleted.",
                        colour=discord.Colour.green()
                        )
            else:
                embed = discord.Embed(
                        title="Error",
                        description="You are not currently in a team.",
                        colour=discord.Colour.red()
                        )
        await ctx.respond(embed=embed)
    

def setup(bot):
    bot.add_cog(Teams(bot))
