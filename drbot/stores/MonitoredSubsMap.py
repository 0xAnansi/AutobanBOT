import json
from drbot import settings, log, reddit
from drbot.util import get_dupes


class MonitoredSubsMap:
    """
    Class that handles the mapping between removal reasons and their point costs.
    Also manages info about expiration durations.
    """

    def refresh_values(self):
        log.info("Loading monitored subs and actions.")

        # Check for dupes
        if len(settings.monitored_subs) != len(set(x["id"] for x in settings.monitored_subs)):
            message = "Duplicate monitored subs IDs in settings (the last instance of each one will be used):"
            for r in get_dupes(x["id"] for x in settings.monitored_subs):
                message += f"\n\t{r}"
            log.error(message)

        # Build the map
        subs_map = {}
        for x in settings.monitored_subs:
            subs_map[x["id"]] = {"action": str(x["action"]), "display_name": str(x["id"])}
            if "label" in x:
                subs_map[x["id"]]["label"] = str(x["label"])
            if "note" in x:
                subs_map[x["id"]]["note"] = str(x["note"])
        log.debug(f"Subs map: {json.dumps(subs_map)}")

        self.subs_map = subs_map

    def __init__(self):
        self.subs_map = {}
        self.refresh_values()

    def __getitem__(self, sub):
        """Get the entry for a sub."""
        if sub not in self.subs_map:
            log.debug(f"Unknown entry for sub '{sub}'")
            return

        return self.subs_map[sub]

    def get_note(self, sub):
        """Get the expiration months for a removal reason (or the default if no special duration is specified)."""

        # Use default if this removal reason is unknown
        if sub not in self.subs_map:
            log.warning(f"Checking note for a sub that is not monitored [{sub}], this should not happen")
            return

        if "note" not in self.subs_map[sub]:
            note = f"Posts in {sub}"
            log.debug(f"Unknown note for '{sub}', using default note ({note}).")
            return note

        return self.subs_map[sub]["note"]

    def get_action(self, sub):

        # Use default if this action  is unknown
        if sub not in self.subs_map:
            log.warning(f"Checking action for a sub that is not monitored [{sub}], this should not happen.")
            return

        if "action" not in self.subs_map[sub]:
            note = "watch"
            log.warning(f"Unknown action for '{sub}', using default action ({note}). This should not happen.")
            return note

        return self.subs_map[sub]["action"]

    def get_label(self, sub):

        # Use default if this action  is unknown
        if sub not in self.subs_map:
            log.warning(f"Checking label for a sub that is not monitored [{sub}], this should not happen.")
            return

        if "label" not in self.subs_map[sub]:
            note = "SPAM_WATCH"
            log.warning(f"Unknown label for '{sub}', using default action ({note}). This should not happen.")
            return note

        return self.subs_map[sub]["label"]
