import datetime
import os

from dateparser import parse
import discord
from discord.commands import slash_command, SlashCommandGroup
from discord.ext import commands
import mysql.connector

import config

# --- settings modal ---
class CtftimeConfigModal(discord.ui.Modal):
    def __init__(self, bot, guild_config):
        super().__init__(title="Configure CTFtime weekly updates")
        self.bot = bot
        self.guild_config = guild_config
        self.add_item(
                discord.ui.InputText(
                    label="Enable? (y/n)",
                    style=discord.InputTextStyle.short,
            )
        )
        self.add_item(
                discord.ui.InputText(
                    label="Channel ID to send updates to",
                    style=discord.InputTextStyle.short,
                    required=False,
                    min_length=18,
                    max_length=18,
            )
        )

        self.add_item(
                discord.ui.InputText(
                    label="Day of week to send updates",
                    style=discord.InputTextStyle.short,
                    min_length=3,
                    required=False,
            )
        )


    async def callback(self, interaction: discord.Interaction):
        # Get data
        enabled = True if self.children[0].value.lower() == 'y' else False
        try:
            assert enabled
            channel_id = int(self.children[1].value)
            send_day = parse(self.children[2].value).weekday()
            channel = self.bot.get_channel(channel_id)
            assert channel != None
        except:
            channel_id = send_day = None

        self.guild_config['ctftime_channel'] = channel_id
        self.guild_config['ctftime_send_day'] = send_day
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                'REPLACE INTO guilds (guild_id, name, ctftime_channel, ctftime_send_day) '\
                'VALUES (%s, %s, %s, %s)',
                (interaction.guild.id, interaction.guild.name, channel_id, send_day),
            )
            cnx.commit()
        embed = await config_to_embed(self.guild_config)
        await interaction.response.edit_message(embed=embed)

# --- settings view ---
class SettingsView(discord.ui.View):
    def __init__(self, bot, guild_config):
        super().__init__()
        self.value = None
        self.bot = bot
        self.guild_config = guild_config

    @discord.ui.button(label="Configure CTFtime weekly updates", style=discord.ButtonStyle.primary)
    async def ctftime(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(CtftimeConfigModal(self.bot, self.guild_config))


# --- function to convert guild config to embed ---
async def config_to_embed(guild_config):
    # Format embed
    if guild_config['ctftime_channel'] != None and guild_config['ctftime_send_day'] != None:
        channel = f'<#{guild_config["ctftime_channel"]}>'
        day = ["Mon", "Tues", "Wed", "Thu", "Fri", "Sat", "Sun"][guild_config['ctftime_send_day']]
        ctftime_updates = f'Enabled ({channel}, every {day})'
    else:
        ctftime_updates = 'Disabled'

    description = f"""**CTFtime weekly updates:** {ctftime_updates}"""
    embed = discord.Embed(
            title="Configuration menu",
            description=description,
            color=discord.Color.blurple()
    )
    return embed


# --- /settings ---
class Settings(commands.Cog):
    """ Configure the bot here! """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    # --- /settings ---
    @slash_command(description="Bot settings")
    async def settings(self, ctx):
        # Get guild's current config
        with config.Connect() as cnx:
            cursor = cnx.cursor(dictionary=True)
            cursor.execute(
                    'SELECT ctftime_channel, ctftime_send_day FROM guilds '\
                    'WHERE guild_id = %s',
                    (ctx.guild.id,)
            )
            guild_config = cursor.fetchone()
            if guild_config == None:
                cursor.execute(
                        'INSERT INTO guilds (guild_id, name) '\
                        'VALUES (%s, %s)',
                        (ctx.guild.id, ctx.guild.name)
                )
                cursor.execute(
                        'SELECT ctftime_channel, ctftime_send_day FROM guilds '\
                        'WHERE guild_id = %s',
                        (ctx.guild.id,)
                )
                guild_config = cursor.fetchone()

        embed = await config_to_embed(guild_config)
        await ctx.respond(embed=embed, view=SettingsView(self.bot, guild_config))

def setup(bot):
    bot.add_cog(Settings(bot))
