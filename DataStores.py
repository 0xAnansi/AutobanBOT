import abc
from typing import Any, Optional
from logging import Logger
from datetime import datetime
import json


class DataStore(metaclass=abc.ABCMeta):
    def __init__(self, logger: Logger):
        self.logger = logger

    @classmethod
    def __subclasshook__(cls, subclass):
        abstract_methods = ["add", "remove", "get_user", "get_user_total", "remove_user", "all_users", "get_last_updated", "_set_last_updated"]
        return all(hasattr(subclass, x) and callable(getattr(subclass, x)) for x in abstract_methods) or NotImplemented

    @abc.abstractmethod
    def add(self, username: str, violation_fullname: str, point_cost: int, expires: Optional[datetime] = None) -> bool:
        """Add a violation to a user's record. Returns True if the data structure was changed."""
        raise NotImplementedError

    @abc.abstractmethod
    def remove(self, username: str, violation_fullname: str) -> bool:
        """Remove a violation from a user's record. Returns True if the data structure was changed."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_user(self, username: str) -> dict[str, Any]:
        """Get all violations of a user."""
        raise NotImplementedError

    def get_user_total(self, username):
        """Convenience method to get the total points from a user."""
        return sum(x["cost"] for x in self.get_user(username).values())

    @abc.abstractmethod
    def remove_user(self, username: str) -> bool:
        """Remove a user's entire record. Returns True if the data structure was changed."""
        raise NotImplementedError

    @abc.abstractmethod
    def all_users(self) -> list[str]:
        """Get a list of all users who have violations."""
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_updated(self) -> datetime:
        """Get the time of the latest entry with which the data store was updated."""
        raise NotImplementedError

    def set_last_updated(self, d) -> bool:
        """Set the time of the latest entry with which the data store was updated.
        Will refuse to decrement the time - it can only increase.
        Returns True if the time was updated and False if it wasn't."""
        return self._set_last_updated(d) if d > self.get_last_updated() else False
    
    @abc.abstractmethod
    def _set_last_updated(self, d) -> bool:
        """Set the time of the latest entry with which the data store was updated.
        Implement this without safety checking for decrementing the time; the parent class method takes care of it.
        Returns True if the time was updated and False if it wasn't."""
        raise NotImplementedError


class LocalDataStore(DataStore):
    """Stores all data locally in a dict."""

    def __init__(self, logger: Logger):
        self.megadict = {}
        self.meta = {
            "last_updated": 0
        }
        super().__init__(logger)

    def add(self, username: str, violation_fullname: str, point_cost: int, expires: Optional[datetime] = None) -> bool:
        if not username in self.megadict:
            self.megadict[username] = {}
        elif violation_fullname in self.megadict[username]:
            self.logger.debug(f"Can't add {violation_fullname} to u/{username} (already exists).")
            return False
        self.megadict[username][violation_fullname] = {"cost": point_cost}
        if not expires is None:
            self.megadict[username][violation_fullname]["expires"] = int(datetime.timestamp(expires))
        self.logger.debug(f"Added {violation_fullname} to u/{username}.")
        return True

    def remove(self, username: str, violation_fullname: str) -> bool:
        if not username in self.megadict:
            self.logger.debug(f"Can't remove {violation_fullname} from u/{username} (user doesn't exist).")
            return False
        if not violation_fullname in self.megadict[username]:
            self.logger.debug(f"Can't remove {violation_fullname} from u/{username} (violation doesn't exist).")
            return False
        del self.megadict[username][violation_fullname]
        self.logger.debug(f"Removed {violation_fullname} from u/{username}.")
        if len(self.megadict[username]) == 0:
            del self.megadict[username]
        return True

    def get_user(self, username: str) -> dict[str, Any]:
        return {k1: {k2: datetime.fromtimestamp(v2) if k2 == "expires" else v2 for k2, v2 in v1.items()} for k1, v1 in self.megadict.get(username, {}).items()}

    def remove_user(self, username: str) -> bool:
        if not username in self.megadict:
            self.logger.debug(f"Can't remove u/{username} (doesn't exist).")
            return False
        self.logger.debug(f"Removed u/{username}.")
        del self.megadict[username]
        return True

    def all_users(self) -> list[str]:
        return list(self.megadict.keys())
    
    def get_last_updated(self) -> datetime:
        return datetime.fromtimestamp(self.meta["last_updated"])
    
    def _set_last_updated(self, d) -> bool:
        self.meta["last_updated"] = int(datetime.timestamp(d))
        return True

    def save_json(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump({"meta": self.meta, "megadict": self.megadict}, f)
        self.logger.debug(f"Saved LocalDataStore to JSON..")

    def load_json(self, path: str) -> None:
        with open(path, "r") as f:
            raw = json.load(f)
            self.meta = raw["meta"]
            self.megadict = raw["megadict"]
        self.logger.debug(f"Loaded LocalDataStore from JSON.")
