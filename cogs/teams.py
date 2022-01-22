import asyncio
import datetime
import os

import discord
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
                    'INNER JOIN teams AS t ON m.id = t.id ' \
                    'WHERE m.member = %s AND t.guild = %s', 
                    (ctx.author.id, ctx.guild.id)
            )
            if cursor.fetchone()[0] == 0:
                # User doesn't have a team in this guild
                cursor.execute(
                        'INSERT INTO teams (title, users, guild)' \
                        'VALUES (%s, 1, %s)',
                        (name, ctx.guild.id)
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
                    'INNER JOIN teams AS t ON m.id = t.id ' \
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            if (team_id := cursor.fetchone()) is not None:
                # TODO: implement voting system to delete team
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
    

def setup(bot):
    bot.add_cog(Teams(bot))
