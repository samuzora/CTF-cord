import asyncio
import datetime
import os

import discord
from discord.commands import slash_command
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

    @commands.command(
            brief="Create a team",
            description="This command allows you to create a team. To " \
                        "add others into your team, use the add command.",
            usage="<team-name>"
    )
    async def create(self, ctx, name):
        with mysql.connector.connect(
                host='127.0.0.1',
                port=3306,
                username='root',
                database='ctfcord',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            # Check if user is in a team in this guild
            # Right now, one user is limited to one team per guild 
            cursor.execute(
                    'SELECT COUNT(1) FROM team_members AS m ' \
                    'INNER JOIN teams AS t ON m.team = t.id ' \
                    'WHERE m.member = %s AND t.guild = %s', 
                    (ctx.author.id, ctx.guild.id)
            )
            if cursor.fetchone()[0] == 0:
                # User doesn't have a team in this guild
                cursor.execute(
                        'INSERT INTO teams (title, members, guild)' \
                        'VALUES (%s, 1, %s)',
                        (name, ctx.guild.id)
                )
                cursor.execute(
                        'INSERT INTO team_members '
                        'SELECT id, %s FROM teams',
                        (ctx.author.id,)
                )
                cnx.commit()
                embed = discord.Embed(
                        title="Success!",
                        description="You have successfully created the team " \
                                f"{name}! To add others into your team, use " \
                                "the add command.",
                        colour=discord.Colour.green()
                )
            else:
                # User has a team in this guild
                embed = discord.Embed(
                        title="Denied",
                        description="Sorry, you already belong to a team in " \
                                "this guild. To leave a team, use " \
                                "the leave command.",
                        colour=discord.Colour.red()
                )
        await ctx.send(embed=embed)
            
    @commands.command(
            brief="Delete your team",
            description="This commmand allows you to delete the team you are " \
                        "in. This action is irreversible; please discuss " \
                        "with your teammates first.",
            usage=""
    )
    async def delete(self, ctx):
        with mysql.connector.connect(
                host='127.0.0.1',
                port=3306,
                username='root',
                database='ctfcord',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                    'SELECT m.id FROM team_members AS m ' \
                    'INNER JOIN teams AS t ON m.team = t.id ' \
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            if (team_id := cursor.fetchone()) is not None:
                # TODO: implement voting system to delete team
                # TODO: possibly remove this feature and instead only 
                # allow users to leave a team, which is deleted when
                # there are no users left
                cursor.execute('DELETE FROM team_members WHERE id = %s',
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
        await ctx.send(embed=embed)
    
    @commands.command(
            brief="Add others into your team",
            description="This command allows you to add another member into "\
                        "your team.",
            usage="@foobar @asdf @qwerty"
    )
    async def add(self, ctx):
        users = ctx.message.mentions
        with mysql.connector.connect(
                host='127.0.0.1',
                port=3306,
                username='root',
                database='ctfcord',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            # Get the invoker's team
            cursor.execute(
                    'SELECT t.id FROM teams AS t ' \
                    'INNER JOIN team_members AS m ON t.id = m.team '\
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            team_id = (cursor.fetchone())[0]
            # Get list of users in team
            cursor.execute(
                    'SELECT member FROM team_members ' \
                    'WHERE team = %s',
                    (team_id,)
            )
            team_members = cursor.fetchall()
            # Remove any users who are already in team
            users = [user.id for user in users if (user.id,) not in team_members] 
            if len(users) == 0:
                embed = discord.Embed(
                        title="Done",
                        description="No one was added, as all users " \
                                    "mentioned are already in the team.",
                        colour=discord.Colour.blurple()
                )
                embed.add_field(
                    name="Members in your team",
                    value='\n'.join([f'<@{member[0]}>' for member in team_members])
                )
                await ctx.send(embed=embed)
                return
            for user in users:
                cursor.execute(
                        'INSERT INTO team_members VALUES (%s, %s)',
                        (team_id, user)
                )
            cursor.execute(
                    'UPDATE teams SET members = members + %s WHERE id = %s',
                    (len(users), team_id)
            )
            embed = discord.Embed(
                    title="Successfully added",
                    colour=discord.Colour.green()
            )
            embed.add_field(
                name='Added',
                value='\n'.join([f'<@{user}>' for user in users])
            )
            await ctx.send(embed=embed)
            cnx.commit()

    @commands.command(
            brief="Kick others from your team",
            description="Remove users from your team :< If you want to add " \
                        "them back, use the add command.",
            usage="@foobar @asdf @qwerty"
    )
    async def kick(self, ctx):
        users = ctx.message.mentions
        with mysql.connector.connect(
                host='127.0.0.1',
                port=3306,
                database='ctfcord',
                username='root',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            # Get the invoker's team
            cursor.execute(
                    'SELECT t.id FROM teams AS t ' \
                    'INNER JOIN team_members AS m ON t.id = m.team '\
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            team_id = (cursor.fetchone())[0]
            # Get users in team
            cursor.execute(
                    'SELECT member FROM team_members WHERE team = %s',
                    (team_id,)
            )
            team_members = cursor.fetchall()
            users = [user.id for user in users if (user.id,) in team_members]
            if len(users) == 0:
                # All users mentioned are not in team
                embed = discord.Embed(
                        title="Done",
                        description="No one was removed, as everyone mentioned " \
                                    "is not currently in your team.",
                        colour=discord.Colour.blurple()
                )
                embed.add_field(
                        name="Members in your team",
                        value=''.join([f'<@{member[0]}>' for member in team_members])
                )
                await ctx.send(embed=embed)
                return
            for user in users:
                cursor.execute(
                        'DELETE FROM team_members ' \
                        'WHERE member = %s AND team = %s',
                        (user, team_id)
                )
            cursor.execute(
                    'UPDATE teams SET members = members - %s ' \
                    'WHERE id = %s',
                    (len(users), team_id)
            )
            embed = discord.Embed(
                    title="Successfully removed",
                    colour=discord.Colour.green()
            )
            embed.add_field(
                    name="Removed",
                    value=''.join([f'<@{user}>' for user in users])
            )
            await ctx.send(embed=embed)
            cnx.commit()

def setup(bot):
    bot.add_cog(Teams(bot))
