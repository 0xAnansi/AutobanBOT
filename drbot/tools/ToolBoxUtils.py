import praw
import prawcore
from praw.models import ModNote, Submission, Comment

from drbot import log
import pandas as pd
import base64
import zlib
import json

from praw import Reddit

"""
    Once decoded, the following information is structured as follows:
    self.mod_notes contains the full mod logs of all users with the format mod_notes['username']
    mod_notes['username']['ns'] contains all notes for the user as list, one entry represented as note below
        note['n']: content of the note (str)
        note['t']: timestamp (int)
        note['m']: id of the moderator in TB (see later) (int)
        note['l']: components of the link concerned by the note (str) - formatted like 'l,thread_id,comment_id' for comment, full link for modmails
        note['w']: id of the note type (see later) (id)

    In root object that we get from TB, we can access 2 items:
    blob: contains the notes as b64
    constants: contains 2 types of entries:
        - users: mods as list, where index is the same as note['m']
        - warnings: note types as list, where index is the same as note['w']
"""

class Converter:
    def __init__(self):
        self.wiki_notes = dict()
        self.cleaned_usernotes = dict()
        self.combined_notes = dict()
        self.df = pd.DataFrame()

    def add(self, wiki, notes):
        self.wiki_notes = wiki
        self.cleaned_usernotes = notes
        self.wiki_notes = self.combine_json()
        self.df = pd.DataFrame.from_dict(self.cleaned_usernotes)

    def empty_notes(func):
        def f(self):
            if not self.wiki_notes:
                raise Exception(f"Not authenticated or no information provided.")
            format_name = func(self)
            log.warning(f"{format_name} file created in current directory")

        return f

    def combine_json(self):
        self.wiki_notes['blob'] = self.cleaned_usernotes
        return self.wiki_notes.copy()

    def combinednotes(self):
        return self.wiki_notes

    @empty_notes
    def json_format(self):
        self.df.to_json('usernotes_json.json')
        return "JSON"

    @empty_notes
    def csv_format(self):
        self.df.to_csv('usernotes_csv.csv', encoding='utf-8', index=False)
        return "CSV"


class BlobDecoder:
    def pInflate(self, data) -> bytes:
        decompress = zlib.decompressobj(15)
        decompressed_data = decompress.decompress(data)
        decompressed_data += decompress.flush()
        return decompressed_data

    def b64d(self, data: str) -> bytes:
        return base64.b64decode(data)

    def js_byte_to_string(self, data: bytes) -> str:
        return data.decode("utf-8")
    def __init__(self):
        self.cleaned_notes = dict()
        self.notelength = int

    def blob_to_string(self, blob: str) -> dict:
        """Base64 -> zlib-compressed -> string -> dict"""
        # base64 decode blob
        zlib_bytes = self.b64d(str.encode(blob))

        # zlib-uncompress to byte
        decompressed_bytes = self.pInflate(zlib_bytes)

        # byte to string
        clean_string = self.js_byte_to_string(decompressed_bytes)

        # Return dict
        self.cleaned_notes = json.loads(clean_string)

        # sum of values to get total
        note_count = [len(x['ns']) for x in self.cleaned_notes.values()]
        self.notelength = sum(note_count)

        return self.cleaned_notes

    def conv_blob(self) -> dict:
        return self.cleaned_notes

    def note_length(self) -> int:
        return self.notelength


