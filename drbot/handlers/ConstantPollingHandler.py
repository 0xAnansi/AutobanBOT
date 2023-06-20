from __future__ import annotations

from datetime import datetime, timedelta
import time
from typing import Tuple

import prawcore
from dateutil.utils import today
from praw.models import Comment, Submission
from prawcore import TooManyRequests

from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.const.BotConstants import UserStatus
from drbot.handlers import Handler
from drbot.stores import MonitoredSubsMap
from enum import Enum, auto

from drbot.stores.PollsMap import PollsMap
from drbot.tools.RedditUserUtils import RedditUserUtils


class ConstantPollingHandler(Handler[Comment]):
    """
    Scan the comments of the sub and check if the author posted previously in monitored subs.
    Acts on the user if this is the case by either adding a modnote or banning, depending on the configuration for this specific sub.
    """

    def _refresh_processing_cache(self):
        self.processed_users_cache = set([])
        self.users_whitelist = set([])
        # add the generic account used for communication
        gen_reddit_name = settings.subreddit + "-ModTeam"
        self.users_whitelist.add(gen_reddit_name)
        # Add automod to avoid checking auto messages
        self.users_whitelist.add("AutoModerator")
        # Add ourselves to avoid checking our own messages
        self.users_whitelist.add(settings.username)

    def setup(self, agent: Agent[Comment]) -> None:
        # Ran once at handler registration in agent
        super().setup(agent)
        self.polls_map = PollsMap()
        self.users_whitelist = set([])
        self.processed_users_cache = set([])
        self.user_utils = RedditUserUtils()
        self._refresh_processing_cache()

    def start_run(self) -> None:
        # ran at the beginning of each batch
        log.debug("Invalidating cache if needed.")
        self._refresh_processing_cache()
        # Refreshed map values from config
        self.polls_map.refresh_values()

    def end_run(self):
        pass


    def is_valid_entry(self, item: Comment, poll: dict) -> Tuple[bool, str]:
        if not item.parent_id.startswith("t3_"):
            log.debug(f"Not a first level comment, dropping")
            return False, "Not a first level comment"
        # Comment was removed, we cannot get the author
        if item.body == "[removed]":  # or item.body == "[ Removed by Reddit ]":
            return False, "Removed comment"

        comment_author = item.author

        # We already processed this user, do nothing
        if comment_author.name in self.processed_users_cache:
            return False, "Vous avez déjà voté. Si vous changez d'avis, il suffit d'éditer votre message initial avec le choix souhaité"
        # Todo : check for account age
        return True, ""

    def get_tally_comment(self, thread: Submission):
        comments = thread.comments
        for comment in comments:
            if comment.stickied and comment.author.name == settings.username:
                return comment
        return thread.reply("placeholder")

    def post_results(self, poll:dict, thread: Submission, choices: dict):
        com = self.get_tally_comment(thread)
        poll_name = self.polls_map.get_poll_name(poll)
        date = datetime.now().strftime("%d/%m/%y %H:%M:%S")
        body = f"""
# {poll_name}
        
Updated: {date}

## Results
  
Entry | Count
---|---
"""
        sorted_res = dict(sorted(choices.items(), key=lambda item: item[1], reverse=True))
        # last = len(sorted_res)
        # i = 1
        for entry in sorted_res:
            body += f"{entry} | {sorted_res[entry]}\n"
            # if i < last:
            #     body += "---|---"
            # i += 1
        body += """

## Disclaimer
        
This is a beta feature, you can blame the mods if it does strange things.

"""
        com.edit(body)
        com.mod.distinguish(how="yes", sticky=True)


    def get_vote(self, comment: Comment, choices: dict) -> str:
        for option in choices:
            if option.lower() in comment.body.lower():
                return option
        return "none"

    def remove_valid_comment(self, comment: Comment, message: str):
        if comment.author.name not in self.users_whitelist and not comment.locked:
            comment.mod.lock()
            comment.mod.remove()
            comment.reply(f"Ce message a été automatiquement supprimé: {message}")

    def tally_poll(self, poll: dict):
        thread_id = poll["thread_id"]
        poll_sub = Submission(reddit=reddit(), id=thread_id)

        sub_creation = datetime.fromtimestamp(poll_sub.created_utc)
        poll_end = sub_creation + timedelta(hours=self.polls_map.get_poll_duration(poll))
        if today() > poll_end:
            if poll_sub.locked:
                # Poll has ended and was tallied already, do nothing
                return

        choices = {}
        for option in poll["options"]:
            choices[option] = 0
        for comment in poll_sub.comments:
            if comment.body == "[removed]" or comment.locked:
                continue
            user_status = self.user_utils.get_user_status(comment.author)
            if user_status != UserStatus.ACTIVE:
                self.remove_valid_comment(comment, "User status not eligible for this poll")
                continue
            if comment.author.name == settings.username:
                continue
            valid, reason = self.is_valid_entry(comment, poll)

            if not valid:
                self.remove_valid_comment(comment, reason)
                continue
            if not comment.locked:
                vote = self.get_vote(comment, choices)
                if vote != "none":
                    choices[vote] += 1
                    self.processed_users_cache.add(comment.author.name)
                else:
                    self.remove_valid_comment(comment, f"Ce vote n'est pas valide, les valeurs possibles attendues sont: {poll['options']}")
        self.post_results(poll, poll_sub, choices)
        log.info("Updating poll results")
        if today() > poll_end:
            self.post_results(poll, poll_sub, choices)
            log.info("Updating final poll results and locking poll")
            poll_sub.mod.lock()



    def run_tally(self):
        for poll in self.polls_map.polls:
            self.start_run()
            self.tally_poll(self.polls_map[poll])


    def handle(self, item: Comment) -> None:
        # No synchroneous management for polls atm
        return
