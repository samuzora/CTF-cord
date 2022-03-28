import asyncio
import datetime
import json
import logging
import os
import time

from dateutil import parser
import discord
from discord.commands import slash_command, SlashCommandGroup
from discord.ext import commands, tasks
import regex
import requests

import config

# TODO: Add /archive command to allow users to archive a CTF manually
# TODO: Support adding roles inside teams, and ping related roles when a CTF approaches
# TODO: Allow users to define custom CTF/archive category channels in a configuaration interface

# --- internal command to get CTF details ---
async def get_ctf_details(event_id):
    # CTFtime will 403 if this is not added
    headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"
    }
    # Grab JSON via API
    req = requests.get(
            f'https://ctftime.org/api/v1/events/{event_id}/', headers=headers,
    )
    if req.status_code == 404:
        # API returned 404
        return 404
    # ID is valid
    event_info = json.loads(req.content)
    if len(event_info['description']) > 1000:
        event_info['description'] = event_info['description'][:997] + '...'
    event_info['start'] = datetime.datetime.fromisoformat(event_info['start'])
    event_info['finish'] = datetime.datetime.fromisoformat(event_info['finish'])
    event_info['discord_inv'] = regex.search(
            '((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?',
            event_info['description'],
    )
    return event_info



# --- /ctf --- 
class CTF(commands.Cog):
    ''' CTFs are managed here. With /ctf signup, you can register a CTF to take \
    part in, and never miss another CTF again with automatic Discord event \
    scheduling! To view details about a CTF, use /ctf details.'''


    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.check_ctf.start()


    # --- slash command group ---
    ctf = SlashCommandGroup('ctf', 'Group of commands for CTF management', guild_ids=config.beta_guilds)


    # --- /ctf details ---
    @ctf.command(description='View details about an event in a nicely formatted embed.')
    async def details(self, ctx, ctftime_link: str):
        # Check if link is valid (try and grab an ID from string)
        event_id = regex.search('[0-9]+', ctftime_link)
        if event_id is None:
            # The link is not valid
            await ctx.respond("This isn't a valid CTFtime event link or id.", ephemeral=True)
            return

        # Link seems valid
        event_id = event_id.group()
        event_info = await get_ctf_details(event_id)
        if event_info == 404:
            # ID is incorrect - got 404
            await ctx.respond("This isn't a valid CTFtime event link or id.", ephemeral=True)
            return

        # ID is correct, formatting embed
        embed = discord.Embed(
                title=event_info['title'],
                description=event_info['description'],
                colour=discord.Colour.blurple()
        )
        embed.set_thumbnail(url=event_info['logo'])
        embed.add_field(
                name='Starts at',
                value=discord.utils.format_dt(event_info['start']),
        )
        embed.add_field(
                name='Ends at',
                value=discord.utils.format_dt(event_info['finish']),
        )
        embed.add_field(
                name='CTFtime',
                value=f'<https://ctftime.org/event/{event_id}>',
        )
        embed.url = event_info['url']
        if event_info['discord_inv'] is not None:
            embed.add_field(
                    name='Discord Server',
                    value=f'[Click here to join!]({event_info["discord_inv"]})',
            )
        await ctx.respond(embed=embed)


    # --- /ctf signup ---
    @ctf.command(description='Sign up for an upcoming CTF, and register it to the bot.')
    async def signup(self, ctx, ctftime_link: str=''):
        # Get the user's team
        team_id = await config.get_user_team(ctx.author, ctx.guild)
        if team_id is None:
            # User doesn't have a team
            await ctx.respond('You need to be in a team to use this command.', ephemeral=True)
            return

        if ctftime_link == '':
            # Send modal to create custom event
            await ctx.send_modal(CustomEventModal(self.bot))
            return

        # Check whether the link is valid
        event_id = regex.search('[0-9]+', ctftime_link)
        if event_id is None:
            # The link is not valid
            await ctx.respond("This isn't a valid CTFtime event link or id.", ephemeral=True)
            return

        # Link seems valid
        event_id = event_id.group()
        event_info = await get_ctf_details(event_id)
        if event_info == 404:
            # ID is incorrect - got 404
            await ctx.respond("This isn't a valid CTFtime event link or id.", ephemeral=True)
            return

        # Check if timing is valid
        if datetime.datetime.now(datetime.timezone.utc) > event_info['finish']:
            # CTF has already ended
            await ctx.respond('This CTF is already over.', ephemeral=True)
            return
        elif datetime.datetime.now(datetime.timezone.utc) > event_info['start']:
            # Start time cannot be in the past 
            # Add a 5 second buffer to account for lag
            event_info['start'] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=5)

        # ID is correct

        with config.Connect() as cnx:
            cursor = cnx.cursor()

            # Check if the user's team has registered this CTF already
            cursor.execute(
                    'SELECT COUNT(1) FROM ctf '\
                    'WHERE team = %s',
                    (team_id,),
            )
            if cursor.fetchone()[0] != 0:
                # CTF is already registered
                await ctx.respond('You have already signed up for this event!', ephemeral=True)
                return

            # Shouldn't have any issues now so we can defer
            await ctx.defer()
            # CTF not registered yet
            # Create scheduled event
            scheduled_event = await ctx.guild.create_scheduled_event(
                    name=event_info['title'],
                    description=event_info['description'],
                    start_time=event_info['start'],
                    end_time=event_info['finish'],
                    location=event_info['url']
            )

            # Create text channel for CTF
            # Get role id of team
            cursor.execute(
                    'SELECT role FROM teams '\
                    'WHERE id = %s',
                    (team_id,)
            )
            role = cursor.fetchall()[0][0]
            # Define perms
            perms = {
                    ctx.guild.default_role: \
                            discord.PermissionOverwrite(view_channel=False),
                    ctx.guild.me: \
                            discord.PermissionOverwrite(view_channel=True),
                    ctx.guild.get_role(role): \
                            discord.PermissionOverwrite(view_channel=True),
            }
            
            # Check if CTF category exists
            cursor.execute(
                    'SELECT ctf_category FROM teams '\
                    'WHERE id = %s',
                    (team_id,),
            )
            if (ctf_category := ctx.guild.get_channel(cursor.fetchall()[0][0])) not in ctx.guild.categories:
                # Category does not exist, create it first
                ctf_category = await ctx.guild.create_category_channel('CTFs')
                # Update category in db
                cursor.execute(
                        'UPDATE teams SET ctf_category = %s '
                        'WHERE id = %s',
                        (ctf_category.id, team_id),
                )

            # Actually create channel
            ctf_channel = await ctx.guild.create_text_channel(
                    event_info['title'],
                    topic=event_info['url'],
                    overwrites=perms,
                    category=ctf_category,
            )

            # Sync CTF to database
            cursor.execute(
                    'INSERT INTO ctf (ctftime_id, title, description, start, '\
                        'finish, discord, participants, url, logo, team, '\
                        'scheduled_event, channel, archived) '\
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)',
                    (
                        event_id,
                        event_info['title'],
                        event_info['description'],
                        int(time.mktime(event_info['start'].timetuple())),
                        int(time.mktime(event_info['finish'].timetuple())),
                        event_info['discord_inv'],
                        event_info['participants'],
                        event_info['url'],
                        event_info['logo'],
                        team_id,
                        scheduled_event.id,
                        ctf_channel.id,
                    ),
            )
            cnx.commit()

        # Format embed
        embed = discord.Embed(
                title=event_info['title'],
                description=event_info['description'],
                colour=discord.Colour.blurple(),
        )
        embed.set_thumbnail(url=event_info['logo'])
        embed.add_field(
                name='Starts at',
                value=discord.utils.format_dt(event_info['start']),
        )
        embed.add_field(
                name='Ends at',
                value=discord.utils.format_dt(event_info['finish']),
        )
        embed.add_field(
                name='CTFtime',
                value=f'<https://ctftime.org/event/{event_id}>',
        )
        embed.url = event_info['url']
        if event_info['discord_inv'] is not None:
            embed.add_field(
                    name='Discord Server',
                    value=f'[Click here to join!]({event_info["discord_inv"]})',
            )

        # Send embeds
        await ctx.respond(embed=embed)
        msg = await ctf_channel.send(embed=embed)
        await msg.pin()


    # --- /ctf unsignup ---
    @ctf.command(description="Unregister a CTF you've signed up for from the bot.")
    async def unsignup(self, ctx, ctftime_link: str=''):
        team = await config.get_user_team(ctx.author, ctx.guild)
        if team == None:
            # User doesn't have a team
            await ctx.respond('You need to be in a team to use this command', ephemeral=True)
            return

        if ctftime_link == '':
            # No link provided, try to guess CTF from the channel the command was invoked in
            with config.Connect() as cnx:
                cursor = cnx.cursor()
                cursor.execute(
                        'SELECT id FROM ctf '\
                        'WHERE channel = %s',
                        (ctx.channel.id,)
                )
                if (id := cursor.fetchone()) == None:
                    await ctx.respond('CTF cannot be inferred from this context, try again in the CTF channel or with the CTFtime ID.', ephemeral=True)
                    return

                # Unregistering CTF
                await ctx.defer()
                id = id[0]

                # Get CTF details from db
                ctf = cnx.cursor(dictionary=True)
                ctf.execute(
                        'SELECT id, ctftime_id, title, description, start, finish, '\
                        'discord, participants, team, scheduled_event, '\
                        'url, logo, channel, archived FROM ctf '\
                        'WHERE id = %s',
                        (id,),
                )
                ctf = ctf.fetchone()
                # Delete scheduled event
                scheduled_event = ctx.guild.get_scheduled_event(ctf['scheduled_event'])
                try:
                    await scheduled_event.delete()
                except:
                    pass

                # Delete CTF channel
                await ctx.channel.delete()

                # Delete CTF from db
                cursor.execute(
                        'DELETE FROM ctf WHERE id = %s',
                        (id,),
                )
                cnx.commit()
                return
        # Check whether the link is valid
        event_id = regex.search('[0-9]+', ctftime_link)
        if event_id is None:
            # Invalid link
            await ctx.respond("This isn't a valid CTFtime event ID or link.", ephemeral=True)
            return

        # Link seems valid
        event_id = event_id.group()

        team_id = await config.get_user_team(ctx.author, ctx.guild)
        if team_id is None:
            await ctx.respond("You need to be in a team to use this command.", ephemeral=True)
            return

        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Check if team has registered this CTF
            ctf = cnx.cursor(dictionary=True)
            ctf.execute(
                    'SELECT id, ctftime_id, title, description, start, finish, '\
                    'discord, participants, team, scheduled_event, '\
                    'url, logo, channel, archived FROM ctf '\
                    'WHERE team = %s AND ctftime_id = %s ',
                    (team_id, event_id),
            )
            if (ctf := ctf.fetchone()) is None:
                # Team didn't sign up for this CTF
                await ctx.respond("You haven't signed up for this CTF.", ephemeral=True)
                return

            # Team signed up for this CTF
            # We can defer now
            await ctx.defer()

            # Delete scheduled event
            scheduled_event = ctx.guild.get_scheduled_event(ctf['scheduled_event'])
            try:
                await scheduled_event.delete()
            except:
                pass

            # Delete CTF channel
            channel = ctx.guild.get_channel(ctf['channel'])
            try:
                await channel.delete()
            except discord.NotFound:
                pass

            # Delete CTF from db
            cursor.execute(
                    'DELETE FROM ctf WHERE id = %s',
                    (ctf['id'],)
            )
            
            # Format embed
            embed = discord.Embed(title=ctf['title'], description=ctf['description'], colour=discord.Colour.green())
            embed.set_thumbnail(url=ctf['logo'])
            embed.add_field(name="Starts at", value=discord.utils.format_dt(ctf['start']))
            embed.add_field(name="Ends at", value=discord.utils.format_dt(ctf['finish']))
            embed.add_field(name="CTFtime", value=f"https://ctftime.org/event/{event_id}")
            embed.url = ctf['url']

            cnx.commit()
            await ctx.respond(embed=embed)


    # --- task loop to check for CTFs ---
    @tasks.loop(seconds=10.0)
    async def check_ctf(self):
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            ctfs = cnx.cursor(dictionary=True)

            # Get all unarchived CTFs
            ctfs.execute('SELECT * FROM ctf WHERE archived = 0')
            ctfs = ctfs.fetchall()
            for ctf in ctfs:
                if (channel := self.bot.get_channel(ctf['channel'])) is None:
                    # Channel not found, treat this CTF as archived
                    cursor.execute(
                            'UPDATE ctf SET archived = 1 '\
                            'WHERE id = %s',
                            (ctf['id'],),
                    )
                elif datetime.datetime.fromtimestamp(ctf['start']) <= datetime.datetime.now() and ctf['reminded'] != 2:
                    # CTF has started
                    cursor.execute(
                            'UPDATE ctf SET reminded = 2 '\
                            'WHERE id = %s',
                            (ctf['id'],),
                    )

                    # Send reminder
                    # TODO: add option to turn off @everyone
                    embed = discord.Embed(
                            title=ctf['title'],
                            description=ctf['description'],
                            colour=discord.Colour.blurple(),
                    )
                    embed.set_thumbnail(url=ctf['logo'])
                    embed.add_field(
                            name='Starts at',
                            value=discord.utils.format_dt(datetime.datetime.fromtimestamp(ctf['start'])),
                    )
                    embed.add_field(
                            name='Ends at',
                            value=discord.utils.format_dt(datetime.datetime.fromtimestamp(ctf['finish'])),
                    )
                    embed.url = ctf['url']
                    await channel.send('@everyone The CTF is starting!', embed=embed)
                    cnx.commit()
                    return
                elif (datetime.datetime.now() - datetime.datetime.fromtimestamp(ctf['start'])).days == -1 \
                        and ctf['reminded'] != 1:
                    # The CTF will start in 1 day
                    cursor.execute(
                            'UPDATE ctf SET reminded = 1 '\
                            'WHERE id = %s',
                            (ctf['id'],),
                    )
                    # Send reminder
                    # TODO: add option to turn off @everyone
                    embed = discord.Embed(
                            title=ctf['title'],
                            description=ctf['description'],
                            colour=discord.Colour.blurple(),
                    )
                    embed.set_thumbnail(url=ctf['logo']) if ctf['logo'] != None else None
                    embed.add_field(
                            name='Starts at',
                            value=discord.utils.format_dt(datetime.datetime.fromtimestamp(ctf['start'])),
                    )
                    embed.add_field(
                            name='Ends at',
                            value=discord.utils.format_dt(datetime.datetime.fromtimestamp(ctf['finish'])),
                    )
                    embed.url = ctf['url']
                    await channel.send('@everyone The CTF will start in 1 day!', embed=embed)
                    cnx.commit()
                    return
                elif datetime.datetime.now() > datetime.datetime.fromtimestamp(ctf['finish']):
                    # CTF is over
                    cursor.execute(
                            'UPDATE ctf SET archived = 1 '\
                            'WHERE id = %s AND team = %s',
                            (ctf['id'], ctf['team']),
                    )

                    # Get category to archive to
                    cursor.execute(
                            'SELECT archived_category FROM teams '\
                            'WHERE id = %s',
                            (ctf['team'],),
                    )

                    if (archived := self.bot.get_channel(cursor.fetchall()[0][0])) is None:
                        # Archived channel not found, create new
                        # Get guild of channel
                        archived = await channel.guild.create_category_channel('Archived')
                        cursor.execute(
                                'UPDATE teams SET archived_category = %s '\
                                'WHERE id = %s',
                                (archived.id, ctf['team']),
                        )

                    # Place text channel in archived category
                    await channel.edit(category=archived)

                    # Get all members in team and their scores
                    cursor.execute(
                            'SELECT solver, points FROM challenges '\
                            'WHERE team = %s AND ctf = %s AND solved = 1',
                            (ctf['team'], ctf['id']),
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
                            description='Point distribution:\n' + members,
                            colour=discord.Colour.green(),
                    )

                    # Send info
                    cnx.commit()
                    await channel.send('@everyone The CTF has ended!', embed=embed)
                    return


