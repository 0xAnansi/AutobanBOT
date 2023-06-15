from __future__ import annotations

import prawcore
from praw.models import Comment, Redditor

from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.const.BotConstants import UserStatus
from drbot.handlers import Handler
from drbot.stores import MonitoredSubsMap
from enum import Enum, auto


class RedditUserUtils:
    def get_user_status(self, redditor_in: str | Redditor):
        if redditor_in is None:
            return UserStatus.UNEXPECTED
        reddit_user = redditor_in
        if isinstance(redditor_in, str):
            try:
                reddit_user = Redditor(reddit(), redditor_in)
            except Exception as e:
                log.error(f"Error initializing user {redditor_in}: {e.message}")
                return UserStatus.UNEXPECTED
        try:
            if hasattr(reddit_user, 'is_suspended') and reddit_user.is_suspended:
                log.info(f"User is suspended: {reddit_user.name}")
                return UserStatus.SUSPENDED
        except prawcore.exceptions.NotFound as e:
            log.warning(f"User {reddit_user.name} seems to be shadowbanned")
            return UserStatus.SHADOWBANNED
        except Exception as e:
            log.error(f"Error processing user {reddit_user.name}: {e.message}")
            # default to active
            return UserStatus.UNEXPECTED
        # any(reddit.subreddit('SUBREDDIT').banned(redditor='USERNAME'))
        if any(reddit().sub.banned(reddit_user.name)):
            log.info(f"u/{reddit_user.name} is banned from sub")
            return UserStatus.BANNED

        log.debug(f"u/{reddit_user.name} is active")
        return UserStatus.ACTIVE
