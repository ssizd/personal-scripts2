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
        self.campaign_id = os.getenv('PATREON_CAMPAIGN_ID', '13098189')
        self.target_tier_id = os.getenv('PATREON_TARGET_TIER_ID', '24453472')  # Gourmet tier

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
        if not self.access_token or not self.webhook:
            print("⚠️ Patreon not configured, skipping...")
            return

        try:
            print("🔍 Checking Patreon for new posts...")
            headers = {'Authorization': f'Bearer {self.access_token}'}

            # Get posts with tier info
            url = f'https://www.patreon.com/api/oauth2/v2/campaigns/{self.campaign_id}/posts'
            params = {
                'include': 'access_rules',
                'fields[post]': 'title,url,published_at',
                'fields[access_rule]': 'access_rule_type,tier_id',
                'page[count]': 5
            }

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            posts = data.get('data', [])
            included = data.get('included', [])

            # Build tier map from access rules
            post_tiers = {}
            for item in included:
                if item.get('type') == 'access-rule':
                    tier_id = item.get('attributes', {}).get('tier_id')
                    if tier_id:
                        for post in posts:
                            rules = post.get('relationships', {}).get('access_rules', {}).get('data', [])
                            for rule in rules:
                                if rule.get('id') == item.get('id'):
                                    if post['id'] not in post_tiers:
                                        post_tiers[post['id']] = []
                                    post_tiers[post['id']].append(str(tier_id))

            new_posts = []
            for post in posts:
                post_id = post['id']
                if post_id not in self.notified_ids:
                    tiers = post_tiers.get(post_id, [])
                    if self.target_tier_id in tiers:
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
