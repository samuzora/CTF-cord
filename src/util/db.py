import os
from typing import List
import discord
from sqlalchemy import Boolean, Column, Integer, Table, create_engine, select
from sqlalchemy import create_engine, ForeignKey, String
from sqlalchemy.orm import Mapped, Session, declarative_base, mapped_column, relationship

engine = None

Base = declarative_base()

chall_to_members = Table(
    "chall_to_members",
    Base.metadata,
    Column("Challenge", ForeignKey("challenges.id"), primary_key=True),
    Column("User", ForeignKey("users.id"), primary_key=True)
)

class Ctf(Base):
    __tablename__ = "ctfs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(Integer)
    join_message_id: Mapped[int] = mapped_column(Integer)
    challenges: Mapped[List["Challenge"]] = relationship("Challenge", back_populates="ctf")

class Challenge(Base):
    __tablename__ = "challenges"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    ctf_id: Mapped[int] = mapped_column(Integer, ForeignKey("ctfs.id"))
    ctf: Mapped["Ctf"] = relationship("Ctf", back_populates="challenges")
    members: Mapped[List["User"]]= relationship(secondary=chall_to_members, back_populates="challenges")
    solved: Mapped[bool] = mapped_column(Boolean, default=False)
    thread_id: Mapped[int] = mapped_column(Integer)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True) # discord user id
    challenges: Mapped[List["Challenge"]] = relationship(secondary=chall_to_members, back_populates="members")

def get_conn():
    global engine
    if not engine:
        path = "data"
        if not os.path.exists(path):
            os.mkdir(path)
        engine = create_engine(f"sqlite:///{os.path.join(path, 'data.db')}")
        Base.metadata.create_all(engine)
    return Session(engine)

def get_all_challs_from_ctx(ctx: discord.AutocompleteContext):
    with get_conn() as conn:
        challenges = conn.scalars(
            select(Challenge)
            .join(Ctf)
            .where(Ctf.channel_id == ctx.interaction.channel_id)
        )
        if not challenges:
            return []
        return [c.name for c in challenges]

def get_unsolved_challs_from_ctx(ctx: discord.AutocompleteContext):
    with get_conn() as conn:
        challenges = conn.scalars(
            select(Challenge)
            .join(Ctf)
            .where(Ctf.channel_id == ctx.interaction.channel_id)
            .where(Challenge.solved == False)
        )
        if not challenges:
            return []
        return [c.name for c in challenges]
