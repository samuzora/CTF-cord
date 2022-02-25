import os

MYSQL_PW = os.getenv('MYSQL_ROOT_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB')
prefix = None
beta_guilds = open('beta_guilds.txt').readlines().strip().close()
