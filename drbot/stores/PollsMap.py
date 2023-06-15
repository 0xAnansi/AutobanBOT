import json
from drbot import settings, log, reddit
from drbot.util import get_dupes


class PollsMap:
    """
    Class that handles the mapping between removal reasons and their point costs.
    Also manages info about expiration durations.
    """

    def refresh_values(self):
        log.info("Loading polls actions.")

        # Check for dupes
        if len(settings.polls) != len(set(x["thread_id"] for x in settings.polls)):
            message = "Duplicate poll IDs in settings (the last instance of each one will be used):"
            for r in get_dupes(x["thread_id"] for x in settings.polls):
                message += f"\n\t{r}"
            log.error(message)

        # Build the map
        polls_map = {}
        for x in settings.polls:
            polls_map[x["thread_id"]] = {"thread_id":x["thread_id"], "options": list(x["options"])}

            if "min_account_age" in x:
                polls_map[x["thread_id"]]["min_account_age"] = str(x["min_account_age"])
            if "name" in x:
                polls_map[x["thread_id"]]["name"] = str(x["name"])
            if "duration" in x:
                polls_map[x["thread_id"]]["duration"] = str(x["duration"])
        log.debug(f"Polls map: {json.dumps(polls_map)}")

        self.polls = polls_map

    def __init__(self):
        self.polls = {}
        self.refresh_values()

    def __getitem__(self, poll):
        """Get the entry for a sub."""
        if poll not in self.polls:
            log.debug(f"Unknown entry for sub '{poll}'")
            return

        return self.polls[poll]

    # Return poll duration in hours
    def get_poll_duration(self, poll: dict) -> int:
        default = 24
        if "duration" not in poll:
            return default
        duration = poll["duration"]
        if len(duration) < 2:
            log.warn(f"Poll duration format seem wrong {duration}")
            return default
        unit = duration[-1]
        try:
            num = int(duration[:-1])
        except Exception as e:
            log.error(f"Error casting duration to int {duration}")
            return default
        match unit:
            case 'h':
                return num
            case 'd':
                return num * 24
            case 'w':
                return num * 24 * 7
            case 'm':
                # consider a month is 30 days
                return num * 24 * 30
            case 'y':
                # consider a year is 365 days
                return num * 24 * 365
            case _:
                log.error(f"Unexpected duration unit for poll {duration}")
        return default

    def get_poll_name(self, poll: dict) -> str:
        if "name" in poll:
            return poll["name"]
        return "The best poll ever polled"