class ToolBoxManipulator:
    def __init__(self, reddit: Reddit, bot_name: str):
        self.tb_converter = Converter()
        self.tb_decoder = BlobDecoder()
        self.mod_notes = []
        self.mod_notes_constants = []
        self.tb_notes_version = 0
        self.wiki_content = ""
        self.reddit = reddit
        self.subreddit = reddit.sub
        self.bot_name = bot_name
        self.refresh_tb()

    @staticmethod
    def _get_index_from_val(entries: dict, val: str):
        if val in entries:
            return entries.index(val)
        else:
            return -1

    @staticmethod
    def _get_val_from_index(entries: dict, index: int) -> str:
        if index < len(entries):
            return entries[index]
        else:
            return "Unknown"

    def get_modo_from_index(self, index: int) -> str:
        return self._get_val_from_index(self.mod_notes_constants["users"], index)

    def get_index_from_modo(self, modo: str) -> int:
        return self._get_index_from_val(self.mod_notes_constants["users"], modo)

    def get_note_type_from_index(self, index: int) -> str:
        return self._get_val_from_index(self.mod_notes_constants["warnings"], index)

    def get_index_from_note_type(self, modo: str) -> int:
        return self._get_index_from_val(self.mod_notes_constants["warnings"], modo)


    @staticmethod
    def get_modnote_label_from_tb_label(tb_label):
        match tb_label:
            case "spamwarning" | 'spamwarn' | "spam":
                return "SPAM_WARNING"
            case 'spamwatch':
                return "SPAM_WATCH"
            case "ban_permanent" | 'permanent_ban' | 'permban':
                return "PERMA_BAN"
            case 'ban_1j' | 'ban_3j' | 'ban_7j' | 'ban_15j' | 'ban_30j' | 'ban_non_perma' | 'ban':
                return "BAN"
            case "abusewarning" | 'abusewarn':
                return "ABUSE_WARNING"
            case 'niaisere' | 'gooduser' | 'good':
                return "HELPFUL_USER"
            case 'botban':
                return "BOT_BAN"
            case 'non_signale':
                # Cases where I've no idea what the category initially meant
                return None
            case _:
                return None

    def get_note_modnote_label(self, note: dict):
        #['spamwarning', 'ban_permanent', 'abusewarning', 'ban_1j', 'abusewarn', 'ban_7j', 'non_signale', None, 'ban_30j', 'spamwatch', 'niaisere', 'gooduser', 'botban',
        # 'ban_3j', 'good', 'spamwarn', 'ban', 'ban_15j', 'permanent_ban']
        #"ABUSE_WARNING", "BAN", "BOT_BAN", "HELPFUL_USER", "PERMA_BAN", "SOLID_CONTRIBUTOR", "SPAM_WARNING", "SPAM_WATCH", or None.
        tb_label = self.get_note_type_from_index(note['w'])
        return self.get_modnote_label_from_tb_label(tb_label)

        pass
    def get_note_type(self, note: dict):
        return self.get_note_type_from_index(note['w'])

    def get_note_owner(self, note: dict):
        return self.get_modo_from_index(note['m'])

    def get_note_date(self, note: dict):
        timest = self.get_note_timestamp(note)
        try:
            dt = pd.to_datetime(int(timest), utc=True, unit='s')
            return dt.date()
        except:
            log.error(f"Failed to transform timestamp to date, sending default value")
            return "None"

    def get_note_content(self, note: dict):
        return note['n']

    def get_note_timestamp(self, note: dict):
        return note['t']

    def get_note_target_link(self, note: dict):
        return note['l']

    def get_note_modnote_thing(self, note: dict) -> Submission | Comment | str | None:
        #  https://github.com/toolbox-team/reddit-moderator-toolbox/wiki/Subreddit-Wikis%3A-usernotes
        """
        l,(SUBMISSION_ID),(COMMENT_ID) represents a link to a comment, and can be expanded to https://www.reddit.com/comments/(SUBMISSION_ID)/_/(COMMENT_ID).
        l,(SUBMISSION_ID) represents a link to a submission, and can be expanded to https://www.reddit.com/comments/(SUBMISSION_ID) or https://redd.it/(SUBMISSION_ID).
        m,(THREAD_ID) represents a link to an old modmail thread and is equivalent to https://www.reddit.com/message/messages/(THREAD_ID).
        Full URLs are sometimes stored directly. Toolbox itself stores links to new modmail threads as full URLs, for example.
        Writing full URLs other than new modmail permalinks is discouraged—don't introduce external URLs, and use the shorthand formats for other resources on Reddit.
        However, for legacy support, you should support reading arbitrary URLs (not just new modmail links), and optionally convert them to the shorthand formats when applicable.
        """
        target = self.get_note_target_link(note)
        if target.startswith('http'):
            return target
        elif len(target) > 4:
            t_components = target.split(',')
            if 2 <= len(t_components) <= 3:
                l_type = t_components[0]
                if l_type == 'l':
                    l_sub = self.reddit.submission(t_components[1])
                    if len(t_components) == 3:
                        l_com = self.reddit.comment(t_components[2])
                        return l_com
                    return l_sub
                elif l_type == 'm':
                    return f"https://www.reddit.com/message/messages/{t_components[1]}"
            else:
                log.error(f"Unexpected value while parsing tb_note link [{target}]")
                return None
        else:
            log.error(f"Unexpected value while parsing tb_note link [{target}]")
            return None

    def get_note_modnote_target(self, note: dict):
        target = self.get_note_modnote_thing(note)
        if isinstance(target, Comment) or isinstance(target, Submission):
            return target
        else:
            log.info("Cannot convert TB link to modnote format, dropping info")
            return None

    def refresh_tb(self):
        try:
            wiki = self.subreddit.wiki["usernotes"].content_md
            self.wiki_content = json.loads(wiki)
        except prawcore.exceptions.NotFound:
            raise Exception(f"NameError: r/{self.subreddit.display_name} is missing the `usernotes` wiki page!")
        except prawcore.exceptions.Forbidden:
            raise Exception(f"Unauthorized: You don't have `wiki` access on r/{self.subreddit.display_name}!")
        except Exception as e:
            log.error(f"Error while loading TB from wiki: {e.message}")
            raise Exception("Did not reach Reddit https://redditstatus.com/")
        else:
            if self.wiki_content['ver'] != 6:
                raise Exception(f"VersionError: TB usernotes v{self.wiki_content['var']} is not supported. Supported v6")
            self.tb_notes_version = self.wiki_content['ver']
            self.mod_notes = self.tb_decoder.blob_to_string(self.wiki_content["blob"])
            self.mod_notes_constants = self.wiki_content['constants']

    def get_user_notes(self, username: str) -> []:
        ret = []
        if username in self.mod_notes:
            return list(reversed(self.mod_notes[username]['ns']))
        return ret

    @staticmethod
    def _extract_modname_from_note(note: str) -> str:
        retval = note.split("|")
        # No match for target format
        if len(retval) == 0:
            return False
        # Return first split without beginning and ending whitespace, just in case
        return retval[0].strip()

    def are_tb_note_and_modnote_same(self, tb_note: dict, modnote: ModNote, strict: bool = False) -> bool:
        """
        [WARNING] This does not check for modnote target due to the structure of the tb_note. This must be done before calling this method.

        Modnote structure:
            action: If this note represents a moderator action, this field indicates the type of action. For example, "banuser" if the action was banning a user.
            created_at: Time the moderator note was created, represented in Unix Time.
            description: If this note represents a moderator action, this field indicates the description of the action. For example, if the action was banning the user, this is the ban reason.
            details: If this note represents a moderator action, this field indicates the details of the action. For example, if the action was banning the user, this is the duration of the ban.
            id: The ID of the moderator note.
            label: The label applied to the note, currently one of: "ABUSE_WARNING", "BAN", "BOT_BAN", "HELPFUL_USER", "PERMA_BAN", "SOLID_CONTRIBUTOR", "SPAM_WARNING", "SPAM_WATCH", or None.
            moderator: The moderator who created the note.
            note: The text of the note.
            reddit_id: The fullname of the object this note is attributed to, or None if not set. If this note represents a moderators action, this is the fullname of the object the action was performed on.
            subreddit: The subreddit this note belongs to.
            type: The type of note, currently one of: "APPROVAL", "BAN", "CONTENT_CHANGE", "INVITE", "MUTE", "NOTE", "REMOVAL", or "SPAM".
            user: The redditor the note is for.

        https://github.com/toolbox-team/reddit-moderator-toolbox/wiki/Subreddit-Wikis%3A-usernotes
        tb_note structure:
            note['n']: content of the note (str)
            note['t']: timestamp (int)
            note['m']: id of the moderator in TB (see later) (int)
            note['l']: components of the link concerned by the note (str) - formatted like 'l,thread_id,comment_id' for comment, full link for modmails
            note['w']: id of the note type (see later) (id)

        Important infos to check:
            - action
            - description
            - details
            - label
            - note
            - reddit_id
            - subreddit
            - type
            - user

        Action to set / check in modnote using custom implementation since we can only impersonate from modnote to TB and not the other way
            - moderator
        """
        # Check if content of modnote is in tb_note or fails
        if tb_note['n'] not in modnote.note:
            return False
        # Check if the note was manually entered and needs to have the same owner or
        # if one of the 2 notes was made byt the bot, check if this is a migrated/translated note
        # format of the translated note is as follows:
        # moderator_name | original content of note
        # Manual notes that include a | should fail graciously
        if modnote.moderator.name != self.get_modo_from_index(tb_note['m']):
            if modnote.moderator.name != self.bot_name:
                return False
            else:
                original_modnote_modname = self._extract_modname_from_note(tb_note['n'])
                # Check if the mod name in the note text is the same as the one in TB (case where TB note was migrated to modnotes)
                if original_modnote_modname != self.get_modo_from_index(tb_note['m']):
                    return False
        # Here we should be relatively sure that both entries were made by the same mod
        if not strict:
            # Creator and content are same, don't care about the rest
            return True
        if not modnote.label == self.get_note_type_from_index(tb_note['w']):
            return False

        pass




