from __future__ import annotations

from praw.models import ModAction, Redditor

from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.const.BotConstants import UserStatus
from drbot.handlers import Handler
from drbot.tools.RedditUserUtils import RedditUserUtils


class ModQueueCleanerHandler(Handler[ModAction]):
    def setup(self, agent: Agent[ModAction]) -> None:
        # Ran once at handler registration in agent
        self.user_utils = RedditUserUtils()
        self.cache = set([])
        super().setup(agent)
        log.info(f"Setting up ModQueueCleaner with autoremoval of contribs set to {settings.wipe_contrib_on_permaban}")

    def wipe_user_entries(self, reddit_user: Redditor):
        entries = []
        if reddit_user.name == "[deleted]":
            log.warn("Should have removed user contrib but user has deleted its account")
            return
        user_status = self.user_utils.get_user_status(reddit_user)
        if user_status is UserStatus.SUSPENDED or user_status is UserStatus.UNEXPECTED or user_status is UserStatus.SHADOWBANNED:
            log.warn("Should have removed user contrib but user has wrong status")
            return
        for comment in reddit_user.comments.new(limit=None):
            if comment.subreddit.display_name == settings.subreddit:
                entries.append(comment)
        for post in reddit_user.submissions.new(limit=None):
            if post.subreddit.display_name == settings.subreddit:
                entries.append(post)

        for item in entries:
            if not settings.dry_run:
                if not item.locked and item.archived is False:
                    item.mod.lock()
                item.mod.remove(mod_note="AutobanBOT: removed user's entry after permaban")
            else:
                log.info(f"DRY RUN: Would have removed entry of user {reddit_user.name}")

    def clear_modqueue_for_user(self, reddit_user):
        modqueue = reddit().sub.mod.modqueue(limit=None)
        for item in modqueue:
            if item.author == reddit_user:
                if not item.locked and item.archived is False:
                    item.mod.lock()
                item.mod.remove(mod_note="AutobanBOT: removed banned user's entry from modqueue")
                pass
            pass
    def handle(self, item: ModAction) -> None:
        if item.mod.name == settings.username:
            log.debug(f"Dropping ModNote management since I am the creator of the entry")
            return
        match item.action:
            case "banuser":
                if item.target_author in self.cache:
                    log.debug("User already processed")
                    return
                if "permanent" in item.details:
                    log.info(f"Handling modqueue and comment removal from permabanned user {item.target_author}")
                    red = reddit().redditor(item.target_author)
                    user_status = self.user_utils.get_user_status(red)
                    # double check that user is still banned in case it was a mistake
                    if user_status is UserStatus.BANNED:
                        self.clear_modqueue_for_user(red)
                        wipe_on_perma = settings.wipe_contrib_on_permaban
                        if wipe_on_perma or "botwipe" in item.description:
                            self.wipe_user_entries(red)
                    self.cache.add(item.target_author)

