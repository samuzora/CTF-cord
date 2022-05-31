from datetime import datetime, time, timezone, timedelta
import json
import secrets

from dateutil import parser, tz
import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
import regex
import requests

import config

# TODO: Add /archive command to allow users to archive a CTF manually

# === CLASSES ===
# --- view for custom event menu ---
class CustomEventModal(discord.ui.Modal):
    def __init__(self, bot, ctx, team_name, users):
        self.bot = bot
        self.ctx = ctx
        self.team_name = team_name
        self.users = users
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
        event_info = {}
        event_info["title"] = self.children[0].value
        event_info["description"] = self.children[1].value
        duration = self.children[2].value
        event_info["url"] = self.children[3].value
        event_info["logo"] = interaction.user.display_avatar.url

        # to force timezone
        default_date = datetime.combine(datetime.now(), time(0, tzinfo=tz.gettz('Asia/Singapore')))
        try:
            duration = duration.split(' to ')
            event_info["start"] = datetime.fromtimestamp(parser.parse(duration[0], ignoretz=True, default=default_date).timestamp())
            event_info["finish"] = datetime.fromtimestamp(parser.parse(duration[1], ignoretz=True, default=default_date).timestamp())
        except:
            # Couldn't parse time
            await interaction.response.send_message('Invalid time specified', ephemeral=True)
            return
        if event_info["start"] >= event_info["finish"]:
            # Start is after finish
            await interaction.response.send_message('The start time can\'t be after the end time!', ephemeral=True)
            return
        elif datetime.now() >= event_info["start"] or datetime.now() >= event_info["finish"]:
            # Start time or end time before current time
            await interaction.response.send_message('The CTF has already started/is already over.', ephemeral=True)
            return

        # Format embed
        embed = discord.Embed(
                title=event_info["title"],
                description=event_info["description"],
                colour=discord.Colour.blurple()
        )
        embed.url = event_info["url"]
        embed.add_field(
                inline=True,
                name="Starts at",
                value=discord.utils.format_dt(event_info["start"]),
        )
        embed.add_field(
                inline=True,
                name="Ends at",
                value=discord.utils.format_dt(event_info["finish"]),
        )
        embed.set_thumbnail(url=event_info["logo"])

        # Reply to the modal
        await interaction.response.send_message(embed=embed)

        # Create team
        role = await create_team(self.ctx, self.team_name, self.users)

        # Create ctf channel
        channel, team_id = await create_ctf_channel(self.ctx, role, event_info)

        # Send embed into text channel
        msg = await channel.send(embed=embed)
        await msg.pin()

        # Schedule event
        scheduled_event = await interaction.guild.create_scheduled_event(
                name=event_info["title"],
                description=event_info["description"],
                start_time=event_info["start"],
                end_time=event_info["finish"],
                location=event_info["url"],
        )

        with config.Connect() as cnx:
            cursor = cnx.cursor()

            # Save CTF in db
            cursor.execute(
                    'INSERT INTO ctf (title, description, start, finish, '\
                    'url, logo, team, scheduled_event, channel, archived) '\
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0)',
                    (
                        event_info["title"],
                        event_info["description"],
                        event_info["start"].timestamp(),
                        event_info["finish"].timestamp(),
                        event_info["url"],
                        event_info["logo"],
                        team_id,
                        scheduled_event.id,
                        channel.id,
                    )
            )
            cnx.commit()

# --- view requesting team info ---
# This modal is archived for now, until pycord supports modals as followups
class TeamInfoModal(discord.ui.Modal):
    def __init__(self, bot, channel, embed, team_name):
        self.bot = bot
        self.target_channel = channel
        self.embed = embed
        super().__init__(title="Team Info")
        # Team name
        self.add_item(
            discord.ui.InputText(
                label="Team name aka. team username to log in",
                placeholder="Foobar",
                style=discord.InputTextStyle.short,
                value=team_name,
            )
        )

        # Team password
        self.add_item(
            discord.ui.InputText(
                label="Team password",
                placeholder="Strong password here...",
                style=discord.InputTextStyle.short,
                required=False,
            )
        )


    async def callback(self, interaction: discord.Interaction):
        # Extract data from form
        team_name = self.children[0].value
        if (password := self.children[1].value) == '':
            password = secrets.token_urlsafe(30)

        # Format embed
        embed = self.embed.copy()
        embed.add_field(
                name="Creds",
                value=password,
                inline=True
        )

        # Send embed into designated ctf channel
        msg = await self.target_channel.send(embed=embed)
        await msg.pin()

