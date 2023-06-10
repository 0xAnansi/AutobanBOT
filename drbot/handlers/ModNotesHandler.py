from __future__ import annotations

import json

import praw
import prawcore
from praw.models import ModAction
from datetime import datetime
from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.handlers import Handler
import re
from drbot.tools import ToolBoxUtils


class ModNotesHandler(Handler[ModAction]):
    """
    Handle note management based on modlog entries.
    Aims to create a modnote when a new entry is created via TB
    Aims to create a TB note when a new modnote is created via new
    """

    def _test(self):
        notelist = []
        cache = []
        h = 0

        #red = "fengapappit"
        c = 0
        params = {
            "filter": "NOTE"
        }
        #params["filter"] = "NOTE"
        comments = reddit().sub.comments(limit=1000)
        redditors = set([])
        for comment in comments: #comment.author.notes.subreddits("france", params=params):
            redditors.add(comment.author.name)
            if len(redditors) >= 10:
                redditors.add("FengaPappit")
                break
        for note in reddit().sub.mod.notes.redditors(redditors, all_notes=True, limit=None, params=params):
            # if note is not None and note.label is not None:
            #     notelist.append(note)
            notelist.append(note)
            c += 1
            # log.info(c)
        #cache.append(note.author.name)
        if c > h:
            h = c
        pass

    def setup(self, agent: Agent[ModAction]) -> None:
        super().setup(agent)
        #comments = reddit().sub.comments(limit=None)
        # todo delete after debugging
        #comments = reddit().sub.comments(limit=1000)
        #self._test()
        self.tb_manipulator = ToolBoxUtils.ToolBoxManipulator(reddit().sub, settings.username)
        self.cache = {}
        self.mod_notes = {}

    def start_run(self) -> None:
        log.debug("Invalidating cache.")
        self.cache = {}
        self.tb_manipulator.refresh_tb()

    @staticmethod
    def is_tb_note_action(item) -> bool:
        return item.details == "Page usernotes edited"

    @staticmethod
    def extract_username_from_tb_action(item) -> str:
        pattern = r"^\"create new note on new user (.+)\" via toolbox$"
        results = re.findall(pattern, item.description)
        if len(results) != 1:
            log.error(f"Matched more than once or not at all while extracting username from new TB note entry {item.description}")
            return ""
        return results[0]

    def handle(self, item: ModAction) -> None:
        # Assume that the bot handle note creation correctly and doesn't need to process its own entries
        if item.mod.name == settings.username:
            log.debug(f"Dropping ModNote management since I am the creator of the entry")
            return

        match item.action:
            # Process a new TB entry (old modnote)
            case "wikirevise":
                if self.is_tb_note_action(item):
                    username = self.extract_username_from_tb_action(item)
                    if len(username) <= 0:
                        log.error(f"Failed to retrieve username, dropping modnote processing")
                        return
                    # todo: extract usernotes from TB and push it into modnotes
                pass
            # Process a new modnote entry (new modnote)
            case "addnote":
                pass
