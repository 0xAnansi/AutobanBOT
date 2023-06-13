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


class AutobanHandler(Handler[Comment]):
    """
    Scan the comments of the sub and check if the author posted previously in monitored subs.
    Acts on the user if this is the case by either adding a modnote or banning, depending on the configuration for this specific sub.
    """

    def _refresh_processing_cache(self):
        if not self.processed_users_cache or len(self.processed_users_cache) > 4096 or len(self.processed_users_cache) <= 0:
            self.processed_users_cache = set([])
            # add the generic account used for communication
            gen_reddit_name = settings.subreddit + "-ModTeam"
            self.processed_users_cache.add(gen_reddit_name)
            self.processed_users_cache.add("Automoderator")
            for moderator in reddit().sub.moderator():
                self.processed_users_cache.add(moderator.name)
            for trusted_user in settings.trusted_users:
                self.processed_users_cache.add(trusted_user)

    def setup(self, agent: Agent[Comment]) -> None:
        # Ran once at handler registration in agent
        super().setup(agent)
        self.processed_users_cache = set([])
        self.monitored_subs_map = MonitoredSubsMap()
        self.user_utils = RedditUserUtils()
        self._refresh_processing_cache()
        self.banned_users_cache = set([])
        self.watched_users_cache = set([])
        self.ban_list_infos = []

    def start_run(self) -> None:
        # ran at the beginning of each batch
        log.debug("Invalidating cache if needed.")
        self._refresh_processing_cache()
        # Refreshed map values from config
        self.monitored_subs_map.refresh_values()
        self.banned_users_cache = set([])
        self.watched_users_cache = set([])
        self.ban_list_infos = []

    def end_run(self):
        # ran at the end of each batch
        if len(self.ban_list_infos) > 0:
            lines = []
            for ban in self.ban_list_infos:
                line = f"/u/{ban['username']} for [{ban['reason']}] based on trigger [{ban['trigger']}]({ban['trigger']})"
                lines.append(line)
            body = "\n\n".join(lines)
            reddit().send_modmail(subject=f"New Autoban actions",
                                  body=f"These users were automatically banned from your sub: \n\n{body}")

    def clear_modqueue_for_user(self, reddit_user):
        modqueue = reddit().sub.mod.modqueue(limit=None)
        for item in modqueue:
            if item.author == reddit_user:
                item.mod.lock()
                item.mod.remove(mod_note="AutobanBOT: removed banned user's entry from modqueue")
                pass
            pass

    def process_user_entries(self, reddit_user, trigger, rule):
        entries = []
        for comment in reddit().user(reddit_user).comments(limit=None):
            if comment.subreddit.display_name == settings.subreddit:
                entries.append(comment)
        for post in reddit().user(reddit_user).submissions(limit=None):
            if post.subreddit.display_name == settings.subreddit:
                entries.append(post)

        for item in entries:
            match self.monitored_subs_map.get_action(rule['sub_name']):
                case "report":
                    reason = self.monitored_subs_map.get_note(rule['sub_name'])
                    reason += " - trigger sub = /r/"
                    reason += rule['sub_name']
                    if not settings.dry_run:
                        item.report(reason=reason)
                    else:
                        log.info(f"DRY RUN: Would have reported comment of user {reddit_user.name} with reason [{reason}]")
                case "remove":
                    if not settings.dry_run:
                        item.mod.lock()
                        item.mod.remove(mod_note="AutobanBOT: removed user's entry")
                    else:
                        log.info(f"DRY RUN: Would have removed entry of user {reddit_user.name}")

    def act_on(self, reddit_user, trigger, rule):
        if not self.user_utils.get_user_status(reddit_user) == UserStatus.ACTIVE:
            log.warning(f"Tried to act on user that is not active {reddit_user.name}")
            return
        #sub_name = rule['sub_name']
        match self.monitored_subs_map.get_action(rule['sub_name']):
            case "ban":
                if not settings.dry_run:
                    try:
                        log.warning(f"Banning user [{reddit_user.name}] for posting in [{rule['sub_name']}]")
                        reddit().sub.banned.add(reddit_user.name, ban_reason=self.monitored_subs_map.get_note(rule['sub_name']),
                                                ban_message="You have been automatically and permanently banned from the sub, if you think this is an error, write us a modmail!")
                        reddit().sub.mod.notes.create(redditor=reddit_user.name,
                                                      label=self.monitored_subs_map.get_label(rule['sub_name']),
                                                      note=self.monitored_subs_map.get_note(rule['sub_name']))
                        self.clear_modqueue_for_user(reddit_user.name)
                        self.banned_users_cache.add(reddit_user.name)
                        self.ban_list_infos.append({
                            "username": reddit_user.name,
                            "reason": self.monitored_subs_map.get_note(rule['sub_name']),
                            "trigger": trigger.permalink
                        })
                    except Exception as e:
                        log.error(f"Failed to ban user [{reddit_user.name}]: {e.message}")
                else:
                    log.info(f"DRY RUN : [NOT] banning user [{reddit_user.name}] for posting in [{rule['sub_name']}]")
            case "watch":
                if reddit_user.name in self.watched_users_cache:
                    log.info(f"User {reddit_user.name} in watched list already, not further action needed")
                    return False
                target_label = self.monitored_subs_map.get_label(rule['sub_name'])
                target_note = self.monitored_subs_map.get_note(rule['sub_name'])
                manual_retry = 1
                while manual_retry >= 1:
                    try:
                        user_notes = reddit().sub.mod.notes.redditors(reddit_user, all_notes=True)
                        manual_retry = 0
                    except TooManyRequests as e:
                        log.warning("Hitting rate limiting during note creation, sleeping")
                        time.sleep(manual_retry * 10)
                        manual_retry += 1
                for modnote in user_notes:
                    if modnote is None:
                        # can return None even in iterator
                        continue
                    if modnote.label == target_label and modnote.note == target_note:
                        # note already exists, do nothing
                        log.info(f"[{reddit_user.name}] already has a note for posting in [{rule['sub_name']}]")
                        self.watched_users_cache.add(reddit_user.name)
                        return
                if not settings.dry_run:
                    log.warning(f"Watching user [{reddit_user.name}] for posting in [{rule['sub_name']}], creating note")
                    manual_retry = 1
                    while manual_retry >= 1:
                        try:
                            reddit().sub.mod.notes.create(redditor=reddit_user.name, label=target_label,
                                                  note=target_note)
                            manual_retry = 0
                        except TooManyRequests as e:
                            log.warning("Hitting rate limiting during note creation, sleeping")
                            time.sleep(manual_retry * 10)
                            manual_retry += 1
                    self.watched_users_cache.add(reddit_user.name)
                else:
                    log.info(f"DRY RUN : watching user [{reddit_user.name}] for posting in [{rule['sub_name']}]")
            case "report":
                self.process_user_entries(reddit_user, trigger, rule)
            case "modalert":
                body = f"This modalert was triggered by the user /u/{reddit_user.name} posting in the sub /r/{rule['sub_name']}\n\n"
                body += f"The comment triggering this alert is the following: [{trigger.permalink}]({trigger.permalink})"
                reddit().send_modmail(subject=f"New modalert targeting user /u/{reddit_user.name} from /r/{rule['sub_name']}",
                                      body=body)
            case _:
                log.error(f"Processing unmanaged action {self.monitored_subs_map.get_action(rule['sub_name'])}")




    def process_user_history(self, comment_author):
        # Check if the user posts in monitored subs
        sub_cache = set([])
        # Avoid checking for our subreddit
        sub_cache.add(settings.subreddit)
        # Check for submissions in shitty subs (faster than comments in case of positive)
        for submission in comment_author.submissions.new(limit=250):
            check = submission.subreddit.display_name
            # We already checked and processed the sub for this user
            if check in sub_cache:
                #log.debug(f"Skipping sub {check} since already processed")
                continue
            if submission.subreddit.display_name in self.monitored_subs_map.subs_map:
                # action = self.monitored_subs_map[comment.subreddit]["action"]
                log.info(f"Found matching rule for sub {check} and user {comment_author.name}")
                self.act_on(comment_author, submission,
                            self.monitored_subs_map.subs_map[submission.subreddit.display_name])
                break
            else:
                sub_cache.add(check)
        # If no submission, check comments
        for comment in comment_author.comments.new(limit=250):
            check = comment.subreddit.display_name
            # We already checked and processed the sub for this user
            if check in sub_cache:
                #log.debug(f"Skipping sub {check} since already processed")
                continue
            if comment.subreddit.display_name in self.monitored_subs_map.subs_map:
                # action = self.monitored_subs_map[comment.subreddit]["action"]
                log.info(f"Found matching rule for sub {check} and user {comment_author.name}")
                self.act_on(comment_author, comment,
                            self.monitored_subs_map.subs_map[comment.subreddit.display_name])
                break
            else:
                sub_cache.add(check)

    def handle(self, item: Comment) -> None:
        # Comment was removed, we cannot get the author
        if item.body == "[removed]":  # or item.body == "[ Removed by Reddit ]":
            return
        comment_author = item.author

        # We already processed this user, do nothing
        if comment_author.name in self.processed_users_cache:
            return
        log.debug(f"Checking history for: {comment_author.name}")
        user_status = self.user_utils.get_user_status(comment_author)
        if comment_author.name in self.banned_users_cache:
            log.info(f"u/{comment_author.name} is already in banned cache")
            user_status = UserStatus.BANNED
        log.debug(f"User {comment_author.name} is {user_status.name}")
        if user_status is not UserStatus.ACTIVE:
            match user_status:
                case UserStatus.SHADOWBANNED:
                    self.clear_modqueue_for_user(comment_author)
                case UserStatus.BANNED:
                    self.banned_users_cache.add(comment_author.name)
                    self.clear_modqueue_for_user(comment_author.name)
            self.processed_users_cache.add(comment_author.name)
            return

        # Check if the user posts in monitored subs
        self.process_user_history(comment_author)
        # user was processed, add to cache to avoid spamming the API
        self.processed_users_cache.add(comment_author.name)
