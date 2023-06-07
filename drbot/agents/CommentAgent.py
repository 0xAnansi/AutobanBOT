from __future__ import annotations
from datetime import datetime
from praw.models import Comment
from drbot import reddit
from drbot.agents import HandlerAgent


class CommentAgent(HandlerAgent[Comment]):
    """Scans incoming posts and runs sub-tools on them."""

    def get_items(self) -> list[Comment]:
        items = []
        for item in reddit().sub.comments(limit=None):
            if self.id(item) <= self.data_store["_meta"]["last_processed"]:
                break

            items.append(item)
        return list(reversed(items))  # Process from earliest to latest

    def id(self, item: Comment) -> str:
        return datetime.fromtimestamp(item.created_utc)

    def get_latest_item(self) -> list[Comment]:
        return next(reddit().sub.comments(limit=1))
