import asyncio
import datetime
import os

import discord
from discord.commands import SlashCommandGroup, slash_command
from discord.ext import commands
import mysql.connector
from prettytable import PrettyTable

import config

class Dev(commands.Cog):
    """ Development convieniences """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    # --- /dev ---
    dev = SlashCommandGroup(
            'dev',
            'Dev stuff',
            guild_ids=config.beta_guilds
    )

    # --- /dev execute ---
    @dev.command(
            description="Executes a query on the DB. For dev use only.",
    )
    async def execute(self, ctx, query:str):
        if (await self.bot.is_owner(ctx.author)) is False:
            await ctx.respond("Go away", ephemeral=True)
            return

        with config.Connect() as cnx:
            cursor = cnx.cursor()
            try:
                cursor.execute(query)
            except mysql.connector.Error:
                await ctx.respond("Error in query", ephemeral=True)
                return
            else:
                out = cursor.fetchall()
            cnx.commit()
        table = PrettyTable()
        table.field_names = [d[0] for d in cursor.description]
        for row in out:
            table.add_row(row)
        print(table)

        await ctx.respond("Check logs", ephemeral=True)
    

def setup(bot):
    bot.add_cog(Dev(bot))
