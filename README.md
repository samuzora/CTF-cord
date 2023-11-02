# CTF-cord

A Discord bot for all your CTF management needs. 

## Features

* CTF details pulled from CTFtime and converted into an embed
* Private channels

[Add it to your server!](https://discord.com/api/oauth2/authorize?client_id=934122115366547526&permissions=541434768464&scope=bot%20applications.commands)

## Documentation

### /ctf

#### `/ctf register <team_name> <ctftime_link>`

* `team_name: str`
* `ctftime_link: str`
	* Link to the CTF on CTFtime, can also be the 4-digit ID of the CTF (the last 4 digits in the CTFtime link)

## Installation

Dependencies:

- `docker`
- `docker-compose`
- `docker-buildx-plugin`

```bash
git clone https://github.com/samuzora/CTF-cord
cd ./CTF-cord/
vim .env # Fill in the environment variables
DOCKER_BUILDKIT=1 docker-compose up --build -d
```
