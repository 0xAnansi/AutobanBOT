from enum import Enum, auto


class UserStatus(Enum):
    ACTIVE = auto()
    SUSPENDED = auto()
    SHADOWBANNED = auto()
    BANNED = auto()
    UNEXPECTED = auto()