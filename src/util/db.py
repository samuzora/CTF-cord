import os

import ZODB

from persistent import Persistent
import BTrees

db = None


class Ctf(Persistent):
    def __init__(self, channel_id: int, join_message_id: int):
        self.channel_id: int = channel_id
        self.join_message_id: int = join_message_id
        self.challenges: list[Challenge] = []


class Challenge(Persistent):
    def __init__(self, name: str, worked_on: int):
        self.name: str = name
        self.worked_on: int = worked_on
        self.solved_by: int = 0
        self.flag: str = ""

    def solve(self, solved_by: int, flag: str):
        self.solved_by = solved_by
        self.flag = flag

def get_conn():
    global db
    if not db:
        path = os.path.expanduser("~/.local/share/ctf-cord/")
        if not os.path.exists(path):
            os.mkdir(path)
        db = ZODB.DB(os.path.join(path, "data.fs"))
        # make sure database schema is up-to-date
        with db.transaction() as tx:
            root = tx.root()
            if not hasattr(root, "ctfs"):
                # {unsigned 64: Ctf}
                root.ctfs = BTrees.QOBTree.BTree()  # type: ignore
    return db
