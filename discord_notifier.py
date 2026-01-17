#!/usr/bin/env python3
"""
Pixiv & X Discord Notifier
Monitors Pixiv and X accounts for new posts and sends Discord notifications
"""

import requests
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from pixivpy3 import AppPixivAPI
import tweepy
import deepl

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()

# Twitter accounts to monitor (set via TWITTER_USERNAMES env var, comma-separated)
def get_twitter_usernames():
    env_usernames = os.getenv('TWITTER_USERNAMES', '')
    if env_usernames:
        return [u.strip() for u in env_usernames.split(',') if u.strip()]
    return []

TWITTER_USERNAMES = get_twitter_usernames()


class DiscordNotifier:
    def __init__(self):
        """Initialize Discord notifier with API credentials"""
        # Discord webhook URLs (separate channels)
        self.pixiv_webhook = os.getenv('DISCORD_WEBHOOK_PIXIV')
        self.twitter_webhook = os.getenv('DISCORD_WEBHOOK_TWITTER')

        # Pixiv settings
        self.pixiv_user_id = os.getenv('PIXIV_USER_ID')
        self.pixiv_refresh_token = os.getenv('PIXIV_REFRESH_TOKEN')

        # X API credentials
        self.twitter_api_key = os.getenv('TWITTER_API_KEY')
        self.twitter_api_secret = os.getenv('TWITTER_API_SECRET')
        self.twitter_access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.twitter_access_token_secret = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        self.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')

        # Twitter accounts to monitor
        self.twitter_usernames = TWITTER_USERNAMES

        # DeepL translator
        self.deepl_key = os.getenv('DEEPL_API_KEY')
        self.translator = deepl.Translator(self.deepl_key) if self.deepl_key else None

        # Notified IDs file
        self.notified_file = Path('notified_ids.json')
        self.notified_ids = self.load_notified_ids()

        # Initialize Pixiv API
        self.pixiv_api = AppPixivAPI()
        if self.pixiv_refresh_token:
            try:
                self.pixiv_api.auth(refresh_token=self.pixiv_refresh_token)
                print("✅ Pixiv API authenticated")
            except Exception as e:
                print(f"⚠️ Pixiv API authentication failed: {e}")

        # Initialize X API
        self.twitter_client = tweepy.Client(
            bearer_token=self.twitter_bearer_token,
            consumer_key=self.twitter_api_key,
            consumer_secret=self.twitter_api_secret,
            access_token=self.twitter_access_token,
            access_token_secret=self.twitter_access_token_secret
        )

    def load_notified_ids(self):
        """Load already notified IDs"""
        self.is_first_run = False
        if self.notified_file.exists():
            with open(self.notified_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Check if first run (empty lists)
                if not data.get('pixiv') and not data.get('twitter'):
                    self.is_first_run = True
                return {
                    'pixiv': set(data.get('pixiv', [])),
                    'twitter': set(data.get('twitter', []))
                }
        self.is_first_run = True
        return {'pixiv': set(), 'twitter': set()}

    def save_notified_ids(self):
        """Save notified IDs"""
        with open(self.notified_file, 'w', encoding='utf-8') as f:
            json.dump({
                'pixiv': list(self.notified_ids['pixiv']),
                'twitter': list(self.notified_ids['twitter'])
            }, f, ensure_ascii=False, indent=2)

    def send_discord_notification(self, content, webhook_url):
        """Send notification to Discord via webhook"""
        try:
            response = requests.post(
                webhook_url,
                json={'content': content},
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Discord notification failed: {e}")
            return False

    def check_pixiv_new_posts(self):
        """Check for new Pixiv posts"""
        try:
            print("🔍 Checking Pixiv for new posts...")
            result = self.pixiv_api.user_illusts(self.pixiv_user_id)

            if not result or 'illusts' not in result:
                print("⚠️ No Pixiv posts found")
                return

            illusts = result['illusts'][:2]  # Check latest 2
            new_posts = []

            for illust in illusts:
                illust_id = str(illust['id'])
                if illust_id not in self.notified_ids['pixiv']:
                    new_posts.append(illust)

            if new_posts:
                print(f"🆕 Found {len(new_posts)} new Pixiv post(s)")
                for i, illust in enumerate(new_posts):
                    illust_id = str(illust['id'])
                    title = illust.get('title', 'Untitled')
                    link = f"https://www.pixiv.net/artworks/{illust_id}"

                    # Translate title
                    try:
                        if self.translator:
                            result = self.translator.translate_text(title, target_lang="EN-US")
                            translated = result.text
                        else:
                            translated = title
                    except:
                        translated = title

                    # First run: save ID only, no notification
                    if self.is_first_run:
                        self.notified_ids['pixiv'].add(illust_id)
                        print(f"📝 Saved (first run): {title}")
                    else:
                        message = f"{link}\n{title} / {translated}"
                        if self.send_discord_notification(message, self.pixiv_webhook):
                            self.notified_ids['pixiv'].add(illust_id)
                            print(f"✅ Notified: {title}")
                        # 3 second delay between notifications
                        if i < len(new_posts) - 1:
                            time.sleep(3)

                self.save_notified_ids()
            else:
                print("✅ No new Pixiv posts")

        except Exception as e:
            print(f"❌ Pixiv check error: {e}")

    def check_twitter_new_posts(self):
        """Check for new X (Twitter) posts from multiple accounts"""
        for i, username in enumerate(self.twitter_usernames):
            # Delay between accounts to avoid rate limit
            if i > 0:
                time.sleep(5)
            try:
                print(f"🔍 Checking X for new posts from @{username}...")

                # Get user ID from username
                user = self.twitter_client.get_user(username=username)
                if not user or not user.data:
                    print(f"⚠️ X user @{username} not found")
                    continue

                user_id = user.data.id

                # Get latest tweets
                tweets = self.twitter_client.get_users_tweets(
                    id=user_id,
                    max_results=5,  # API minimum is 5
                    exclude=['retweets', 'replies']
                )

                if not tweets or not tweets.data:
                    print(f"✅ No new X posts from @{username}")
                    continue

                new_posts = []
                for tweet in tweets.data[:2]:  # Check latest 2 only
                    tweet_id = str(tweet.id)
                    if tweet_id not in self.notified_ids['twitter']:
                        new_posts.append(tweet)

                if new_posts:
                    print(f"🆕 Found {len(new_posts)} new X post(s) from @{username}")
                    for i, tweet in enumerate(new_posts):
                        tweet_id = str(tweet.id)
                        link = f"https://twitter.com/{username}/status/{tweet_id}"

                        # First run: save ID only, no notification
                        if self.is_first_run:
                            self.notified_ids['twitter'].add(tweet_id)
                            print(f"📝 Saved (first run): {tweet_id}")
                        else:
                            message = f"**New X Post from @{username}**\n{link}"
                            if self.send_discord_notification(message, self.twitter_webhook):
                                self.notified_ids['twitter'].add(tweet_id)
                                print(f"✅ Notified: {tweet_id}")
                            # 3 second delay between notifications
                            if i < len(new_posts) - 1:
                                time.sleep(3)

                    self.save_notified_ids()
                else:
                    print(f"✅ No new X posts from @{username}")

            except Exception as e:
                print(f"❌ X check error for @{username}: {e}")

    def run(self):
        """Main execution function"""
        print("\n" + "="*60)
        print("🤖 Discord Notifier Running")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")

        self.check_pixiv_new_posts()
        print()
        self.check_twitter_new_posts()

        print("\n" + "="*60)
        print("✅ Check complete")
        print("="*60 + "\n")


if __name__ == '__main__':
    notifier = DiscordNotifier()
    notifier.run()
