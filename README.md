# CTF-cord

## What is this?
A Discord bot for all your CTF management needs. 

## What can this bot do?
- Manage CTF teams in a guild (currently, you can only have one team per guild; this might change in the future)
	- Role-based teams: to add someone to your team, just give him your team's role!
	- Private channels for each CTF 
	- (Guild == Server)

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

## Might be added
- Search for event by name and year
- List events on CTFtime within a certain date range
- List all events signed up for
- Team contribution across all CTFs 
