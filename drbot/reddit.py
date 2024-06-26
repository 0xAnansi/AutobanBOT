import praw
import json
import prawcore
from prawcore import Requestor
import random
from typing import Optional
from requests.status_codes import codes
import logging
from drbot import settings, log
from drbot.log import ModmailLoggingHandler, TemplateLoggingFormatter, BASE_FORMAT

DRBOT_CLIENT_ID_PATH = "drbot/drbot_client_id.txt"

# handler = logging.StreamHandler()
# handler.setLevel(logging.DEBUG)
# for logger_name in ("praw", "prawcore"):
#     logger = logging.getLogger(logger_name)
#     logger.setLevel(logging.DEBUG)
#     logger.addHandler(handler)

class InfiniteRetryStrategy(prawcore.sessions.RetryStrategy):
    """For use with PRAW.
    Retries requests forever using capped exponential backoff with jitter.
    This prevents the bot from dying when reddit's servers have an outage or the internet is down.
    Use by setting
        reddit._core._retry_strategy_class = InfiniteRetryStrategy
    right after initializing your praw.Reddit object."""

    def _sleep_seconds(self):
        if self._attempts == 0:
            return None
        if self._attempts > 3:
            log.warn(f"Request still failing after multiple tries, retrying... ({self._attempts})")
        return random.randrange(0, min(self._cap, self._base * 2 ** self._attempts))

    def __init__(self, _base=2, _cap=60, _attempts=0):
        self._base = _base
        self._cap = _cap
        self._attempts = _attempts

    def consume_available_retry(self):
        return type(self)(_base=self._base, _cap=self._cap, _attempts=self._attempts + 1)

    def should_retry_on_failure(self):
        return True


del prawcore.Session.STATUS_EXCEPTIONS[codes["too_many_requests"]]
prawcore.Session.RETRY_STATUSES.add(codes["too_many_requests"])
    
class JSONDebugRequestor(Requestor):
    def request(self, *args, **kwargs):
        response = super().request(*args, **kwargs)
        with open("log_file.json", "a") as f:
            if "https://oauth.reddit.com/api/mod/notes" in args[1]:
                log.warn("Logging modnote request")
                #f.write(json.dumps({"args": args, "kwargs": kwargs, "response": response.json()}) + '\n' + '\n')
                f.write(response.text + '\n' + '\n')
                log.warn("Request logged")
        return response

class Reddit(praw.Reddit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._core._retry_strategy_class = InfiniteRetryStrategy



    @property
    def sub(self):
        return self.subreddit(settings.subreddit)

    def user_exists(self, username: str) -> bool:
        """Check if a user exists on reddit."""
        try:
            self.redditor(username).fullname
        except prawcore.exceptions.NotFound:
            return False  # Account deleted
        except AttributeError:
            return False  # Account suspended
        else:
            return True

    def page_exists(self, page: str) -> bool:
        try:
            self.sub.wiki[page].may_revise
            return True
        except prawcore.exceptions.NotFound:
            return False

    def get_thing(self, fullname: str) -> praw.reddit.models.Comment | praw.reddit.models.Submission:
        """For getting a comment or submission from a fullname when you don't know which one it is."""
        if fullname.startswith("t1_"):
            return self.comment(fullname)
        elif fullname.startswith("t3_"):
            return self.submission(fullname[3:])  # PRAW requires us to chop off the "t3_"
        else:
            raise Exception(f"Unknown fullname type: {fullname}")

    def send_modmail(self, subject: str, body: str, recipient: Optional[praw.reddit.models.Redditor | str] = None, add_common: bool = True, archive: bool = False, **kwargs) -> None:
        """Sends modmail, handling dry_run mode.
        Creates a moderator discussion by default if a recipient is not provided."""

        # Add common elements
        if add_common:
            subject = "AutobanBOT: " + subject
            body += "\n\n(This is an automated message by [AutobanBOT](https://github.com/0xAnansi/AutobanBOT/).)"

        # Hide username by default in modmails to users
        if not recipient is None and not 'author_hidden' in kwargs:
            kwargs['author_hidden'] = True

        if settings.dry_run:
            log.info(f"""[DRY RUN: would have sent the following modmail:
    Subject: "{subject}"
    {body}]""")
        else:
            log.info(f'Sending modmail {"as mod discussion " if recipient is None else f"to u/{recipient} "}with subject "{subject}"')
            log.debug(f"""Sending modmail:
    Recipient: {"mod discussion" if recipient is None else f"u/{recipient}"}
    Subject: "{subject}"
    {body}""")

            if len(body) > 10000:
                log.warning(f'Modlog "{subject}" over maximum length, truncating.')
                trailer = "... [truncated]"
                body = body[:10000 - len(trailer)] + trailer

            modmail = self.sub.modmail.create(subject=subject, body=body, recipient=recipient, **kwargs)
            if archive:
                modmail.archive()

    def is_mod(self, username: str | praw.reddit.models.Redditor) -> bool:
        """Check if a user is a mod in your sub"""
        if isinstance(username, praw.reddit.models.Redditor):
            username = username.name
        return len(self.sub.moderator(username)) > 0


_reddit = None


def reddit() -> praw.Reddit:
    if _reddit is None:
        raise Exception("You need to call reddit.login() before you can use the reddit() object.")
    return _reddit


def login() -> praw.Reddit:
    global _reddit

    if settings.refresh_token != "":
        with open(DRBOT_CLIENT_ID_PATH, "r") as f:
            drbot_client_id = f.read()
        _reddit = Reddit(client_id=drbot_client_id,
                         client_secret=None,
                         refresh_token=settings.refresh_token,
                         #requestor_class=JSONDebugRequestor,
                         user_agent="Moderation helper https://github.com/0xAnansi/AutobanBOT v1.0 (by /u/FromModToSirius")
    else:
        _reddit = Reddit(client_id=settings.client_id,
                         client_secret=settings.client_secret,
                         username=settings.username,
                         password=settings.password,
                         #requestor_class=JSONDebugRequestor,
                         user_agent="Moderation helper https://github.com/0xAnansi/AutobanBOT v1.0 (by /u/FromModToSirius")

    log.info(f"Logged in to Reddit as u/{_reddit.user.me().name}")

    try:
        if not _reddit.subreddit(settings.subreddit).user_is_moderator:
            raise Exception(f"u/{_reddit.user.me().name} is not a mod in r/{settings.subreddit}")
    except prawcore.exceptions.Forbidden:
        raise Exception(f"r/{settings.subreddit} is private or quarantined.")
    except prawcore.exceptions.NotFound:
        raise Exception(f"r/{settings.subreddit} is banned.")

    # Set up logging to modmail for non test run
    if not settings.dry_run and settings.modmail_logging:
        log.info(f"Loading modmail logger because settings is at {settings.modmail_logging}")
        modmail_handler = ModmailLoggingHandler(_reddit)
        modmail_handler.setFormatter(TemplateLoggingFormatter(fmt=BASE_FORMAT, template={
            logging.ERROR: """DRBOT has encountered a non-fatal error:
    
    ```
    {log}
    ```
    
    DRBOT is still running. Check the log for more details.""",
            logging.CRITICAL: """DRBOT has encountered a fatal error and crashed:
    
    ```
    {log}
    ```"""}))
        modmail_handler.setLevel(logging.ERROR)
        log.addHandler(modmail_handler)


reddit.login = login