# --- view for custom event menu ---
class CustomEventModal(discord.ui.Modal):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(title="Custom CTF Event Creation")
        # Input for CTF name
        self.add_item(
            discord.ui.InputText(
                label="CTF Name",
                placeholder="Foo CTF",
                style=discord.InputTextStyle.short,
            )
        )

        # Input for CTF description
        self.add_item(
            discord.ui.InputText(
                label="CTF Description",
                placeholder="Lorem ipsum...",
                style=discord.InputTextStyle.long,
                max_length=1000
            )
        )

        # Input for CTF start and end time
        self.add_item(
            discord.ui.InputText(
                label="CTF Duration",
                placeholder="1 Jan 10:00 to 2 Jan 10:00 (timezone in GMT+8)",
                style=discord.InputTextStyle.short,
            )
        )

        # Input for CTF link
        self.add_item(
            discord.ui.InputText(
                label="CTF Link",
                placeholder="https://ctf.foo.com",
                style=discord.InputTextStyle.short,
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Extract data from form
        title = self.children[0].value
        description = self.children[1].value
        duration = self.children[2].value
        duration = duration.replace('+', '-')
        duration = duration.replace('-', '+')
        link = self.children[3].value
        logo = interaction.user.display_avatar.url
        try:
            duration = duration.split(' to ')
            start = datetime.datetime.fromtimestamp(parser.parse(duration[0], ignoretz=True).timestamp(), datetime.timezone.utc)
            finish = datetime.datetime.fromtimestamp(parser.parse(duration[1], ignoretz=True).timestamp(), datetime.timezone.utc)
        except Exception as e:
            # Couldn't parse time
            print(e)
            await interaction.response.send_message('Invalid time specified', ephemeral=True)
            return
        try:
            if start >= finish:
                # Start is after finish
                await interaction.response.send_message('The start time can\'t be after the end time!', ephemeral=True)
                return
            elif datetime.datetime.now(datetime.timezone.utc) >= start or datetime.datetime.now(datetime.timezone.utc) >= finish:
                # Start time or end time before current time
                await interaction.response.send_message('The CTF has already started/is already over.', ephemeral=True)
                return
        except Exception as e:
            print(e)
            # Couldn't parse time
            await interaction.response.send_message('Invalid time specified', ephemeral=True)
            return

        # Format embed
        embed = discord.Embed(
                title=title,
                description=description,
                colour=discord.Colour.blurple()
        )
        embed.url = link
        embed.add_field(
                inline=True,
                name="Starts at",
                value=discord.utils.format_dt(start),
        )
        embed.add_field(
                inline=True,
                name="Ends at",
                value=discord.utils.format_dt(finish),
        )
        embed.set_thumbnail(url=logo)

        with config.Connect() as cnx:
            cursor = cnx.cursor()
            team_id = await config.get_user_team(interaction.user, interaction.guild)

            # Create ctf channel
            cursor.execute(
                    'SELECT ctf_category, role FROM teams '\
                    'WHERE id = %s',
                    (team_id,),
            )
            data = cursor.fetchone()
            role = interaction.user.get_role(data[1])
            ctf_category = data[0]
            perms = {
                    interaction.guild.default_role: \
                            discord.PermissionOverwrite(view_channel=False),
                    interaction.guild.me: \
                            discord.PermissionOverwrite(view_channel=True),
                    role: \
                            discord.PermissionOverwrite(view_channel=True),
            }
            if ctf_category is None or self.bot.get_channel(ctf_category) is None:
                # CTF category does not exist
                ctf_category = await interaction.guild.create_category_channel('CTFs')
                cursor.execute(
                        'UPDATE teams SET ctf_category = %s '\
                        'WHERE id = %s',
                        (ctf_category.id, team_id)
                )
            else:
                ctf_category = interaction.guild.get_channel(ctf_category)

            ctf_channel = await interaction.guild.create_text_channel(
                    title,
                    overwrites=perms,
                    topic=link,
                    category=ctf_category,
            )
            # Send embed into text channel
            # TODO: Pin embed to channel
            await ctf_channel.send(embed=embed)

            # Schedule event
            scheduled_event = await interaction.guild.create_scheduled_event(
                    name=title,
                    description=description,
                    start_time=start,
                    end_time=finish,
                    location=link,
            )

            # Save CTF in db
            cursor.execute(
                    'INSERT INTO ctf (title, description, start, finish, '\
                    'url, logo, team, scheduled_event, channel, archived) '\
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)',
                    (
                        title,
                        description,
                        start.timestamp(),
                        finish.timestamp(),
                        link,
                        logo,
                        team_id,
                        scheduled_event.id,
                        ctf_channel.id,
                    )
            )
            cnx.commit()
            await interaction.response.send_message(embed=embed)



# --- load cog ---
def setup(bot):
    bot.add_cog(CTF(bot))
