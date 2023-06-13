from __future__ import annotations

import json
import time
from typing import Tuple

import praw
import prawcore
from praw.models import ModAction, ModNote
from datetime import datetime

from prawcore import TooManyRequests

from drbot import settings, log, reddit
from drbot.agents import Agent
from drbot.const.BotConstants import UserStatus
from drbot.handlers import Handler
import re
from drbot.tools import ToolBoxUtils
from drbot.tools.RedditUserUtils import RedditUserUtils


class ModNotesHandler(Handler[ModAction]):
    """
    Handle note management based on modlog entries.
    Aims to create a modnote when a new entry is created via TB
    Aims to create a TB note when a new modnote is created via new
    """

    def setup(self, agent: Agent[ModAction]) -> None:
        super().setup(agent)
        self.tb_manipulator = ToolBoxUtils.ToolBoxManipulator(reddit(), settings.username)
        self.user_utils = RedditUserUtils()
        self.cache = set([])
        self.mod_notes = {}

    def start_run(self) -> None:
        log.debug("Invalidating cache")
        #self.cache = {}
        self.tb_manipulator.refresh_tb()

    @staticmethod
    def is_tb_note_action(item) -> bool:
        return item.details == "Page usernotes edited"

    @staticmethod
    def extract_type_and_username_from_tb_action(item) -> Tuple[str, str]:
        (firstWord, rest) = item.description.split(maxsplit=1)
        if not firstWord or len(firstWord) <= 6:
            log.warning(f"Action not recognized on TB note action firstword [{firstWord}]")
            return "", ""
        firstWord = firstWord[1:]
        match firstWord:
            case "create":
                pattern = r"^\"create new note on.+user (.+)\" via toolbox$"
                results = re.findall(pattern, item.description)
                if len(results) != 1:
                    log.error(f"Matched more than once or not at all while extracting username from new TB note entry {item.description}")
                    return "", ""
                return firstWord, results[0]
            case "delete":
                pattern = r"^\"delete note.*on.*user (.+)\" via toolbox$"
                results = re.findall(pattern, item.description)
                if len(results) != 1:
                    log.error(
                        f"Matched more than once or not at all while extracting username from removed TB note entry {item.description}")
                    return ""
                return firstWord, results[0]
            case _:
                log.warning(f"Action not recognized on TB note action [{item.description}]")
                return "", ""

    def is_tb_in_modnote(self, tb_note: dict, modnotes) -> bool:
        target_owner = self.tb_manipulator.get_note_owner(tb_note)
        target_label = self.tb_manipulator.get_note_modnote_label(tb_note)
        target_note = self.tb_manipulator.get_note_content(tb_note)
        target_datetime = self.tb_manipulator.get_note_date(tb_note)
        target_date = f"{target_datetime}"
        for modnote in modnotes:
            if modnote is None:
                # can return None even in iterator
                return False
            if modnote.label == target_label:
                # Either the note was manually created by user (rare) or was transferred by bot
                if modnote.moderator.name == target_owner:
                    if target_note == modnote.note:
                        # Matching note found, skip this tb_note
                        return True
                else:
                    # Note was created by bot, check if the note content mentions the text and mod name
                    if target_note in modnote.note and target_owner in modnote.note and target_date in modnote.note:
                        # Matching note found, skip this tb_note
                        return True
                    # Old format was not starting with date but with owner
                    if target_note in modnote.note and modnote.note.startswith(target_owner):
                        return True
        return False

    def get_user_modnotes(self, username):
        notes = []
        for note in reddit().sub.mod.notes.redditors(username, all_notes=True, params={"filter": "NOTE"}):
            notes.append(note)
        return notes

    def handle(self, item: ModAction) -> None:
        # Assume that the bot handle note creation correctly and doesn't need to process its own entries
        if item.mod.name == settings.username:
            log.debug(f"Dropping ModNote management since I am the creator of the entry")
            return
        match item.action:
            # Process a new TB entry (old modnote)
            case "wikirevise":
                if self.is_tb_note_action(item):
                    type, username = self.extract_type_and_username_from_tb_action(item)
                    if len(username) <= 0:
                        log.error(f"Failed to retrieve username, dropping modnote processing")
                        return
                    if username in self.cache:
                        log.debug(f"User in cache, dropping {username}")
                        return
                    user_status = self.user_utils.get_user_status(username)
                    self.cache.add(username)
                    if user_status == UserStatus.SUSPENDED \
                            or user_status == UserStatus.UNEXPECTED \
                            or user_status == UserStatus.SHADOWBANNED:
                        log.warning(f"Retrieved unwanted status {user_status.name} for user {username}, dropping modnote processing")
                        return
                    if type == "create":
                        usernotes_tb = self.tb_manipulator.get_user_notes(username)
                        manual_retry = 1
                        while manual_retry >= 1:
                            try:
                                usernotes_reddit = self.get_user_modnotes(username)
                                manual_retry = 0
                            except TooManyRequests as e:
                                log.warning("Hitting rate limiting while fetching user notes, sleeping")
                                time.sleep(manual_retry * 10)
                                manual_retry += 1
                        for tb_note in usernotes_tb:
                            if self.is_tb_in_modnote(tb_note, usernotes_reddit):
                                # Found match, nothing to do
                                log.debug("Found matching note, checking next entry")
                                continue
                            else:
                                # Need to create the note in reddit
                                redditor = username
                                label = self.tb_manipulator.get_note_modnote_label(tb_note)
                                date_s = self.tb_manipulator.get_note_date(tb_note)
                                note = f"{date_s} | {self.tb_manipulator.get_note_owner(tb_note)} | {self.tb_manipulator.get_note_content(tb_note)}"
                                thing = self.tb_manipulator.get_note_modnote_target(tb_note)
                                log.info(f"Creating mod note in new reddit from tb_note - user [{redditor}] label [{label}] content [{note}]")
                                manual_retry = 1
                                while manual_retry >= 1:
                                    try:
                                        reddit().sub.mod.notes.create(redditor=redditor, label=label,
                                                                    note=note, thing=thing)
                                        manual_retry = 0
                                    except TooManyRequests as e:
                                        log.warning("Hitting rate limiting during note creation, sleeping")
                                        time.sleep(manual_retry * 10)
                                        manual_retry += 1
                    elif type == "delete":
                        # todo
                        pass


            # Process a new modnote entry (new modnote)
            case "addnote":
                pass
