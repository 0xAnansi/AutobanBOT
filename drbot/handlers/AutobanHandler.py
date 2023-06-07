from __future__ import annotations

import prawcore
from praw.models import Comment

from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.handlers import Handler
from drbot.stores import MonitoredSubsMap


class AutobanHandler(Handler[Comment]):
    """
    Scan the comments of the sub and check if the author posted previously in monitored subs.
    Acts on the user if this is the case by either adding a modnote or banning, depending on the configuration for this specific sub.
    """

    def _refresh_cache(self):
        if not self.cache or len(self.cache) > 4096 or len(self.cache) <= 0:
            self.cache = []
            # add the generic account used for communication
            gen_reddit_name = settings.subreddit + "-ModTeam"
            self.cache.append(gen_reddit_name)
            for moderator in reddit().sub.moderator():
                self.cache.append(moderator.name)

    def setup(self, agent: Agent[Comment]) -> None:
        # Ran once at handler registration in agent
        super().setup(agent)
        self.cache = []
        self.monitored_subs_map = MonitoredSubsMap()
        self._refresh_cache()
        self.banned_users = []
        self.watched_users = []

    def start_run(self) -> None:
        # ran at the beginning of each batch
        log.debug("Invalidating cache if needed.")
        self._refresh_cache()
        # Refreshed map values from config
        self.monitored_subs_map.refresh_values()
        self.banned_users = []
        self.watched_users = []

    def end_run(self):
        # ran at the end of each batch
        if len(self.banned_users) > 0:
            banned = "\n\n".join(self.banned_users)
            reddit().send_modmail(subject=f"New Autoban actions",
                                  body=f"These users were automatically banned from your sub: {banned}")

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
                        log.warning(f"Banning user [{reddit_user.name}] for posting in [{sub_name}]")
                        reddit().sub.banned.add(reddit_user.name, ban_reason=self.monitored_subs_map.get_note(sub_name),
                                                ban_message="You have been permanently banned from the sub, if you think this is an error, write us a modmail!")
                        reddit().sub.mod.notes.create(redditor=reddit_user.name,
                                                      label=self.monitored_subs_map.get_label(sub_name),
                                                      note=self.monitored_subs_map.get_note(sub_name))
                        self.clear_modqueue_for_user(reddit_user.name)
                        self.banned_users.append(reddit_user.name)
                    except Exception as e:
                        log.error(f"Failed to ban user [{reddit_user.name}]: {e.message}")
                else:
                    log.info(f"DRY RUN : [NOT] banning user [{reddit_user.name}] for posting in [{sub_name}]")
            case "watch":
                if reddit_user.name in self.watched_users:
                    log.info(f"User {reddit_user.name} in watched list already, not further action needed")
                    return False
                target_label = self.monitored_subs_map.get_label(sub_name)
                target_note = self.monitored_subs_map.get_note(sub_name)
                # user_notes = reddit().notes(redditors=[reddit_user], subreddits=[reddit().sub], all_notes=True)
                user_notes = reddit().sub.mod.notes.redditors(reddit_user, all_notes=True)
                for modnote in user_notes:
                    if modnote is None:
                        # can return None even in iterator
                        continue
                    if modnote.label == target_label and modnote.note == target_note:
                        # note already exists, do nothing
                        log.info(f"[{reddit_user.name}] already has a note for posting in [{sub_name}]")
                        self.watched_users.append(reddit_user.name)
                        return
                if not settings.dry_run:
                    log.warning(f"Watching user [{reddit_user.name}] for posting in [{sub_name}], creating note")
                    reddit().sub.mod.notes.create(redditor=reddit_user.name, label=target_label,
                                                  note=target_note)
                    self.watched_users.append(reddit_user.name)
                else:
                    log.info(f"DRY RUN : watching user [{reddit_user.name}] for posting in [{sub_name}]")
            case _:
                log.error(f"Processing unmanaged action {sub_entry['action']}")

    def handle(self, item: Comment) -> None:
        # Comment was removed, we cannot get the author
        if item.body == "[removed]":  # or item.body == "[ Removed by Reddit ]":
            return
        comment_author = item.author

        # Breakpoint for debugging special cases
        # if comment_author.name in ["Spiritual_Collar881"]:
        #   log.info("Debugging special case")
        # We already processed this user, do nothing
        if comment_author.name in self.cache:
            return
        log.info(f"Checking history for: {comment_author.name}")
        # This user was suspended by reddit, do nothing
        try:
            if hasattr(comment_author, 'is_suspended') and comment_author.is_suspended:
                log.info(f"User is suspended: {comment_author.name}")
                self.cache.append(comment_author.name)
                return
        except prawcore.exceptions.NotFound as e:
            log.warning(f"User {comment_author.name} seems to be shadowbanned")
            self.clear_modqueue_for_user(comment_author)
            self.cache.append(comment_author.name)
            return
        except Exception as e:
            log.error(f"Error processing user {comment_author.name}: {e.message}")
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
        for submission in comment_author.submissions.new(limit=250):
            check = submission.subreddit.display_name
            # We already checked and processed the sub for this user
            if check in sub_cache:
                continue
            if submission.subreddit.display_name in self.monitored_subs_map.subs_map:
                # action = self.monitored_subs_map[comment.subreddit]["action"]
                self.act_on(comment_author, submission.subreddit.display_name,
                            self.monitored_subs_map.subs_map[submission.subreddit.display_name])
                break
            else:
                sub_cache.append(check)
        # If no submission, check comments
        for comment in comment_author.comments.new(limit=250):
            check = comment.subreddit.display_name
            # We already checked and processed the sub for this user
            if check in sub_cache:
                continue
            if comment.subreddit.display_name in self.monitored_subs_map.subs_map:
                # action = self.monitored_subs_map[comment.subreddit]["action"]
                self.act_on(comment_author, comment.subreddit.display_name,
                            self.monitored_subs_map.subs_map[comment.subreddit.display_name])
                break
            else:
                sub_cache.append(check)
        # user was processed, add to cache to avoid spamming the API
        self.cache.append(comment_author.name)
