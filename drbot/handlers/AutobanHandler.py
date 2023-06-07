from __future__ import annotations
import praw
from praw.models import ModAction, Comment
from datetime import datetime
from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.handlers import Handler
from drbot.stores import MonitoredSubsMap


class AutobanHandler(Handler[Comment]):
    """Scans the modlog for instances of moderators moderating their own comments,
    comments on their posts, or comments in the reply tree below their own comments."""

    # def __init__(self):
    #     self.monitored_subs_map = []
    #     self.cache = []
    #     self.banned_users = []
    #     self.watched_users = []

    def setup(self, agent: Agent[Comment]) -> None:
        super().setup(agent)
        self.monitored_subs_map = MonitoredSubsMap()
        self.cache = []
        self.banned_users = []
        self.watched_users = []

    def start_run(self) -> None:
        log.debug("Invalidating cache if needed.")
        if len(self.cache) > 4096:
            self.cache = []
        # Refreshed map values from config
        self.monitored_subs_map.refresh_values()
        self.banned_users = []
        self.watched_users = []

    def end_run(self):
        if len(self.banned_users) > 0 or len(self.watched_users) > 0:
            reddit().sub.message(subject=f"New Autoban actions",
                                  body=f"These users were automatically banned from your sub: {self.banned_users}\nThese users were put on watch on your sub: {self.watched_users}")


    def clear_modqueue_for_user(self, reddit_user):
        modqueue = reddit().sub.mod.modqueue(limit=None)
        for item in modqueue:
            if item.author == reddit_user:
                item.mod.lock()
                item.mod.remove(mod_note="AutobanBOT: removed banned user's entry from modqueue")
                pass
            pass


    def act_on(self, reddit_user, sub_name, sub_entry):
        if reddit_user.name in self.banned_users:
            log.debug(f"User {reddit_user.name} in banned list already, not further action needed")
            return False

        if next(reddit().sub.banned(reddit_user.name), None) is not None:
            log.info(f"u/{reddit_user.name} is already banned from sub; skipping action.")
            self.banned_users.append(reddit_user.name)
            return False

        match sub_entry["action"]:
            case "ban":
                if not settings.dry_run:
                    try:
                        log.debug(f"Banning user [{reddit_user.name}] for posting in [{sub_name}]")
                        reddit().sub.banned.add(reddit_user.name, ban_reason=self.monitored_subs_map.get_note(sub_name), ban_message="You have been permanently banned from the sub, if you think this is an error, write us a modmail!")
                        reddit().sub.mod.notes.create(redditor=reddit_user.name, label=self.monitored_subs_map.get_label(sub_name), note=self.monitored_subs_map.get_note(sub_name))
                        self.banned_users.append(reddit_user.name)
                    except Exception as e:
                        log.error(f"Failed to ban user [{reddit_user.name}]: {e.message}")
                else:
                    log.info(f"DRY RUN : [NOT] banning user [{reddit_user.name}] for posting in [{sub_name}]")
            case "watch":
                if reddit_user.name in self.watched_users:
                    log.debug(f"User {reddit_user.name} in watched list already, not further action needed")
                    return False
                target_label = self.monitored_subs_map.get_label(sub_name)
                target_note = self.monitored_subs_map.get_note(sub_name)
                #user_notes = reddit().notes(redditors=[reddit_user], subreddits=[reddit().sub], all_notes=True)
                user_notes = reddit().sub.mod.notes.redditors(reddit_user, all_notes=True)
                for modnote in user_notes:
                    if modnote is None:
                        # can return None even in iterator
                        continue
                    if modnote.label == target_label and modnote.note == target_note:
                        # note already exists, do nothing
                        log.debug(f"[{reddit_user.name}] already has a note for posting in [{sub_name}]")
                        break
                if not settings.dry_run:
                    log.debug(f"Watching user [{reddit_user.name}] for posting in [{sub_name}], creating note")
                    reddit().sub.mod.notes.create(redditor=reddit_user.name, label=target_label,
                                            note=target_note)
                    self.watched_users.append(reddit_user.name)
                else:
                    log.info(f"DRY RUN : watching user [{reddit_user.name}] for posting in [{sub_name}]")
            case _:
                log.warning(f"Processing unmanaged action {sub_entry['action']}")


    def handle(self, item: Comment) -> None:
        # Comment was removed, we cannot get the author
        if item.body == "[removed]":  # or item.body == "[ Removed by Reddit ]":
            return
        comment_author = item.author

        # Breakpoint for debugging special cases
        #if comment_author.name in ["Spiritual_Collar881"]:
         #   log.info("Debugging special case")
        # We already processed this user, do nothing
        if comment_author.name in self.cache:
            return
        log.info(f"Checking history for: {comment_author.name}")
        # This user was suspended by reddit, do nothing
        if hasattr(comment_author, 'is_suspended') and comment_author.is_suspended:
            log.info(f"User is suspended: {comment_author.name}")
            self.cache.append(comment_author.name)
            return

        # User is already banned from the sub, do nothing
        if next(reddit().sub.banned(comment_author.name), None) is not None:
            log.info(f"u/{comment_author.name} is already banned from sub; skipping action.")
            self.banned_users.append(comment_author.name)
            return

        # Check if the user posts in monitored subs
        sub_cache = []
        # Avoid checking for our subreddit
        sub_cache.append(settings.subreddit)
        # Check for submissions in shitty subs (faster than comments in case of positive)
        for submission in comment_author.submissions.new(limit=None):
            check = submission.subreddit.display_name
            # We already checked and processed the sub for this user
            if check in sub_cache:
                continue
            if submission.subreddit.display_name in self.monitored_subs_map.subs_map:
                #action = self.monitored_subs_map[comment.subreddit]["action"]
                self.act_on(comment_author, submission.subreddit.display_name, self.monitored_subs_map.subs_map[submission.subreddit.display_name])
                break
            else:
                sub_cache.append(check)
        # If no submission, check comments
        for comment in comment_author.comments.new(limit=None):
            check = comment.subreddit.display_name
            # We already checked and processed the sub for this user
            if check in sub_cache:
                continue
            if comment.subreddit.display_name in self.monitored_subs_map.subs_map:
                #action = self.monitored_subs_map[comment.subreddit]["action"]
                self.act_on(comment_author, comment.subreddit.display_name, self.monitored_subs_map.subs_map[comment.subreddit.display_name])
                break
            else:
                sub_cache.append(check)
        # user was processed, add to cache to avoid spamming the API
        self.cache.append(comment_author.name)
