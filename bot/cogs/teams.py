import asyncio
import datetime
import os

import discord
from discord.commands import slash_command, SlashCommandGroup
from discord.ext import commands
import mysql.connector

import config

# TODO: Hand over team management to roles. Keep /team add and /team remove, but don't get teams based on database. This will allow multiple teams per user per guild. (BIG REWORK!!)

class Teams(commands.Cog):
    """ Teams are groups of people that you usually play CTFs with. Creating \
    a team allows you to manage CTFs, split challenges to solve in an \
    organized manner and keep track of solve ratio of challenges per member \
    (useful for prize distribution) """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    team_group = SlashCommandGroup(
            'team', 'Group of commands for team management', 
            guild_ids=config.beta_guilds
    )
    @team_group.command(
            description="Creates a team so you can use this bot with others!"
    )
    async def create(self, ctx, name: str):
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Check if user is in a team in this guild
            # Right now, one user is limited to one team per guild 
            cursor.execute(
                    'SELECT COUNT(1) FROM team_members AS m ' \
                    'INNER JOIN teams AS t ON m.team = t.id ' \
                    'WHERE m.member = %s AND t.guild = %s', 
                    (ctx.author.id, ctx.guild.id)
            )
            if cursor.fetchone()[0] != 0:
                # User already has a team in this guild
                await ctx.respond("Sorry, you already have a team in this "\
                        "guild. Due to limitations, as of now you can only "\
                        "be in one team per guild.", ephemeral=True)
                return
            # User doesn't have a team in this guild
            cursor.execute(
                    'INSERT INTO teams (title, members, guild) ' \
                    'VALUES (%s, 1, %s)',
                    (name, ctx.guild.id)
            )
            # Get the uid of the team
            cursor.execute('SELECT LAST_INSERT_ID()')
            team_id = cursor.fetchone()
            cursor.execute(
                    'INSERT INTO team_members (team, member) '\
                    'VALUES (%s, %s)',
                    (team_id[0], ctx.author.id)
            )
            embed = discord.Embed(
                    title="Success!",
                    description="You have successfully created the team " \
                            f"{name}! To add others into your team, use " \
                            "the /team add command.",
                    colour=discord.Colour.green()
            )
            cnx.commit()
            await ctx.respond(embed=embed)
            
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
    
    @team_group.command(
            description="Adds another member into your team!"
    )
    async def add(self, ctx, member: discord.Member):
        member = member.id
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Get the invoker's team
            cursor.execute(
                    'SELECT t.id FROM teams AS t ' \
                    'INNER JOIN team_members AS m ON t.id = m.team '\
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            if (team_id := cursor.fetchone()) == None:
                embed = discord.Embed(
                        title='Failed',
                        description="Sorry, you don't have a team yet! Use /team create to make a new team.",
                        colour=discord.Colour.red()
                        )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            else:
                team_id = team_id[0]
            # Get list of users in team
            cursor.execute(
                    'SELECT m.member FROM team_members AS m ' \
                    'INNER JOIN teams AS t ' \
                    'ON t.id = m.team '\
                    'WHERE t.guild = %s AND m.team = %s',
                    (ctx.guild.id, team_id)
            )
            team_members = cursor.fetchall()
            if (member,) in team_members:
                # Member mentioned already in team
                embed = discord.Embed(
                        title="Failed",
                        description="This user is already in your team.",
                        colour=discord.Colour.red()
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            else:
                # Member not in team
                # Update team_member table
                cursor.execute(
                        'INSERT INTO team_members (team, member) VALUES (%s, %s)',
                        (team_id, member)
                )
                # Update size of team
                cursor.execute(
                        'UPDATE teams SET members = members + 1 WHERE id = %s',
                        (team_id,)
                )
                embed = discord.Embed(
                        title="Successfully added",
                        description=f"Successfully added <@{member}> into team. Good luck!",
                        colour=discord.Colour.green()
                        )
                # Add member to all CTF channels relevant to team
                cursor.execute(
                        'SELECT channel FROM ctf WHERE team = %s',
                        (team_id,)
                )
                channels = cursor.fetchall()
                for c in channels:
                    try:
                        channel = self.bot.get_channel((c[0]))
                        overwrites = channel.overwrites
                        overwrites[ctx.guild.get_member(member)] = discord.PermissionOverwrite(view_channel=True)
                        await channel.edit(overwrites=overwrites)
                    except AttributeError:
                        pass
                         
            # Refresh list in case of changes
            cursor.execute(
                    'SELECT member FROM team_members AS m ' \
                    'INNER JOIN teams AS t '\
                    'ON t.id = m.team '\
                    'WHERE t.guild = %s AND m.team = %s',
                    (ctx.guild.id, team_id)
            )
            team_members = cursor.fetchall()
            # Add list of team_members
            embed.add_field(
                    name="Members in your team",
                    value='\n'.join([f'<@{team_member[0]}>' for team_member in team_members])
            )
            await ctx.respond(embed=embed)
            cnx.commit()

    @team_group.command(
            description="Remove others from your team"
    )
    async def remove(self, ctx, member: discord.Member):
        member = member.id
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Get the invoker's team
            cursor.execute(
                    'SELECT t.id FROM teams AS t ' \
                    'INNER JOIN team_members AS m ON t.id = m.team '\
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            if (team_id := cursor.fetchone()) == None:
                embed = discord.Embed(
                        title="Failed", 
                        description="Sorry, you don't have a team yet! Use /team create to make a new team.",
                        colour=discord.Colour.red()
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            else:
                team_id = team_id[0]
            # Get users in team
            cursor.execute(
                    'SELECT member FROM team_members WHERE team = %s',
                    (team_id,)
            )
            team_members = cursor.fetchall()
            if (member,) not in team_members:
                embed = discord.Embed(
                        title="Failed",
                        description="The user is not in your team.",
                        colour=discord.Colour.red()
                )
                embed.add_field(
                    name="Members in your team",
                    value='\n'.join([f'<@{team_member[0]}>' for team_member in team_members])
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            else:
                # Remove user from team_members table
                cursor.execute(
                        'DELETE FROM team_members ' \
                        'WHERE member = %s AND team = %s',
                        (member, team_id)
                )
                # Reduce team member count by one
                cursor.execute(
                        'UPDATE teams SET members = members - 1 ' \
                        'WHERE id = %s',
                        (team_id,)
                )
                embed = discord.Embed(
                        title="Successfully removed",
                        description=f"<@{member}> has been removed from your team. Good bye!",
                        colour=discord.Colour.green()
                )
                # Remove member from all ctf channels
                cursor.execute(
                        'SELECT channel FROM ctf WHERE team = %s',
                        (team_id,)
                )
                channels = cursor.fetchall()
                for c in channels:
                    try:
                        channel = self.bot.get_channel((c[0]))
                        overwrites = channel.overwrites
                        overwrites.pop(ctx.guild.get_member(member))
                        await channel.edit(overwrites=overwrites)
                    except AttributeError:
                        pass

            # Refresh list of members
            cursor.execute(
                    'SELECT member FROM team_members WHERE team = %s',
                    (team_id,)
            )
            team_members = cursor.fetchall()
            users = '\n'.join([f'<@{team_member[0]}>' for team_member in team_members])
            if users == '':
                # The team has no more members
                cursor.execute(
                        'DELETE FROM teams ' \
                        'WHERE id = %s',
                        (team_id,)
                )
                embed.add_field(
                        name='Members in your team', 
                        value='There are no users left in your team, so this team has been deleted automatically.'
                )
            else:
                embed.add_field(
                        name="Members in your team",
                        value='\n'.join([f'<@{team_member[0]}>' for team_member in team_members])
                )
            await ctx.respond(embed=embed)
            cnx.commit()

def setup(bot):
    bot.add_cog(Teams(bot))
