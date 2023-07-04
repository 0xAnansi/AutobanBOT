from __future__ import annotations

import time

import prawcore
from praw.models import Comment
from prawcore import TooManyRequests

from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.const.BotConstants import UserStatus
from drbot.handlers import Handler
from drbot.stores import MonitoredSubsMap
from enum import Enum, auto

from drbot.tools.RedditUserUtils import RedditUserUtils


class SpecialUserStatusHandler(Handler[Comment]):
    """
    Scan the comments of the sub and check if the author posted previously in monitored subs.
    Acts on the user if this is the case by either adding a modnote or banning, depending on the configuration for this specific sub.
    """

    def setup(self, agent: Agent[Comment]) -> None:
        # Ran once at handler registration in agent
        super().setup(agent)
        self.user_utils = RedditUserUtils()
        self.user_cache = {}
        self.user_cache["AutoModerator"] = UserStatus.ACTIVE

    def start_run(self) -> None:
        log.info("Starting to check for special user status")
        self.user_cache["AutoModerator"] = UserStatus.ACTIVE

    def end_run(self):
        # ran at the end of each batch
        log.info("Stopping to check for special user status")


    def handle(self, item: Comment) -> None:
        # Comment was removed, we cannot get the author
        if item.body == "[removed]":  # or item.body == "[ Removed by Reddit ]":
            return
        comment_author = item.author
        if comment_author is None:
            log.info(f"Item {item.permalink} has no author, dropping")
            return
        # We already processed this user, do nothing
        if comment_author.name not in self.user_cache:
            log.debug(f"Checking status for: {comment_author.name}")
            user_status = self.user_utils.get_user_status(comment_author)
            self.user_cache[comment_author.name] = user_status

        match self.user_cache[comment_author.name]:
            case UserStatus.SHADOWBANNED:
                reason = f"User {comment_author.name} has posted while being shadowbanned"
                if not settings.dry_run:
                    log.info(f"Sending report for user {comment_author.name} on comment {item.permalink}")
                    item.report(reason=reason)
                else:
                    log.info(f"DRY RUN: Would have reported comment of user {comment_author.name} with reason [{reason}]")

