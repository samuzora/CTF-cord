# CTF-cord v2

A Discord bot for all your CTF management needs. 

## Features

* CTF details scraped from CTFtime
* Private channels with reaction-based permission management
- Scheduled events
- Creation of challenge threads

## Limitations

The server owner can always see the channel even when not opting-in, due to
having administrator privileges. If this is an issue, server ownership can be
transferred to a non-participating third-party.

## Data privacy

For privacy purposes, you should host an instance of the bot for your own
team. You can create a Discord application from the Discord developer console,
and create an invite with the required permissions to add it to your server.

## Required intents, permissions and scopes

Intents:

`members`

Scope:

`bot`, `applications.commands`

Permissions (17927193521232):

- `Manage channels`
- `View channels`
- `Manage events`
- `Create events`
- `Send messages`
- `Create public threads`
- `Send messages in threads`
- `Manage messages`
- `Manage threads`
- `Embed links`
- `Add reactions`

## Deployment

Just set the BOT_TOKEN environment variable in a .env file, and run `docker compose up`
