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

    Once decoded, the following information is structured as follows:
    self.mod_notes contains the full mod logs of all users with the format mod_notes['username']
    mod_notes['username']['ns'] contains all notes for the user as list, one entry represented as note below
    note['n']: content of the note (str)
    note['t']: timestamp (int)
    note['m']: id of the moderator in TB (see later) (int)
    note['l']: components of the link concerned by the note (str) - formatted like 'l,thread_id,comment_id' for comment, full link for modmails
    note['w']: id of the note type (see later)

    In root object that we get from TB, we can access 2 items:
    blob: contains the notes as b64
    constants: contains 2 types of entries:
        - users: mods as list, where index is the same as note['m']
        - warnings: note types as list, where index is the same as note['w']
    """

    def setup(self, agent: Agent[ModAction]) -> None:
        super().setup(agent)
        self.tb_converter = ToolBoxUtils.Converter()
        self.tb_decoder = ToolBoxUtils.BlobDecoder()
        self.cache = {}
        self.mod_notes = {}


    def refresh_notes_from_tb(self):
        """Retrive usernotes from subreddit wiki and checks the version compatibility"""
        try:
            wiki = reddit().sub.wiki["usernotes"].content_md
            wiki = json.loads(wiki)
        except prawcore.exceptions.NotFound:
            raise Exception(f"NameError: r/{reddit().sub.display_name} is missing the `usernotes` wiki page!")
        except prawcore.exceptions.Forbidden:
            raise Exception(f"Unauthorized: You don't have `wiki` access on r/{reddit().sub.display_name}!")
        except Exception as e:
            log.error(f"Error while loading TB from wiki: {e.message}")
            raise Exception("Did not reach Reddit https://redditstatus.com/")
        else:
            if wiki['ver'] != 6:
                raise Exception(f"VersionError: TB usernotes v{wiki['var']} is not supported. Supported v6")
            self.mod_notes = self.tb_decoder.blob_to_string(wiki["blob"])
            self.mod_notes_constants = wiki['constants']
            #self.tb_converter.add(wiki, self.mod_notes)

    def start_run(self) -> None:
        log.debug("Invalidating cache.")
        self.cache = {}
        self.refresh_notes_from_tb()

    def is_tb_note_action(self, item):
        return item.details == "Page usernotes edited"

    def extract_username_from_tb_action(self, item):
        #test = "\"create new note on new user Live-Cover4440\" via toolbox"
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
            case "wikirevise":
                if self.is_tb_note_action(item):
                    username = self.extract_username_from_tb_action(item)
                    if len(username) <= 0:
                        log.error(f"Failed to retrieve username, dropping modnote processing")
                        return
                    # todo: extract usernotes from TB and push it into modnotes
                pass
            case "addnote":
                pass