# === FUNCTIONS ===
# --- internal function to get CTF details ---
async def get_ctf_details(ctftime_link):
    # Check whether the link is valid
    event_id = regex.search('[0-9]+', ctftime_link)
    if event_id is None:
        # The link is not valid
        return False
    else:
        event_id = event_id.group()
    
    headers = {
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"
    } # CTFtime will 403 if this is not added

    # Grab JSON via API
    req = requests.get(
            f'https://ctftime.org/api/v1/events/{event_id}/', headers=headers,
    )
    if req.status_code == 404:
        # API returned 404
        return False

    # ID is valid
    event_info = json.loads(req.content)
    if len(event_info['description']) > 1000:
        event_info['description'] = event_info['description'][:997] + '...'
    event_info['start'] = datetime.fromisoformat(event_info['start'])
    event_info['finish'] = datetime.fromisoformat(event_info['finish'])
    event_info['discord_inv'] = regex.search(
            '((https://)?|(https://)?)(www.)?discord.(gg|(com/invite))/[A-Za-z0-9]+/?',
            event_info['description'],
    )
    event_info['id'] = event_id
    return event_info

# --- internal function to convert event details to embed ---
async def details_to_embed(event_info):
    # ID is correct, formatting embed
    embed = discord.Embed(
            title=event_info['title'],
            description=event_info['description'],
            colour=discord.Colour.random()
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
            value=f'<https://ctftime.org/event/{event_info["id"]}>',
    )
    embed.url = event_info['url']
    if event_info.get('discord_inv') is not None:
        embed.add_field(
                name='Discord Server',
                value=f'[Click here to join!]({event_info["discord_inv"]})',
        )
    return embed

# --- internal function to get team based on channel ---
async def get_team(ctx):
    with config.Connect() as cnx:
        cursor = cnx.cursor()
        cursor.execute('SELECT id FROM teams WHERE channel = %s', (ctx.channel.id,))
        team = cursor.fetchone()
    if team != None:
        return team[0]
    else:
        return False

# --- internal function to create team ---
async def create_team(ctx, name, users):
    # Create role and assign to all relevant members
    role = await ctx.guild.create_role(name=name, color=discord.Color.random())
    """for member in members:
        try:
            await member.add_roles(role)
        except discord.errors.HTTPException:
            logging.warning(f'Could not add {role} to {member}')
    """
    for user in users:
        await user.add_roles(role)
    # Return the new team's id
    return role

# --- internal function to create channel for ctf ---
async def create_ctf_channel(ctx, role, event_info):
    # Create channel and allow access to ppl w the team role
    # Define perms
    perms = {
        ctx.guild.default_role: \
            discord.PermissionOverwrite(view_channel=False),
        ctx.guild.me: \
            discord.PermissionOverwrite(view_channel=True),
        role: \
            discord.PermissionOverwrite(view_channel=True),
        }

    # Create channel
    ctf_channel = await ctx.guild.create_text_channel(
            event_info['title'],
            topic=event_info['url'],
            overwrites=perms,
    )

    # Update db with new team info
    with config.Connect() as cnx:
        cursor = cnx.cursor()
        cursor.execute(
                'INSERT INTO teams (name, role, guild, channel) '\
                'VALUES (%s, %s, %s, %s)', 
                (role.name, role.id, ctx.guild.id, ctf_channel.id)
        )
        cursor.execute('SELECT LAST_INSERT_ID()')
        team = cursor.fetchone()[0]
        cnx.commit()

    return ctf_channel, team

