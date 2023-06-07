# AutobanBOT a bot that automate bans based on subreddits a user posts in or previous mod actions


AutobanBOT is a reddit bot that automatically monitors a subreddit and acts on specific events.

At this moment, the events are:
- New comment
- New modlog entry
- New modmail
- New post

For each of these events, a handler can be registered in the corresponding agent to implement a specific logic on each item the event is based on.

For example, the following handlers are built-in:


|            Handler             |  Agent  | Description                                                                                                                                                                              |
|:------------------------------:|:-------:|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|          AdminHandler          | Modlog  | Send a modmail to the sub when Reddit's AEO removes something                                                                                                                            |
|         AutobanHandler         | Comment | Either ban or add a modnote to a user based on subreddit this user has posted or commented in the past. <br/>This is similar to SafestBot, except this bot is FOSS and self-hostable     |
|       ConfigEditHandler        | Modlog  | Refresh the local copy of the settings file when a change in the wiki page is detected.                                                                                                  |
|         PointsHandler          | Modlog  | For each removed entry, attribute a number of points to a user based on the removal reason. <br/>Once a threshold is passed, either automatically ban the user or notify the moderators. |
|     SelfModerationHandler      | Modlog  | Remnant from DRBOT, untested here but should work. <br/>Send a modmail when a moderator self-moderate.                                                                                   |
|    ModMailMobileLinkHandler    | Modmail | Remnant from DRBOT, untested here but should work. <br/>Add mobile friendly links to modmails.                                                                                                |


This bot was made to be easily extendable with an Agent/Handler model.

## Prerequisites

This bot was built for python 3.11 and uses modern features.

I do not intend to support older versions of python.

You need to create a specific account on reddit for your bot. 

This bot will need pretty much all permissions on your sub to be able to run properly.

## Setup

1. Clone this repo and cd inside.
2. Optional but highly recommended, create your local virtual environment: `pyenv install 3.11.3 && pyenv virtualenv 3.11.3 venv_autobanbot && pyenv activate venv_autobanbot`
3. `pip install -r requirements.txt`
4. Run first-time setup: `python first_time_setup.py`. This will also create a settings file for you.
5. Change any other settings you want in `data/auth.toml`.
6. Run the bot: `python main.py`

## Configuration

This bot uses a wikipage as master config. All local changes will be overwritten when the setting page is detected as edited.

The setting page is available after the first run of the bot at https://www.reddit.com/r/<your_sub>/<wiki_page>/settings

## Caveats

Re-approving and then re-deleting a comment deletes the removal reason on reddit's side, so if you do this, be aware that DRBOT will treat the removal as having no reason as well.

## Difference with original DRBOT?

- Split config between server side settings and "application" settings where a wiki page is authority
- Removed sub specific features autoloading
- Added an antispambot/autoban feature based on user's history
- Added a CommentAgent to process handlers in new comments
  - Used as agent for the antispambot feature
- Removed pushshift use since reddit killed it

&nbsp;

<p xmlns:dct="http://purl.org/dc/terms/" xmlns:vcard="http://www.w3.org/2001/vcard-rdf/3.0#">
  <a rel="license"
     href="http://creativecommons.org/publicdomain/zero/1.0/">
    <img src="http://i.creativecommons.org/p/zero/1.0/88x31.png" style="border-style: none;" alt="CC0" />
  </a>
</p>