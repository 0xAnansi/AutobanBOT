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

    def setup(self, agent: Agent[ModAction]) -> None:
        super().setup(agent)
        #comments = reddit().sub.comments(limit=None)
        notelist = []
        # todo delete after debugging
        # for comments in reddit().sub.comments(limit=None):
        #     for note in reddit().notes.things(comments):
        #         if note is not None:
        #             notelist.append(note)
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