# === SLASH COMMANDS ===
# --- /ctf --- 
class CTF(commands.Cog):
    ''' CTFs are managed here. With /ctf signup, you can register a CTF to take \
    part in, and never miss another CTF again with automatic Discord event \
    scheduling! To view details about a CTF, use /ctf details.'''


    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.check_ctf.start()
        self.update_ctftime.start()


    # --- slash command group ---
    ctf = SlashCommandGroup('ctf', 'Group of commands for CTF management', guild_ids=config.beta_guilds)


    # --- /ctf details ---
    @ctf.command(description='View details about an event in a nicely formatted embed.')
    async def details(self, ctx, ctftime_link: str):
        event_info = await get_ctf_details(ctftime_link)
        if event_info == False:
            # CTF doesn't exist
            await ctx.respond("This isn't a valid CTFtime event link or id.", ephemeral=True)
            return

        embed = await details_to_embed(event_info)
        await ctx.respond(embed=embed)


    # --- /ctf signup ---
    @ctf.command(description='Sign up for an upcoming CTF, and register it to the bot.')
    async def signup(
            self, 
            ctx, 
            team_name: discord.Option(str, "Your team name for this CTF"),
            ctftime_link: discord.Option(str, "Link to CTF on CTFtime, can optionally be the 4-digit ID of the CTF.", default=''),
            user1: discord.Option(discord.Member, "Addtional team members", default=None),
            user2: discord.Option(discord.Member, "Addtional team members", default=None),
            user3: discord.Option(discord.Member, "Addtional team members", default=None),
            user4: discord.Option(discord.Member, "Addtional team members", default=None),
    ):
        # Get all users (sry for ugly)
        users = [ctx.author]
        if user1:
            users.append(user1)
        if user2:
            users.append(user2)
        if user3:
            users.append(user3)
        if user4:
            users.append(user4)

        # If no ctftime link given, means user wants to make a custom event
        if ctftime_link == '':
            # Send modal to create custom event
            await ctx.send_modal(CustomEventModal(self.bot, ctx, team_name, users))
            return

        # Get CTF details
        event_info = await get_ctf_details(ctftime_link)
        if event_info == False:
            # CTF doesn't exist
            await ctx.respond("This isn't a valid CTFtime event link or id.", ephemeral=True)
            return

        # Check if timing is valid
        if datetime.now(timezone.utc) > event_info['finish']:
            # CTF has already ended
            await ctx.respond('This CTF is already over.', ephemeral=True)
            return
        elif datetime.now(timezone.utc) > event_info['start']:
            # Start time cannot be in the past 
            # Add a 5 second buffer to account for lag
            event_info['start'] = datetime.now(timezone.utc) + timedelta(seconds=5)

        # Let's defer
        await ctx.defer()

        # Create team
        role = await create_team(ctx, team_name, users)

        # Create text channel for CTF
        channel, team_id = await create_ctf_channel(ctx, role, event_info)

        embed = await details_to_embed(event_info)
        # Send modal to request for team info
        # await ctx.send_modal(TeamInfoModal(self.bot, channel, embed, team_name)) # this will error with InteractionNotFound if 3 seconds has passed since invocation
        # a fix would be to defer, but i haven't figured out how to defer and then send a modal as a followup
        # or js pray it doesn't time out
        # or nvm i won't support this (see note at TeamInfoModal)

        # Create scheduled event
        scheduled_event = await ctx.guild.create_scheduled_event(
                name=event_info['title'],
                description=event_info['description'],
                start_time=event_info['start'],
                end_time=event_info['finish'],
                location=event_info['url']
        )

        # Send embeds to respective channels
        msg = await channel.send(embed=embed)
        await msg.pin()
        await ctx.respond(embed=embed) 

        # Update db with ctf details
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Sync CTF to database
            cursor.execute(
                    'INSERT INTO ctf (ctftime_id, title, description, start, '\
                        'finish, discord, participants, url, logo, team, '\
                        'scheduled_event, channel, archived) '\
                    'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)',
                    (
                        event_info['id'],
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
                        channel.id,
                    ),
            )
            cnx.commit()


    # --- /ctf unsignup ---
    @ctf.command(description="Unregister a CTF you've signed up for from the bot. Must be used in the designated CTF channel.")
    async def unsignup(self, ctx):
        team = await get_team(ctx)
        if team == False:
            # Command wasn't invoked in a team channel
            await ctx.respond('You need to use this command in the designated CTF channel.', ephemeral=True)
            return

        # Guess CTF from the channel the command was invoked in
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Unregistering CTF
            await ctx.defer()

            # Get CTF details from db
            ctf = cnx.cursor(dictionary=True)
            ctf.execute(
                    'SELECT id, ctftime_id, title, description, start, finish, '\
                    'discord, participants, team, scheduled_event, '\
                    'url, logo, channel, archived FROM ctf '\
                    'WHERE team = %s',
                    (team,),
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
                    'DELETE FROM ctf WHERE team = %s',
                    (team,),
            )

            # Delete team 
            cursor.execute(
                    'SELECT role FROM teams WHERE id = %s',
                    (team,)
            )
            role = cursor.fetchone()[0]
            role = ctx.guild.get_role(role)
            await role.delete()

            cursor.execute(
                    'DELETE FROM teams WHERE id = %s',
                    (team,)
            )
            cnx.commit()


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
                elif datetime.fromtimestamp(ctf['start']) <= datetime.now() and ctf['reminded'] != 2:
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
                            value=discord.utils.format_dt(datetime.fromtimestamp(ctf['start'])),
                    )
                    embed.add_field(
                            name='Ends at',
                            value=discord.utils.format_dt(datetime.fromtimestamp(ctf['finish'])),
                    )
                    embed.url = ctf['url']
                    await channel.send('@everyone The CTF is starting!', embed=embed)
                    cnx.commit()
                    return
                elif (datetime.now() - datetime.fromtimestamp(ctf['start'])).days == -1 \
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
                            value=discord.utils.format_dt(datetime.fromtimestamp(ctf['start'])),
                    )
                    embed.add_field(
                            name='Ends at',
                            value=discord.utils.format_dt(datetime.fromtimestamp(ctf['finish'])),
                    )
                    embed.url = ctf['url']
                    await channel.send('@everyone The CTF will start in 1 day!', embed=embed)
                    cnx.commit()
                    return
                elif datetime.now() > datetime.fromtimestamp(ctf['finish']):
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


    # --- task loop to update CTFtime
    @tasks.loop(hours=1.0)
    async def update_ctftime(self):
        # only run loop at 8am GMT+8
        if datetime.now().hour != 8:
            return
        with config.Connect() as cnx:
            cursor = cnx.cursor()
            # Get all guilds that configured the updates to send on this day of the week
            day = datetime.now().weekday()
            cursor.execute(
                    'SELECT ctftime_channel FROM guilds WHERE ctftime_send_day = %s AND ctftime_channel IS NOT NULL',
                    (day,)
            )
            channel_ids = cursor.fetchall()

        # Get all CTFs that start in a week
        start, finish = int(datetime.now().timestamp()), int((datetime.now() + timedelta(days=7)).timestamp())
        headers = {
                "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:61.0) Gecko/20100101 Firefox/61.0"
        } # CTFtime will 403 if this is not added
        req = requests.get(f'https://ctftime.org/api/v1/events/?limit=100&start={start}&finish={finish}', headers=headers)
        embeds = []
        for ctf in json.loads(req.content):
            ctf['start'], ctf['finish'] = datetime.fromisoformat(ctf['start']), datetime.fromisoformat(ctf['finish'])
            embeds.append(await details_to_embed(ctf))

        # Send embeds
        for channel_id in channel_ids:
            channel = await self.bot.fetch_channel(channel_id[0])
            await channel.send(embeds=embeds)

# --- load cog ---
def setup(bot):
    bot.add_cog(CTF(bot))
