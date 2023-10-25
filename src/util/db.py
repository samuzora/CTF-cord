import os

import ZODB  # type: ignore

from persistent import Persistent  # type: ignore
import BTrees.OOBTree  # type: ignore

db = None


class Ctf(Persistent):
    def __init__(self, channel_id: int, join_message_id: int):
        self.channel_id: int = channel_id
        self.join_message_id: int = join_message_id
        self.challenges: list[Challenge] = []


class Challenge(Persistent):
    def __init__(self, name: str, solved: bool):
        self.name: str = name
        self.solved: bool = solved
        self.solved_by: int = 0


def get_conn():
    global db
    if not db:
        path = os.path.expanduser("~/.local/share/ctf-cord/data.fs")
        if not os.path.exists(path):
            os.mkdir(path)
        db = ZODB.DB(os.path.join(path, "data.fs"))
        # make sure database schema is up-to-date
        with db.transaction() as tx:
            root = tx.root()
            if "ctfs" not in root:
                # {unsigned 64: Ctf}
                root.ctfs = BTrees.QOBTree.BTree()
    return db
