from __future__ import annotations
import re
from datetime import datetime
import urllib.request
import json
from praw.models import ModAction
from drbot import settings, log, reddit
from drbot.handlers import Handler


class AdminHandler(Handler[ModAction]):
    """Scans the modlog for actions by reddit's admins."""

    def handle(self, item: ModAction) -> None:
        if item._mod == "Anti-Evil Operations":
            log.warning(f"Reddit admins took action {item.action} on item {item.target_fullname} on {datetime.fromtimestamp(item.created_utc)}")

            if item.action == 'removecomment':
                kind = "comment"
            elif item.action == 'removelink':
                kind = "post"
            else:
                # Strange action, send a simple modmail and return
                if settings.admin_modmail:
                    reddit().send_modmail(subject=f'Admins took action "{item.action}" in your sub',
                                          body=f"Reddit's Anti-Evil Operations took action {item.action} in your sub.")
                log.info(f"Full info for unknown action type:\n{vars(item)}")
                return

            if settings.admin_modmail:
                message = f"On {datetime.fromtimestamp(item.created_utc)}, reddit's Anti-Evil Operations removed a {kind} in your sub.\n\nDue to pushshift being shutdown, the message originally available here could not be retrieved: [{item.target_permalink}]({item.target_permalink})"

                reddit().send_modmail(subject=f"Admins removed a {kind} in your sub", body=message)
