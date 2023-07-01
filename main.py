"""
DRBOT - Do Really Boring Overhead Tasks
Originally developed for r/DebateReligion by u/c0d3rman @ https://github.com/c0d3rman/DRBOT
Forked and customized for the french community's needs @ https://github.com/0xAnansi/AutobanBOT
Free to use by anyone for any reason (licensed under CC0)
"""


import logging
import schedule
import time

from prawcore import TooManyRequests

from drbot import settings, log, reddit
from drbot.stores import *
from drbot.agents import *
from drbot.handlers import *


def main():
    log.info(f"AutobanBOT for r/{settings.subreddit} starting up")

    reddit.login()

    data_store = DataStore()

    # Save locally every minute
    schedule.every(1).minute.do(data_store.save)

    #if not settings.is_test_env:
    # Modlog agent

    modlog_agent = ModlogAgent(data_store)
    modlog_agent.register(ModQueueCleanerHandler())

    modlog_agent.register(ModNotesHandler())

    points_handler = PointsHandler()
    modlog_agent.register(points_handler)
    schedule.every().hour.do(points_handler.scan_all)
    modlog_agent.register(AdminHandler())
    config_handler = ConfigEditHandler()
    modlog_agent.register(config_handler)

    schedule.every(10).seconds.do(modlog_agent.run)

    # Comment agent
    comment_agent = CommentAgent(data_store)
    comment_agent.register(AutobanHandler())
    poll_handler = PollHandler()
    comment_agent.register(poll_handler)
    schedule.every(60).minutes.do(poll_handler.run_tally)
    schedule.every(30).seconds.do(comment_agent.run)

    # Periodic scan of points (scheduled last so other stuff happens first)

    #data_store.from_backup()
    # Load from wiki last to load data into the existing agents' data stores
    if settings.wiki_page != "":
        wiki_store = WikiStore(data_store)
        # Push save into wiki every 30mn to avoid spamming modlog
        schedule.every(15).minutes.do(wiki_store.save)

    #else:
        # poll_handler = PollHandler()
        # comment_agent = CommentAgent(data_store)
        # comment_agent.register(PollHandler())
        # schedule.every(30).seconds.do(poll_handler.run_tally)
    #     pass

    # Load from local backup just in case
    #data_store.from_backup()
    # Run all jobs immediately except those that shouldn't be run initially
    cont = 1
    while cont == 1:
        try:
            [job.run() for job in schedule.get_jobs() if "no_initial" not in job.tags]
            cont = 0
        except TooManyRequests as e:
            log.error("Hitting general rate limiting, missing management in method, sleeping")
            time.sleep(30)

    # The scheduler loop
    while True:
        cont = 1
        while cont == 1:
            try:
                schedule.run_pending()
                cont = 0
            except TooManyRequests as e:
                log.warning("Hitting general rate limiting, missing management in method, sleeping")
                time.sleep(30)
        t = schedule.idle_seconds()
        if t > 0:
            time.sleep(t)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Bot manually interrupted - shutting down...")
    except Exception as e:
        log.critical(e)
        raise e
    logging.shutdown()
