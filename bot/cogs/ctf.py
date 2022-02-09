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
# TODO: Add relevant people to relevant channels when they are added to team

class CTF(commands.Cog):
    """ CTFs are managed here. With signup, you can register a CTF to take \
    part in, and never miss another CTF again with automatic Discord event \
    scheduling! To view details about a CTF, use /ctf details."""

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    ctf = SlashCommandGroup('ctf', 'Group of commands for CTF management', guild_ids=config.beta_guilds)

    @ctf.command(
            description="View details about an event in a nicely formatted embed."
    )
    async def details(self, ctx, ctftime_link: str=''):
        if ctftime_link == '':
            embed = discord.Embed(
                    title="CTF name",
                    description="Please send the CTF name in chat.", 
                    colour=discord.Colour.green()
            )
            embed.set_footer(
                    text="What's this? No CTFtime link was detected, so you are making a custom event now."
            )
            await ctx
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
        else:
            # Search for the ID in link
            event = regex.search("[0-9]+", ctftime_link)
            event_id = event.group()
            # Required, if not CTFtime will 403
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0",
            }
            # Get JSON via API
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                # ID is incorrect - got 404
                embed = discord.Embed(
                    title="Error!",
                    description="Sorry, this isn't a valid CTFtime event link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                # Parse the JSON
                event_json = req.content
                event_info = json.loads(event_json)
                title = event_info["title"]
                desc = event_info["description"]
                if len(desc) > 1000:
                    desc = desc[:997] + '...'
                participants = event_info["participants"]
                # Timings are in ISO format - convert to datetime.datetime object
                start = datetime.datetime.fromisoformat(event_info["start"])
                finish = datetime.datetime.fromisoformat(event_info["finish"])
                # Refers to the event CTF url
                url = event_info["url"]
                logo_url = event_info["logo"]
                # Format embed
                embed = discord.Embed(title=title, description=desc, colour=discord.Colour.blurple())
                embed.set_thumbnail(url=logo_url)
                embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
                embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
                embed.add_field(name="CTFtime", value=f"<https://ctftime.org/event/{event_id}>")
                embed.set_footer(
                        text=f"{participants} participants"
                )
                embed.url = url
                # walrus kool :)
                if discord_inv := regex.search(
                    "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                    desc,
                ):
                    # Discord invite link found
                    embed.add_field(
                        name="Discord Server",
                        value=f"[Click here to join]({discord_inv.group()})",
                    )
        await ctx.respond(embed=embed)

    @ctf.command(
            description="Sign up for an upcoming CTF, and register it to the bot."
    )
    async def signup(self, ctx, link):
        await ctx.defer()
        # Check whether the link is valid
        p = regex.match(
            "((https://)|(http://))?(www.)?ctftime.org/event/[0-9]+(/)?", link
        )
        if p is None and regex.match("[0-9]+", link) is None:
            # The link is neither valid nor a possible CTFtime event ID
            embed = discord.Embed(
                title="Failed",
                description="Sorry, this isn't a valid CTFtime event link or id.",
                colour=discord.Colour.red(),
            )
        else:
            # Try to grab the event ID from the link
            event = regex.search("[0-9]+", link)
            event_id = event.group()
            # Required, if not CTFtime will 403
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0)" \
                                "Gecko/20100101 Firefox/61.0",
            }
            # Get JSON via API
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                # Invalid event ID
                embed = discord.Embed(
                    title="Failed",
                    description="Sorry, this isn't a valid CTFtime event " \
                                "link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                # TODO: Get stuff from db instead, and remove CTFtime api verification (in case event gets yeeted from CTFtime)
                # Parse JSON
                event_json = req.content
                event_info = json.loads(event_json)
                title = event_info["title"]
                desc = event_info["description"]
                if len(desc) > 1000:
                    desc = desc[:997] + '...'
                participants = event_info["participants"]
                start = datetime.datetime.fromisoformat(event_info["start"])
                finish = datetime.datetime.fromisoformat(event_info["finish"])
                # Refers to the CTF link
                url = event_info["url"]
                logo_url = event_info["logo"]
                # Format embed
                embed = discord.Embed(title=title, description=desc)
                embed.set_thumbnail(url=logo_url)
                embed.add_field(name="Starts at", value=discord.utils.format_dt(start))
                embed.add_field(name="Ends at", value=discord.utils.format_dt(finish))
                embed.add_field(name="CTFtime", value=f"https://ctftime.org/event/{event_id}")
                embed.url = url
                if discord_inv := regex.search(
                    "((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?",
                    desc,
                ):
                    # Discord invite found
                    embed.add_field(
                        name="Discord Server",
                        value=f"[Click here to join]({discord_inv.group()})",
                    )
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
                        # Change embed colour to blurple as a hint to the user 
                        embed.colour = discord.Colour.blurple()
                        embed.set_footer(
                                text="You have already signed up for this event!"
                        )
                        # Update the relevant information in case it has changed
                        # TODO: add discord invite
                        cursor.execute(
                            "UPDATE ctf AS c " \
                            "INNER JOIN team_members AS m ON c.team = m.team " \
                            "INNER JOIN teams AS t ON m.team = t.id " \
                            "SET c.description = %s, c.start = %s, c.finish = %s, " \
                            "WHERE m.member = %s AND t.guild = %s",
                            (
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
                                ctx.author.id,
                                ctx.guild.id
                            )
                        )
                    else:
                        # CTF not registered yet
                        # Green to inform the user that the CTF has been added successfully
                        embed.colour = discord.Colour.green()
                        embed.set_footer(
                                text="Successfully signed up for this event!"
                        )
                        # Create scheduled event
                        scheduled_event = await ctx.guild.create_scheduled_event(
                                name=title,
                                description=desc + f'\nCTFtime:\nhttps://ctftime.org/event/{event_id}',
                                start_time=start,
                                end_time=finish,
                                location=url
                        )
                        # Add CTF into db
                        # TODO: add discord inv
                        cursor.execute(
                                "INSERT INTO ctf (id, title, description, start, " \
                                    "finish, team, scheduled_event, archived) " \
                                "SELECT %s, %s, %s, %s, %s, t.id, %s, 0 FROM teams AS t " \
                                "INNER JOIN team_members AS m ON m.team = t.id " \
                                "WHERE m.member = %s AND t.guild = %s ",
                            (
                                event_id,
                                title,
                                desc,
                                int(time.mktime(start.timetuple())),
                                int(time.mktime(finish.timetuple())),
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
                        team_id = cursor.fetchone()[0]
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
                                title,
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

    @ctf.command(
            description="Un-signup for a CTF, unregistering it from the bot."
    )
    async def unsignup(self, ctx, ctftime_link: str):
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
        else:
            # Try to grab the event ID from the link
            event = regex.search("[0-9]+", ctftime_link)
            event_id = event.group()
            # Required, if not CTFtime will 403
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0)" \
                                "Gecko/20100101 Firefox/61.0",
            }
            # Get JSON via API
            req = requests.get(
                f"https://ctftime.org/api/v1/events/{event_id}/", headers=headers
            )
            if req.status_code == 404:
                # Invalid event ID
                embed = discord.Embed(
                    title="Failed",
                    description="Sorry, this isn't a valid CTFtime event " \
                                "link or id.",
                    colour=discord.Colour.red(),
                )
            else:
                with mysql.connector.connect(
                        host=config.MYSQL_DB,
                        port=3306,
                        database='ctfcord',
                        username='root',
                        password=config.MYSQL_PW
                ) as cnx:
                    cursor = cnx.cursor()
                    # Check if the team has registered this CTF
                    cursor.execute(
                            'SELECT t.id FROM ctf AS c ' \
                            'INNER JOIN teams AS t ON c.team = t.id ' \
                            'INNER JOIN team_members AS m ON t.id = m.team ' \
                            'WHERE c.id = %s AND t.guild = %s AND m.member = %s',
                            (event_id, ctx.guild.id, ctx.author.id)
                    )
                    if (team_id := cursor.fetchone()) is not None:
                        # Team has registered this CTF
                        # Parse JSON
                        event_json = req.content
                        event_info = json.loads(event_json)
                        title = event_info["title"]
                        desc = event_info["description"]
                        if len(desc) > 1000:
                            desc = desc[:997] + '...'
                        participants = event_info["participants"]
                        start = datetime.datetime.fromisoformat(event_info["start"])
                        finish = datetime.datetime.fromisoformat(event_info["finish"])
                        # Refers to the CTF link
                        url = event_info["url"]
                        logo_url = event_info["logo"]
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
                                'SELECT c.scheduled_event FROM ctf AS c ' \
                                'INNER JOIN teams AS t ON c.team = t.id ' \
                                'WHERE c.id = %s',
                                (event_id,)
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
                                'WHERE team = %s AND id = %s',
                                (team_id[0], event_id)
                        )
                        channel = ctx.guild.get_channel(cursor.fetchone()[0])
                        try:
                            await channel.delete()
                        except:
                            pass
                        # Delete CTF from db
                        cursor.execute(
                                'DELETE FROM ctf WHERE team = %s AND id = %s',
                                (team_id[0], event_id)
                        )
                        embed.set_footer(
                                text="The event has been successfully unregistered."
                        )
                        cnx.commit()
                    else:
                        embed = discord.Embed(
                                title="Failed",
                                description="Sorry, you have not signed up " \
                                            "for this event.",
                                colour=discord.Colour.red()
                                )

            await ctx.respond(embed=embed)
    
    @tasks.loop(seconds=300.0)
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
            # Get all CTFs and the time which they start
            ctfs.execute('SELECT * FROM ctf')
            for ctf in ctfs:
                if datetime.datetime.fromtimestamp(ctf['start']) == datetime.datetime.now():
                    # CTF has started
                    channel = self.bot.get_channel(ctf['channel'])
                    # TODO: add option to turn off @everyone
                    embed = discord.Embed(
                            title=ctf['title'],
                            description='@everyone This CTF has started!',
                            colour=discord.Colour.blurple()
                    )
                    await channel.send(embed=embed)
                    return
                elif (datetime.datetime.now() - datetime.datetime.fromtimestamp(ctf['start'])).days == -1:
                    # CTF will start in a day's time
                    channel = self.bot.get_channel(ctf['channel'])
                    embed = discord.Embed(
                            title=ctf['title'],
                            description='The CTF will start in 1 day!',
                            colour=discord.Colour.blurple()
                    )
                    await channel.send(embed=embed)
                    return
                elif (datetime.datetime.now() - datetime.datetime.fromtimestamp(ctf['finish'])) > datetime.timedelta(0):
                    # CTF is over, archive it
                    channel = self.bot.get_channel(ctf['channel'])
                    guild = channel.guild
                    cursor.execute(
                            'SELECT archived_category FROM teams '\
                            'WHERE id = %s',
                            (ctf['team'],)
                    )
                    archived = cursor.fetchone()[0]
                    archived = self.bot.get_channel(archived)
                    await channel.edit(category=archived)
                    # Get all members in team and their scores
                    cursor.execute(
                            'SELECT solver, points FROM challenges '\
                            'WHERE team = %s',
                            (ctf['team'],)
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
                    members = '\n'.join([f'{m}: {members[m]} points ({round(members[m] / total * 100, 1)}%)' for m in members])
                    embed = discord.Embed(
                            title=ctf['title'],
                            description='@everyone The CTF has ended! Below are the percentage points of each team member:\n' + 'members',
                            colour=discord.Colour.green()
                            )
                    cursor.execute('UPDATE ctf SET archived = 0 WHERE ctf = %s AND team = %s', (ctf['id'], ctf['team']))
                    cnx.commit()
                    await channel.send(embed=embed)
    chall = SlashCommandGroup('chall', 'Group of commands relating to challenges', guild_ids=config.beta_guilds)
    
    @chall.command(
            description="Mark a challenge as in progress."
    )
    async def solved(self, ctx, chall_name: str, points: int=0):
        # How this command should work
        # 1. Get the CTF this challenge belongs to based on the channel this command is invoked in
        # 2. Record the challenge in MySQL in the challenges table 
        with mysql.connector.connect(
                host=config.MYSQL_DB,
                port=3306,
                database='ctfcord',
                user='root',
                password=config.MYSQL_PW
        ) as cnx:
            cursor = cnx.cursor()
            cursor.execute(
                    'SELECT id FROM ctf WHERE channel = %s',
                    (ctx.channel.id,)
            )
            ctf = cursor.fetchone()[0]
            cursor.execute(
                    'REPLACE INTO challenges (name, points, ctf, solver, team, solved) '\
                    'SELECT %s, %s, %s, m.member, t.id, 1 FROM teams AS t '\
                    'INNER JOIN team_members AS m ON m.team = t.id '\
                    'WHERE m.member = %s AND t.guild = %s',
                    (chall_name, points, ctf, ctx.author.id, ctx.guild.id)
            )
            embed = discord.Embed(
                    title='Congrats',
                    description=f'<@!{ctx.author.id}> solved {chall_name}!',
                    colour=discord.Colour.green()
            )
            cursor.execute(
                    'SELECT name, points FROM challenges '\
                    'WHERE solver = %s AND solved = 1',
                    (ctx.author.id,)
            )
            solved = cursor.fetchall()
            embed.add_field(
                    name=f'You have solved:',
                    value='\n'.join([chall[0] if chall[1] == 0 else f'{chall[0]} ({chall[1]} point)' for chall in solved])
            )
            cnx.commit()
        await ctx.respond(embed=embed)
    
class CustomEvent(discord.ui.Select):
    def __init__(self):
        options = [
                discord.SelectOption(
                    label="CTF Name",
                    description="Edit the CTF's name",
                    value="title"
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
            r = await interaction.response.send_message(content="Please send the CTF's title in chat now.", ephemeral=True)
            try:
                title = await client.wait_for('message', check=check, timeout=60.0)
            except:
                await interaction.edit_original_message(content="Timeout")
                return
            else:
                await interaction.delete_original_message()
                await interaction.message.edit(embed=embed)

def setup(bot):
    bot.add_cog(CTF(bot))
