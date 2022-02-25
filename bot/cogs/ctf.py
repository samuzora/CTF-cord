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

# TODO: Finish up /solving and /solved
# TODO: Add /archive command to allow users to archive a CTF manually
# TODO: Support adding roles inside teams, and ping related roles when a CTF approaches 
# TODO: Allow users to define custom events that are not in CTFtime

async def get_ctf_details(event_id):
    # Required, if not CTFtime will 403
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0",
    }
    # Get JSON via API
    req = requests.get(
        f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
    )
    if req.status_code == 404:
        return 404
    # ID is valid
    event_json = req.content
    event_info = json.loads(event_json)
    if len(event_info['description']) > 1000:
        event_info['description'] = event_info['description'][:997] + '...'
    participants = event_info["participants"]
    # Timings are in ISO format - convert to datetime.datetime object
    event_info['start'] = datetime.datetime.fromisoformat(event_info["start"])
    event_info['finish'] = datetime.datetime.fromisoformat(event_info["finish"])
    return event_info

class CTF(commands.Cog):
    """ CTFs are managed here. With signup, you can register a CTF to take \
    part in, and never miss another CTF again with automatic Discord event \
    scheduling! To view details about a CTF, use /ctf details."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.check_ctf.start()

    ctf = SlashCommandGroup('ctf', 'Group of commands for CTF management', guild_ids=config.beta_guilds)


    @ctf.command(description="View details about an event in a nicely formatted embed.")
    async def details(self, ctx, ctftime_link: str):
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", ctftime_link
        )
        if p is None and regex.match("[0-9]+", ctftime_link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Search for the ID in link
        event = regex.search("[0-9]+", ctftime_link)
        event_id = event.group()
        # ID is incorrect - got 404
        event_info = await get_ctf_details(event_id)
        if event_info == 404:
            embed = discord.Embed(
                title="Error!",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Format embed
        embed = discord.Embed(title=event_info['title'], description=event_info['description'], colour=discord.Colour.blurple())
        embed.set_thumbnail(url=event_info['logo'])
        embed.add_field(name="Starts at", value=discord.utils.format_dt(event_info['start']))
        embed.add_field(name="Ends at", value=discord.utils.format_dt(event_info['finish']))
        embed.add_field(name="CTFtime", value=f"<https://ctftime.org/event/{event_id}>")
        embed.set_footer(
                text=f"{event_info['participants']} participants"
        )
        embed.url = event_info['url']
        if discord_inv := regex.search(
            "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
            event_info['desc'],
        ):
            # Discord invite link found
            embed.add_field(
                name="Discord Server",
                value=f"[Click here to join]({discord_inv.group()})",
            )
        await ctx.respond(embed=embed)


    @ctf.command(description="Sign up for an upcoming CTF, and register it to the bot.")
    async def signup(self, ctx, ctftime_link: str=''):
        if ctftime_link == '':
            # Custom event creation
            embed = discord.Embed(
                    title='CTF title',
                    description='CTF description',
                    colour=discord.Colour.blurple()
            )
            embed.add_field(
                    name='Starts at',
                    value='CTF start time'
            )
            embed.add_field(
                    name='Ends at',
                    value='CTF end time'
            )
            embed.set_footer(
                    text="What's this? No CTFtime ctftime_link was detected, so you are making a custom event now."
            )
            await ctx.respond(embed=embed, view=CustomEventView(self.bot))
            return
        # Check whether the ctftime_link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", ctftime_link
        )
        if p is None and regex.match("[0-9]+", ctftime_link) is None:
            # The ctftime_link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Failed",
                description="Sorry, this isn't a valid CTFtime event ctftime_link or id.",
                colour=discord.Colour.red(),
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Try to grab the event ID from the ctftime_link
        event = regex.search("[0-9]+", ctftime_link)
        event_id = event.group()
        event_info = get_ctf_details(event_id)
        # Check if CTF timing is valid
        if datetime.datetime.now(datetime.timezone.utc) > event_info['finish']:
            # CTF has already ended
            embed = discord.Embed(
                    title='Failed',
                    description='This CTF is already over.',
                    colour=discord.Colour.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        elif datetime.datetime.now(datetime.timezone.utc) > event_info['start']:
            # CTF has started, but start time cannot be in the past due to Discord event limitation
            # Add 5 second buffer to allow for lag due to creating event etc
            event_info['start'] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5)
        # Format embed
        embed = discord.Embed(title=event_info['title'], description=event_info['description'])
        embed.set_thumbnail(url=event_info['logo'])
        embed.add_field(name="Starts at", value=discord.utils.format_dt(event_info['start']))
        embed.add_field(name="Ends at", value=discord.utils.format_dt(event_info['finish']))
        embed.add_field(name="CTFtime", value=f"https://ctftime.org/event/{event_id}")
        embed.url = event_info['url']
        if discord_inv := regex.search(
            "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
            event_info['description'],
        ):
            # Discord invite found
            embed.add_field(
                name="Discord Server",
                value=f"[Click here to join]({discord_inv.group()})",
            )
        # There shouldn't be any exceptions from here on, so we don't need to worry abt ephemeral
        # Deferring is necessary as the heavy db operations later on might cause the app to not respond in time (3s)
        await ctx.defer()
        # Add the ctf to the database
        with mysql.connector.connect(
            host=config.MYSQL_DB,
            port=3306,
            username="root",
            database="ctfcord",
            password=config.MYSQL_PW,
        ) as cnx:
            cursor = cnx.cursor()
            # Check if the user's team has registered this CTF already
            cursor.execute(
                "SELECT t.id FROM ctf AS c " \
                "INNER JOIN team_members AS m ON c.team = m.team " \
                "INNER JOIN teams AS t ON m.team = t.id " \
                "WHERE c.id = %s AND t.guild = %s AND m.member = %s",
                (event_id, ctx.guild.id, ctx.author.id)
            ) 
            if (team_id := cursor.fetchone()) is not None:
                # CTF is already registered
                embed.colour = discord.Colour.blurple()
                embed.set_footer(
                        text="You have already signed up for this event!"
                )
                # Update the relevant information in case it has changed
                cursor.execute(
                    "UPDATE ctf AS c " \
                    "INNER JOIN team_members AS m ON c.team = m.team " \
                    "INNER JOIN teams AS t ON m.team = t.id " \
                    "SET c.description = %s, c.start = %s, c.finish = %s, c.discord = %s, c.participants = %s " \
                    "WHERE m.member = %s AND t.guild = %s",
                    (
                        event_info['desc'],
                        int(time.mktime(event_info['start'].timetuple())),
                        int(time.mktime(event_info['finish'].timetuple())),
                        discord_inv,
                        event_info['participants'],
                        ctx.author.id,
                        ctx.guild.id
                    )
                )
                await ctx.respond(embed=embed)
                return
            # CTF not registered yet
            embed.colour = discord.Colour.green()
            embed.set_footer(
                    text="Successfully signed up for this event!"
            )
            # Fix description length if its too long for scheduled event
            if len(event_info['description'] + f'...\nCTFtime:\nhttps://ctftime.org/event/{event_id}') >= 1000:
                event_info['description'] = event_info['description'][:1000 - len(f'...\nCTFtime:\nhttps://ctftime.org/event/{event_id}')] + f'...\nCTFtime:\nhttps://ctftime.org/event/{event_id}'
            # Create scheduled event
            scheduled_event = await ctx.guild.create_scheduled_event(
                    name=event_info['title'],
                    description=event_info['description'],
                    start_time=event_info['start'],
                    end_time=event_info['finish'],
                    location=event_info['url']
            )
            # Add CTF into db
            cursor.execute(
                    "INSERT INTO ctf (ctftime_id, title, description, start, " \
                        "finish, discord, participants, url, logo, team, scheduled_event, archived) " \
                    "SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s, t.id, %s, 0 FROM teams AS t " \
                    "INNER JOIN team_members AS m ON m.team = t.id " \
                    "WHERE m.member = %s AND t.guild = %s ",
                (
                    event_id,
                    event_info['title'],
                    event_info['description'],
                    int(time.mktime(event_info['start'].timetuple())),
                    int(time.mktime(event_info['finish'].timetuple())),
                    discord_inv,
                    event_info['participants'],
                    event_info['url'],
                    event_info['logo'],
                    scheduled_event.id,
                    ctx.author.id,
                    ctx.guild.id
                )
            ) 
            # Create new text channel for the CTF
            # Get list of members to update perms for channel
            # Default perms to view_channel = False
            perms = {
                    ctx.guild.default_role: \
                            discord.PermissionOverwrite(view_channel=False),
                    ctx.guild.me: \
                            discord.PermissionOverwrite(view_channel=True)

            }
            # Get user's team
            cursor.execute(
                    'SELECT t.id FROM team_members AS m '\
                    'INNER JOIN teams AS t ON t.id = m.team '\
                    'WHERE t.guild = %s AND m.member = %s',
                    (ctx.guild.id, ctx.author.id)
            )
            if (team_id := cursor.fetchone()[0]) == None:
                await ctx.respond("Sorry, you don't have a team yet, please make one via /team create", ephemeral=True)
                return
            # Get all members in team
            cursor.execute(
                    'SELECT member FROM team_members AS m '\
                    'INNER JOIN teams AS t '\
                    'ON t.id = m.team '\
                    'WHERE t.guild = %s AND m.team = %s',
                    (ctx.guild.id, team_id)
            )
            members = cursor.fetchall()
            for member in members:
                member_id = member[0]
                perms[ctx.guild.get_member(member_id)] = \
                        discord.PermissionOverwrite(view_channel=True)
            # Check if CTF category exists
            cursor.execute(
                    'SELECT t.ctf_category FROM teams AS t ' \
                    'INNER JOIN team_members AS m ON t.id = m.team ' \
                    'WHERE m.member = %s AND t.guild = %s',
                    (ctx.author.id, ctx.guild.id)
            )
            if (ctf_category := cursor.fetchone()) is None \
                    or ctx.guild.get_channel(ctf_category[0]) not in ctx.guild.categories:
                # Category does not exist, create it first
                ctf_category = await ctx.guild.create_category_channel('CTFs')          
                cursor.execute(
                        'UPDATE teams SET ctf_category = %s '\
                        'WHERE id = %s',
                        (ctf_category.id, team_id)
                )
            else:
                ctf_category = ctx.guild.get_channel(ctf_category[0])
            # Create channel
            ctf_channel = await ctx.guild.create_text_channel(
                    event_info['title'],
                    topic=f"https://ctftime.org/event/{event_id}",
                    overwrites=perms,
                    category=ctf_category
            ) 
            # Save channel in db
            cursor.execute(
                    'UPDATE ctf SET channel = %s '\
                    'WHERE id = %s',
                    (ctf_channel.id, event_id)
            )
            # Commit changes
            cnx.commit()
        await ctx.respond(embed=embed)
        await ctf_channel.send(embed=embed)


    @ctf.command(description="Un-signup for a CTF, unregistering it from the bot.")
    async def unsignup(self, ctx, ctftime_link: str):
        # TODO: Delete custom events
        await ctx.defer()
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", ctftime_link
        )
        if p is None and regex.match("[0-9]+", ctftime_link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Failed",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return
        # Try to grab the event ID from the link
        event = regex.search("[0-9]+", ctftime_link)
        event_id = event.group()
        with mysql.connector.connect(
                host=config.MYSQL_DB,
                port=3306,
                database='ctfcord',
                username='root',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            # Check if the team has registered this CTF
            ctf = cnx.cursor(dictionary=True)
            ctf.execute(
                    'SELECT c.id, c.title, c.description, c.start, c.finish, c.discord, c.participants, c.team, c.scheduled_event, c.url, c.logo, c.channel, c.archived FROM ctf AS c ' \
                    'INNER JOIN teams AS t ON c.team = t.id ' \
                    'INNER JOIN team_members AS m ON t.id = m.team ' \
                    'WHERE c.ctftime_id = %s AND t.guild = %s AND m.member = %s',
                    (event_id, ctx.guild.id, ctx.author.id)
            )
            if (ctf := ctf.fetchone()) is None:
                # Team didn't sign up for this CTF
                embed = discord.Embed(
                        title="Failed",
                        description="Sorry, you have not signed up " \
                                    "for this event.",
                        colour=discord.Colour.red()
                )
                await ctx.respond(embed=embed, ephemeral=True)
                return
            # Team signed up for this CTF
            title = ctf['title']
            desc = ctf['description']
            participants = ctf['participants']
            start = datetime.datetime.fromtimestamp(ctf['start'])
            finish = datetime.datetime.fromtimestamp(ctf['finish'])
            url = ctf['url']
            logo_url = ctf['logo']
            # Format embed
            embed = discord.Embed(title=title, description=desc)
            embed.set_thumbnail(url=logo_url)
            embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
            embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
            embed.add_field(name="CTFtime", value=f"https://ctftime.org/event/{event_id}")
            embed.url = url
            if discord_inv := regex.search(
                "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                desc
            ):
                # Discord invite found
                embed.add_field(
                    name="Discord Server",
                    value=f"[Click here to join]({discord_inv.group()})"
                )
            # Delete scheduled event
            cursor.execute(
                    'SELECT scheduled_event FROM ctf ' \
                    'WHERE id = %s', 
                    (ctf['id'],)
            )
            scheduled_event = ctx.guild.get_scheduled_event(cursor.fetchone()[0])
            try:
                await scheduled_event.delete()
            except:
                embed.add_field(
                    name="Scheduled Discord event",
                    value="The event could not be found, please try deleting it manually."
                )
                embed.colour = discord.Colour.blurple()
            else:
                embed.colour = discord.Colour.green()
            # Delete CTF channel
            cursor.execute(
                    'SELECT channel FROM ctf '\
                    'WHERE id = %s',
                    (ctf['id'],)
            )
            channel = ctx.guild.get_channel(cursor.fetchone()[0])
            try:
                await channel.delete()
            except:
                pass
            # Delete CTF from db
            cursor.execute(
                    'DELETE FROM ctf WHERE id = %s',
                    (ctf['id'],)
            )
            embed.set_footer(
                    text="The event has been successfully unregistered."
            )
            await ctx.respond(embed=embed)
    

    @tasks.loop(seconds=10.0)
    async def check_ctf(self):
        with mysql.connector.connect(
                host=config.MYSQL_DB,
                port=3306,
                database='ctfcord',
                user='root',
                password=config.MYSQL_PW
        ) as cnx:
            ctfs = cnx.cursor(dictionary=True)
            cursor = cnx.cursor()
            # Get all unarchived CTFs and the time which they start
            ctfs.execute('SELECT * FROM ctf WHERE archived = 0')
            ctfs = ctfs.fetchall()
            for ctf in ctfs:
                channel = self.bot.get_channel(ctf['channel'])
                if channel == None:
                    cursor.execute('UPDATE ctf SET archived = 0 WHERE id = %s AND team = %s', (ctf['id'], ctf['team']))
                    cnx.commit()
                    continue
                if datetime.datetime.fromtimestamp(ctf['start']) == datetime.datetime.now():
                    # CTF has started
                    # TODO: add option to turn off @everyone
                    embed = discord.Embed(
                            title=ctf['title'],
                            description='@everyone This CTF has started!',
                            colour=discord.Colour.blurple()
                    )
                elif (datetime.datetime.now() - datetime.datetime.fromtimestamp(ctf['start'])).days == -1:
                    # CTF will start in a day's time
                    embed = discord.Embed(
                            title=ctf['title'],
                            description='The CTF will start in 1 day!',
                            colour=discord.Colour.blurple()
                    )
                elif datetime.datetime.now() > datetime.datetime.fromtimestamp(ctf['finish']): 
                    # CTF is over, archive it
                    guild = channel.guild
                    cursor.execute(
                            'SELECT archived_category FROM teams '\
                            'WHERE id = %s',
                            (ctf['team'],)
                    )
                    archived = cursor.fetchone()[0]
                    if (archived := self.bot.get_channel(archived)) == None:
                        archived = await guild.create_category_channel('Archived')
                        cursor.execute(
                                'UPDATE teams SET archived_category = %s '\
                                'WHERE id = %s', 
                                (archived.id, ctf['team'])
                        )
                    print(archived)
                    archived = self.bot.get_channel(archived)
                    print(archived)
                    await channel.edit(category=archived)
                    # Get all members in team and their scores
                    cursor.execute(
                            'SELECT solver, points FROM challenges '\
                            'WHERE team = %s AND ctf = %s',
                            (ctf['team'], ctf['id'])
                    )
                    challenges = cursor.fetchall()
                    members = {}
                    total = 0
                    for c in challenges:
                        if c[0] not in members:
                            members[c[0]] = c[1]
                        else:
                            members[c[0]] += c[1]
                        total += c[1]
                    members = '\n'.join([f'<@{m}>: {members[m]} points ({round(members[m] / total * 100, 1)}%)' for m in members])
                    embed = discord.Embed(
                            title=ctf['title'],
                            description='@everyone The CTF has ended! Below are the percentage points of each team member:\n' + members,
                            colour=discord.Colour.green()
                            )
                    cursor.execute('UPDATE ctf SET archived = 1 WHERE id = %s AND team = %s', (ctf['id'], ctf['team']))
                await channel.send(embed=embed)
                cnx.commit()

class CustomEvent(discord.ui.Select):
    def __init__(self, bot):
        options = [
                discord.SelectOption(
                    label="CTF Name",
                    description="Edit the CTF's name",
                    value="title"
                ),
                discord.SelectOption(
                    label='CTF Platform Link',
                    description='Edit the CTF platform link',
                    value='link'
                ),
                discord.SelectOption(
                    label="CTF Description",
                    description="Edit the CTF's description",
                    value="desc"
                ),
                discord.SelectOption(
                    label="CTF Duration",
                    description="Edit the duration of the CTF",
                    value="start_end"
                ),
                discord.SelectOption(
                    label="Discord Invite",
                    description="Add a Discord Server invite, if there is one",
                    value="discord_inv"
                ),
                discord.SelectOption(
                    label="Done",
                    description="Done editing the challenge?",
                    emoji='✅',
                    value="done"
                ),
                discord.SelectOption(
                    label="Cancel",
                    description="Discard changes",
                    emoji='❌',
                    value="cancel"
                )
        ]
        self.bot = bot
        # In case it isn't initialized at point of saving
        self.discord_inv = None
        super().__init__(
                placeholder="Choose what to edit...",
                min_values=1,
                max_values=1,
                options=options
        )
    async def callback(self, interaction: discord.Interaction):
        # Check for wait_for(message)
        def check(m):
            return m.author == interaction.user and m.channel == interaction.channel

        # Get value of option
        option = self.values[0]
        if option == "title":
            await interaction.response.send_message(content="Please send the CTF's title in chat now.")
            try:
                title = await self.bot.wait_for('message', check=check, timeout=60.0)
            except:
                await interaction.edit_original_message(content="Timeout", delete_after=5.0)
                return
            else:
                await interaction.delete_original_message()
                embed = interaction.message.embeds[0]
                embed.title = discord.utils.escape_markdown(title.clean_content)
                await interaction.message.edit(embed=embed)
                self.title = embed.title
                return
        elif option == 'link':
            await interaction.response.send_message(content="Please send the CTF platform link in chat now.")
            try:
                link = await self.bot.wait_for('message', check=check, timeout=60.0)
            except:
                await interaction.edit_original_message(content="Timeout", delete_after=5.0)
                return
            else:
                embed = interaction.message.embeds[0]
                link = discord.utils.escape_markdown(link.clean_content)
                if regex.match('((?:https)|(?:http))?://.+\..+', link):
                    embed.url = link
                else:
                    await interaction.edit_original_message(content="Sorry, that doesn't seem to be a valid URL.", delete_after=5.0)
                    return
                await interaction.delete_original_message()
                await interaction.message.edit(embed=embed)
                self.url = embed.url
                return
        elif option == 'desc':
            await interaction.response.send_message(content='Please send a short description of the CTF in chat now.')
            try:
                desc = await self.bot.wait_for('message', check=check, timeout=60.0)
            except:
                await interaction.edit_original_message(content="Timeout", delete_after=5.0)
                return
            else:
                await interaction.delete_original_message()
                embed = interaction.message.embeds[0]
                desc = desc.clean_content
                embed.description = desc
                self.desc = embed.description
                await interaction.message.edit(embed=embed)
        elif option == 'start_end':
            await interaction.response.send_message(content='Please send the duration of the CTF (GMT) in the following format: DD/MM/YY HH:MM to DD/MM/YY HH:MM')
            try:
                duration = await self.bot.wait_for('message', check=check, timeout=60.0)
            except:
                await interaction.edit_original_message(content="Timeout", delete_after=5.0)
                return
            else:
                await interaction.delete_original_message()
                embed = interaction.message.embeds[0]
                duration = duration.content.split(' to ')
                start, finish = datetime.datetime.strptime(duration[0], '%d/%m/%y %H:%M'), datetime.datetime.strptime(duration[1], '%d/%m/%y %H:%M')

                if datetime.datetime.now() >= start or datetime.datetime.now() >= finish:
                    await interaction.edit_original_message('The time specified is invalid.', delete_after=5.0)
                    return
                else:
                    self.start, self.finish = start, finish
                    start, finish = discord.utils.format_dt(start), discord.utils.format_dt(finish)
                embed.set_field_at(0, name='Starts at', value=start)
                embed.set_field_at(1, name='Starts at', value=finish)
                await interaction.message.edit(embed=embed)
        elif option == 'discord_inv':
            await interaction.response.send_message(content='Please send the Discord invite link to the CTF discord.')
            try:
                discord_inv = await self.bot.wait_for('message', check=check, timeout=60.0)
            except:
                duration = await interaction.edit_original_message(content="Timeout", delete_after=5.0)
                return
            else:
                discord_inv = discord_inv.content
                if p := regex.match('((https)?|(https)?)://(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?', discord_inv):
                    for i in embed.fields:
                        if i.name == 'Discord Server':
                            index = embed.fields.index(i)
                            embed.set_field_at(index, name='Discord Server', value=discord_inv)
                            break
                        else:
                            embed.add_field(name='Discord Server', value=discord_inv)
                    self.discord_inv = discord_inv
                else:
                    await interaction.response.edit_original_message(content="That doesn't seem like a valid Discord invite!", delete_after=5.0)
        elif option == 'done':
            with mysql.connector.connect(
                    host=config.MYSQL_DB,
                    port=3306,
                    database='ctfcord',
                    user='root',
                    password=config.MYSQL_PW
            ) as cnx:
                cursor = cnx.cursor()
                cursor.execute('SELECT t.ctf_category, t.id FROM teams AS t '\
                        'INNER JOIN team_members AS m '\
                        'ON t.id = m.team '\
                        'WHERE t.guild = %s AND m.member = %s',
                        (interaction.guild.id, interaction.user.id)
                        )
                team = cursor.fetchone()
                category = self.bot.get_channel(team[0])
                cursor.execute(
                        'SELECT member FROM team_members WHERE team = %s',
                        (team[1],)
                )
                members = cursor.fetchall()
                perms = {
                        interaction.guild.default_role: \
                                discord.PermissionOverwrite(view_channel=False),
                        interaction.guild.me: \
                                discord.PermissionOverwrite(view_channel=True)

                }
                for member in members:
                    member_id = member[0]
                    perms[interaction.guild.get_member(member_id)] = \
                            discord.PermissionOverwrite(view_channel=True)
                # Check if CTF category exists
                cursor.execute(
                        'SELECT ctf_category FROM teams ' \
                        'WHERE id = %s',
                        (team[1],)
                )
                if (ctf_category := cursor.fetchone()) is None \
                        or interaction.guild.get_channel(ctf_category[0]) not in interaction.guild.categories:
                    # Category does not exist, create it first
                    ctf_category = await interaction.guild.create_category_channel('CTFs')          
                    cursor.execute(
                            'UPDATE teams SET ctf_category = %s '\
                            'WHERE id = %s',
                            (ctf_category.id, team[1])
                    )
                else:
                    ctf_category = interaction.guild.get_channel(ctf_category[0])
                # Create channel
                ctf_channel = await interaction.guild.create_text_channel(
                        self.title,
                        overwrites=perms,
                        category=ctf_category
                ) 
                # Schedule event
                scheduled_event = await interaction.guild.create_scheduled_event(
                        name=self.title,
                        description=self.desc,
                        start_time=self.start,
                        end_time=self.finish,
                        location=self.url
                )
                # Save CTF in db
                cursor.execute('INSERT INTO ctf (title, description, start, finish, '\
                        'discord, team, scheduled_event, channel, archived) '\
                        'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0)',
                        (self.title, self.desc, self.start, self.finish, self.discord_inv, team[1], scheduled_event.id, ctf_channel.id))
                cnx.commit()
                await interaction.response.send_message('The CTF has been saved!', ephemeral=True)
        elif option == 'cancel':
            await interaction.response.send_message('Deleting challenge...', delete_after=5.0, ephemeral=True)
            await interaction.message.delete()

        else:
            await interaction.response.send_message(content='Sorry, not implemented yet', ephemeral=True)
            return

class CustomEventView(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.add_item(CustomEvent(bot))

def setup(bot):
    bot.add_cog(CTF(bot))
