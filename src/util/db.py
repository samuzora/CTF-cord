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
    def __init__(self, name: str, solved_by: int):
        self.name: str = name
        self.solved_by: int = solved_by


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
                root.ctfs = BTrees.QOBTree.BTree() # type: ignore
    return db
