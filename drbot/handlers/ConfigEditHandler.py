from __future__ import annotations

import os
import re

import tomlkit
from praw.models import ModAction
from drbot import settings, log, reddit
from drbot.handlers import Handler


class ConfigEditHandler(Handler[ModAction]):

    def handle(self, item: ModAction) -> None:
        SETTINGS_PATH = os.path.join(os.path.dirname(__file__), '../../data/settings.toml')
        SETTINGS_PAGE = f"{settings.wiki_page}/settings"
        # If a removal reason is added, add the violation to the user's record
        if item.action == "wikirevise":
            if "surmodobot/settings" in item.details:
                log.info("Updating local copy of settings from wiki")
                data = reddit().sub.wiki[SETTINGS_PAGE].content_md
                rem_settings = {}
                with open(SETTINGS_PATH, "w") as f:
                    rem_settings = tomlkit.parse(data)
                    f.write(tomlkit.dumps(rem_settings))


