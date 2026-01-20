#!/usr/bin/env python3
"""
Patreon Discord Notifier
Monitors Patreon for new posts with specific tier access and sends Discord notifications
"""

import requests
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()


class PatreonNotifier:
    def __init__(self):
        """Initialize Patreon notifier with API credentials"""
        self.webhook = os.getenv('DISCORD_WEBHOOK_PATREON')
        self.access_token = os.getenv('PATREON_ACCESS_TOKEN')
        self.campaign_id = os.getenv('PATREON_CAMPAIGN_ID')
        self.target_tier_id = os.getenv('PATREON_TARGET_TIER_ID')

        # Notified IDs file
        self.notified_file = Path('patreon_notified_ids.json')
        self.notified_ids = self.load_notified_ids()

    def load_notified_ids(self):
        """Load already notified IDs"""
        self.is_first_run = False
        if self.notified_file.exists():
            with open(self.notified_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data.get('patreon'):
                    self.is_first_run = True
                return set(data.get('patreon', []))
        self.is_first_run = True
        return set()

    def save_notified_ids(self):
        """Save notified IDs"""
        with open(self.notified_file, 'w', encoding='utf-8') as f:
            json.dump({'patreon': list(self.notified_ids)}, f, ensure_ascii=False, indent=2)

    def send_discord_notification(self, content):
        """Send notification to Discord via webhook"""
        try:
            response = requests.post(
                self.webhook,
                json={'content': content},
                timeout=10
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"❌ Discord notification failed: {e}")
            return False

    def check_new_posts(self):
        """Check for new Patreon posts with target tier access"""
        if not self.access_token or not self.webhook or not self.campaign_id or not self.target_tier_id:
            print("⚠️ Patreon not configured, skipping...")
            return

        try:
            print("🔍 Checking Patreon for new posts...")
            headers = {'Authorization': f'Bearer {self.access_token}'}

            # Get posts with tier info
            url = f'https://www.patreon.com/api/oauth2/v2/campaigns/{self.campaign_id}/posts'
            params = {
                'fields[post]': 'title,url,published_at,tiers'
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            posts = data.get('data', [])

            new_posts = []
            for post in posts:
                post_id = post['id']
                if post_id not in self.notified_ids:
                    # Check if this post includes target tier
                    tiers = post.get('attributes', {}).get('tiers', [])
                    if int(self.target_tier_id) in tiers:
                        new_posts.append(post)

            if new_posts:
                print(f"🆕 Found {len(new_posts)} new Patreon post(s) with Gourmet tier")
                for i, post in enumerate(new_posts):
                    post_id = post['id']
                    title = post.get('attributes', {}).get('title', 'Untitled')
                    post_url = post.get('attributes', {}).get('url', f'https://www.patreon.com/posts/{post_id}')

                    if self.is_first_run:
                        self.notified_ids.add(post_id)
                        print(f"📝 Saved (first run): {title}")
                    else:
                        if self.send_discord_notification(post_url):
                            self.notified_ids.add(post_id)
                            print(f"✅ Notified: {title}")
                        if i < len(new_posts) - 1:
                            time.sleep(3)

                self.save_notified_ids()
            else:
                print("✅ No new Patreon posts with Gourmet tier")

        except Exception as e:
            print(f"❌ Patreon check error: {e}")

    def run(self):
        """Main execution function"""
        print("\n" + "="*60)
        print("🤖 Patreon Notifier Running")
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60 + "\n")

        self.check_new_posts()

        print("\n" + "="*60)
        print("✅ Check complete")
        print("="*60 + "\n")


if __name__ == '__main__':
    notifier = PatreonNotifier()
    notifier.run()
