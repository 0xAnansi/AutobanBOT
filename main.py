"""
DRBOT - Do Really Boring Overhead Tasks
Originally eveloped for r/DebateReligion by u/c0d3rman @ https://github.com/c0d3rman/DRBOT
Forked and customized for the french community's needs @ https://github.com/0xAnansi/AutobanBOT
Free to use by anyone for any reason (licensed under CC0)
"""


import logging
import schedule
import time
from drbot import settings, log, reddit
from drbot.agents.CommentAgent import CommentAgent
from drbot.stores import *
from drbot.agents import *
from drbot.handlers import *


def main():
    log.info(f"AutobanBOT for r/{settings.subreddit} starting up")

    reddit.login()

    data_store = DataStore()
    schedule.every(1).minute.do(data_store.save)

    # Modlog agent

    modlog_agent = ModlogAgent(data_store)
    points_handler = PointsHandler()
    modlog_agent.register(points_handler)
    modlog_agent.register(AdminHandler())
    config_handler = ConfigEditHandler()
    modlog_agent.register(config_handler)
    schedule.every(30).seconds.do(modlog_agent.run)
    schedule.every().hour.do(points_handler.scan_all)

    # Comment agent
    comment_agent = CommentAgent(data_store)
    comment_agent.register(AutobanHandler())
    schedule.every(10).seconds.do(comment_agent.run)

    # Periodic scan of points (scheduled last so other stuff happens first)


    # Load from wiki last to load data into the existing agents' data stores
    if settings.wiki_page != "":
        wiki_store = WikiStore(data_store)
        schedule.every(1).minute.do(wiki_store.save)

    # Run all jobs immediately except those that shouldn't be run initially
    [job.run() for job in schedule.get_jobs() if "no_initial" not in job.tags]
    # The scheduler loop
    while True:
        schedule.run_pending()
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
