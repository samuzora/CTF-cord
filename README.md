# CTF-cord

## What is this?

A Discord bot for all your CTF management needs. 

## What can this bot do?

- Manage CTF teams in a guild (1 team to be created manually per CTF)
	- Role-based teams: to add someone to your team, just give him your team's role!
	- Private channels for each CTF 

- Create CTF events from CTFtime link
	- Just send the link of the CTF and let the bot do the rest!

- Custom CTF event support
	- On invocation, summons a form to fill in
	- Automatic channel creation and event scheduling
	- Smart parsing of CTF duration through Python's dateutil.parser
	- Note: timezone is in GMT+8 (SGT)

- Displays relevant info about a CTF from ctftime.org as a pretty-printed embed. Includes:
	- Hyperlinked CTF platform in title
	- Automatic search for Discord server invite link
	- Start and end times in Discord dynamic time

- Creates and schedules events in Discord for registered CTFs
	- Creates a text channel for that CTF under "CTF" category
	- Sends a reminder 1 day before the CTF starts, and when the CTF starts
	- After the CTF is over, move the CTF text channel to "Archived" category

- Track challenges solved and team contribution per CTF
	- Create thread for challenge when solving
	- Challenges can be marked as solved, and at the end of the CTF, the points of that challenge can be set and the team contribution will be calculated by the bot.


## What will this bot not do?

- Sign up for CTFs automagically (whether on CTFtime or the platform itself)
- Submit flags for you

## Documentation

### /ctf

#### `/ctf details <ctftime_link>`

> View details about a CTF on CTFtime

##### Parameters:
* `ctftime_link: str`
	* Link to the CTF on CTFtime, can also be the 4-digit ID of the CTF (the last 4 digits in the CTFtime link)

#### `/ctf signup <team_name> <ctftime_link:optional> <userX:optional>`

> Register for a CTF and let the bot handle the rest. This will create a channel designated for that CTF. All CTF-related commands must be used in that channel. 

##### Parameters:
* `team_name: str`
	* Your team's name for that CTF, used to create roles for the team
* `ctftime_link: str = ''`
	* Link to the CTF on CTFtime, can also be the 4-digit ID of the CTF. If left blank, a custom CTF (not based on CTFtime) can be created
* `users1-4`: discord.User = None
	* Can be used to add users to your team. Currently, up to a maximum of 5 members inclusive of yourself can be added to a team

##### `/ctf unsignup`

> Un-register for a CTF. This command must be invoked in the designated CTF channel

*Must be invoked from the designated CTF channel*

### /chall

#### `/chall solved <chall_name> <chall_points:optional>`

> Mark a challenge as solved and optionally specify the points the challenge is worth. 

##### Parameters:

* `chall_name: str`
	* Name of the challenge
* `chall_points: int = 0`
	* Challenge score, can be omitted

#### `/chall solving <chall_category> <chall_name>`

> Create a thread for the challenge.

##### Parameters:
* `chall_category: str`
	* Challenge category, used to create thread for the challenge
* `chall_name: str`
	* Challenge name, used to create thread for the challenge

## Might be added

- Search for event by name and year
- List events on CTFtime within a certain date range
- List all events signed up for


