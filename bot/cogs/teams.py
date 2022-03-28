import asyncio
import datetime
import os

import discord
from discord.commands import slash_command, SlashCommandGroup
from discord.ext import commands
import mysql.connector

import config

class Teams(commands.Cog):
    """ Teams are groups of people that you usually play CTFs with. Creating \
    a team allows you to manage CTFs, split challenges to solve in an \
    organized manner and keep track of solve ratio of challenges per member \
    (useful for prize distribution) """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    # --- /team ---
    team_group = SlashCommandGroup(
            'team', 'Group of commands for team management', 
            guild_ids=config.beta_guilds
    )

    # --- /team create ---
    @team_group.command(
            description="Creates a team so you can use this bot with your team!"
    )
    async def create(self, ctx, name: str):
        with config.Connect() as cnx:
            cursor = cnx.cursor()
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
            # Check if user is already in a team
            team = await config.get_user_team(ctx.author, ctx.guild)
            if team != None:
                # User already has a team
                await ctx.respond(
                        'You are already in a team in this server. Due to Discord limitations, you can only be in one team per guild.',
                        ephemeral=True,
                )
                return

            # User isn't in a team
            # Create role
            role = await ctx.guild.create_role(
                    name=name, 
            ) 
            # Add author to role
            await ctx.author.add_roles(role)
            # Add team to db
            cursor.execute(
                    'INSERT INTO teams (title, role, guild) '\
                    'VALUES (%s, %s, %s)',
                    (name, role.id, ctx.guild.id)
            )

            # Format embed
            embed = discord.Embed(
                    title="Team created!",
                    description=f"The team {role.mention} has been created. Assign others this role to add them to your team.",
                    colour=discord.Colour.green(),
            )
            await ctx.respond(embed=embed)
            cnx.commit()


    # --- /team delete ---
    @team_group.command(
            description="Deletes a team. This is irrversible."
    )
    async def delete(self, ctx):
        team = await config.get_user_team(ctx.author, ctx.guild)
        if team == None:
            embed = discord.Embed(
                    title="Error",
                    description="You are not currently in a team.",
                    colour=discord.Colour.red(),
            )

        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Get role of team
            cursor.execute(
                    'SELECT role FROM teams WHERE id = %s',
                    (team,),
            )
            role = ctx.author.get_role(cursor.fetchone()[0])
            # Delete role
            await role.delete()

            # Delete team from db
            cursor.execute('DELETE FROM teams WHERE id = %s',
                    (team,),
            )
            cnx.commit()

            # Format embed
            embed = discord.Embed(
                    title="Success!",
                    description="Your team has been successfully deleted.",
                    colour=discord.Colour.green()
                    )
        await ctx.respond(embed=embed)
    

def setup(bot):
    bot.add_cog(Teams(bot))
