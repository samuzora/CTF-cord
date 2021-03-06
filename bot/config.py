import os

import mysql.connector

MYSQL_PW = os.getenv('MYSQL_ROOT_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB')
prefix = None
try:
    beta_guilds = [a.strip() for a in open('beta_guilds.txt').readlines()]
    beta_guilds = beta_guilds if beta_guilds != [] else None
except:
    beta_guilds = None

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
