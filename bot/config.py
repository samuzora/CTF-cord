import os

import mysql.connector

MYSQL_PW = os.getenv('MYSQL_ROOT_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB')
prefix = None
beta_guilds = [a.strip() for a in open('beta_guilds.txt').readlines()]
beta_guilds = beta_guilds if beta_guilds != [] else None

# --- class to connect to db ---
class Connect():
    def __enter__(self):
        cnx = mysql.connector.connect(
                host=MYSQL_DB,
                port=3306,
                database='ctfcord',
                user='root',
                password=MYSQL_PW
        )
        self.cnx = cnx
        return cnx
    
    def __exit__(self, type, value, traceback):
        self.cnx.close()

# --- internal command to get user's team ---
async def get_user_team(user, guild):
    with Connect() as cnx:
        cursor = cnx.cursor()
        # lord forgive me for sqli
        cursor.execute(
                'SELECT id FROM teams '\
                f'WHERE guild = %s AND role IN ({", ".join([str(role.id) for role in user.roles])})',
                (guild.id,),
        )
        try:
            return cursor.fetchall()[0][0]
        except IndexError:
            return None
