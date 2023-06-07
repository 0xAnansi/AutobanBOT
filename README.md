# AutobanBOT a bot that automate bans based on subreddits a user posts in or previous mod actions


AutobanBOT is a reddit bot that automatically monitors a subreddit and tracks removals. 

Each removal of a user's submission gives that user a certain number of points, and once their points hit some threshold, the bot takes action, either by notifying the mods or automatically banning the user.

On top of this, the bot monitors new comments on the subreddit and can either ban a user or put a modnote on it based on posts in specific subreddits.

This bot was made to be easily extandable with an Agent/Handler model.

## Setup

1. Clone this repo and cd inside.
2. `pip install -r requirements.txt`
3. Run first-time setup: `python first_time_setup.py`. This will also create a settings file for you.
4. Change any other settings you want in `data/auth.toml`.
5. Run the bot: `python main.py`

## Configuration

This bot uses a wikipage as master config. All local changes will be overwritten when the setting page is detected as edited.

The setting page is available after the first run of the bot at https://www.reddit.com/r/<your_sub>/surmodobot/settings

## Caveats

Re-approving and then re-deleting a comment deletes the removal reason on reddit's side, so if you do this, be aware that DRBOT will treat the removal as having no reason as well.

&nbsp;

<p xmlns:dct="http://purl.org/dc/terms/" xmlns:vcard="http://www.w3.org/2001/vcard-rdf/3.0#">
  <a rel="license"
     href="http://creativecommons.org/publicdomain/zero/1.0/">
    <img src="http://i.creativecommons.org/p/zero/1.0/88x31.png" style="border-style: none;" alt="CC0" />
  </a>
</p>