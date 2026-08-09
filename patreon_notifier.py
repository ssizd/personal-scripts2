#!/usr/bin/env python3
"""
Patreon Discord Notifier
Monitors Patreon for new posts with specific tier access and sends Discord notifications
"""

import requests
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Korea timezone (UTC+9)
KST = timezone(timedelta(hours=9))
DUPLICATE_WINDOW = timedelta(hours=3)

# Windows console encoding fix
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Load environment variables
load_dotenv()


class PatreonNotifier:
    def __init__(self):
        """Initialize Patreon notifier with API credentials"""
        self.webhook_gourmet = os.getenv('DISCORD_WEBHOOK_PATREON')
        self.webhook_public = os.getenv('DISCORD_WEBHOOK_PATREON_PUBLIC')
        self.webhook_vault = os.getenv('DISCORD_WEBHOOK_PATREON_VAULT')
        self.webhook_tier4 = os.getenv('DISCORD_WEBHOOK_PATREON_TIER4')
        self.access_token = os.getenv('PATREON_ACCESS_TOKEN')
        self.campaign_id = os.getenv('PATREON_CAMPAIGN_ID')
        self.target_tier_id = os.getenv('PATREON_TARGET_TIER_ID')
        self.lowest_tier_id = os.getenv('PATREON_LOWEST_TIER_ID')  # TASTER tier
        self.tier4_tier_id = os.getenv('PATREON_TIER4_TIER_ID')
        self.tier2_tier_id = os.getenv('PATREON_TIER2_TIER_ID')  # Big Eater tier

        # Notified IDs file
        self.notified_file = Path('patreon_notified_ids.json')
        self.recent_posts = {}
        self.notified_ids = self.load_notified_ids()

    def load_notified_ids(self):
        """Load already notified IDs"""
        self.is_first_run = False
        self.tier4_seeded = False
        if self.notified_file.exists():
            with open(self.notified_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not data.get('patreon'):
                    self.is_first_run = True
                self.tier4_seeded = data.get('tier4_seeded', False)
                self.recent_posts = data.get('recent_posts', {})
                return set(data.get('patreon', []))
        self.is_first_run = True
        return set()

    def save_notified_ids(self):
        """Save notified IDs"""
        with open(self.notified_file, 'w', encoding='utf-8') as f:
            json.dump({
                'patreon': sorted(self.notified_ids, key=int),
                'tier4_seeded': self.tier4_seeded,
                'recent_posts': self.recent_posts
            }, f, ensure_ascii=False, indent=2)

    def post_fingerprint(self, post):
        """Build a stable key that ignores Patreon's numeric post ID."""
        attributes = post.get('attributes', {})
        title = ' '.join(attributes.get('title', '').casefold().split())
        path = attributes.get('url', '').split('?', 1)[0].rstrip('/')
        path = re.sub(r'-?\d+$', '', path).rstrip('-')
        return f'{title}|{path}'

    def is_recent_duplicate(self, post, now):
        fingerprint = self.post_fingerprint(post)
        previous = self.recent_posts.get(fingerprint)
        if not previous:
            return False
        try:
            sent_at = datetime.fromisoformat(previous['sent_at'].replace('Z', '+00:00'))
        except (KeyError, TypeError, ValueError):
            return False
        return now - sent_at <= DUPLICATE_WINDOW

    def remember_post(self, post, now):
        fingerprint = self.post_fingerprint(post)
        self.recent_posts[fingerprint] = {
            'post_id': post['id'],
            'sent_at': now.isoformat().replace('+00:00', 'Z')
        }

        cutoff = now - DUPLICATE_WINDOW
        self.recent_posts = {
            key: value for key, value in self.recent_posts.items()
            if datetime.fromisoformat(value['sent_at'].replace('Z', '+00:00')) >= cutoff
        }

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

    def fetch_latest_posts(self):
        """Fetch latest posts by getting last page"""
        headers = {'Authorization': f'Bearer {self.access_token}'}

        # First get total count to find last page
        url = f'https://www.patreon.com/api/oauth2/v2/campaigns/{self.campaign_id}/posts'
        params = {
            'fields[post]': 'title,url,published_at,tiers',
            'page[count]': 100
        }

        # Keep fetching until we get to the last page
        all_posts = []
        cursor = None

        while True:
            if cursor:
                params['page[cursor]'] = cursor

            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()

            posts = data.get('data', [])
            all_posts = posts  # Only keep latest batch

            cursor = data.get('meta', {}).get('pagination', {}).get('cursors', {}).get('next')
            if not cursor or len(posts) == 0:
                break

        # Last page has newest posts, sort by ID descending
        all_posts.sort(key=lambda x: int(x['id']), reverse=True)
        return all_posts[:10]  # Return latest 10

    def check_new_posts(self):
        """Check for new Patreon posts with target tier access"""
        if not self.access_token or not self.campaign_id:
            print("⚠️ Patreon not configured, skipping...")
            return

        try:
            print("🔍 Checking Patreon for new posts...")

            posts = self.fetch_latest_posts()

            gourmet_posts = []
            vault_posts = []
            public_posts = []
            tier4_posts = []
            state_changed = False
            now = datetime.now(timezone.utc)

            for post in posts:
                post_id = post['id']
                if post_id not in self.notified_ids:
                    if self.is_recent_duplicate(post, now):
                        print(f"⏭️ Skipping recent duplicate with new ID: {post.get('attributes', {}).get('title', 'Untitled')}")
                        self.notified_ids.add(post_id)
                        state_changed = True
                        continue

                    # Skip scheduled posts (KST 20:00-21:00)
                    published_at = post.get('attributes', {}).get('published_at', '')
                    if published_at:
                        pub_time = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                        pub_kst = pub_time.astimezone(KST)
                        if pub_kst.hour == 20:
                            print(f"⏭️ Skipping scheduled post: {post.get('attributes', {}).get('title', 'Untitled')}")
                            self.notified_ids.add(post_id)  # Mark as seen so we don't check again
                            state_changed = True
                            continue

                    title = post.get('attributes', {}).get('title', '')
                    tiers = post.get('attributes', {}).get('tiers', [])

                    # tiers is cumulative (contains the selected tier and every tier above it),
                    # so exclude the tier right below each bucket to avoid catching lower-tier posts
                    is_tier2 = self.tier2_tier_id and int(self.tier2_tier_id) in tiers
                    is_gourmet = self.target_tier_id and int(self.target_tier_id) in tiers

                    # [Vault] posts → T2 channel only (not T3)
                    if '[Vault]' in title:
                        vault_posts.append(post)
                    # Check for Gourmet tier (T3+), excluding posts also visible to Big Eater (T2)
                    elif is_gourmet and not is_tier2:
                        gourmet_posts.append(post)
                    # Check for Tier4, excluding posts also visible to Gourmet (T3)
                    elif self.tier4_tier_id and int(self.tier4_tier_id) in tiers and not is_gourmet:
                        tier4_posts.append(post)
                    # Check for public/lowest tier (empty tiers = public, or lowest tier included)
                    elif len(tiers) == 0 or (self.lowest_tier_id and int(self.lowest_tier_id) in tiers):
                        public_posts.append(post)

            # Notify Gourmet tier posts
            if gourmet_posts and self.webhook_gourmet:
                print(f"🆕 Found {len(gourmet_posts)} new Gourmet tier post(s)")
                for i, post in enumerate(gourmet_posts):
                    post_id = post['id']
                    title = post.get('attributes', {}).get('title', 'Untitled')
                    post_url = f"https://www.patreon.com{post.get('attributes', {}).get('url', f'/posts/{post_id}')}"

                    if self.is_first_run:
                        self.notified_ids.add(post_id)
                        self.remember_post(post, now)
                        state_changed = True
                        print(f"📝 Saved (first run): {title}")
                    else:
                        if self.send_discord_notification(post_url, self.webhook_gourmet):
                            self.notified_ids.add(post_id)
                            self.remember_post(post, now)
                            state_changed = True
                            print(f"✅ Notified (Gourmet): {title}")
                        if i < len(gourmet_posts) - 1:
                            time.sleep(3)

            # Notify Vault posts (T2 channel)
            if vault_posts and self.webhook_vault:
                print(f"🆕 Found {len(vault_posts)} new Vault post(s)")
                for i, post in enumerate(vault_posts):
                    post_id = post['id']
                    title = post.get('attributes', {}).get('title', 'Untitled')
                    post_url = f"https://www.patreon.com{post.get('attributes', {}).get('url', f'/posts/{post_id}')}"

                    if self.is_first_run:
                        self.notified_ids.add(post_id)
                        self.remember_post(post, now)
                        state_changed = True
                        print(f"📝 Saved (first run): {title}")
                    else:
                        if self.send_discord_notification(post_url, self.webhook_vault):
                            self.notified_ids.add(post_id)
                            self.remember_post(post, now)
                            state_changed = True
                            print(f"✅ Notified (Vault/T2): {title}")
                        if i < len(vault_posts) - 1:
                            time.sleep(3)

            # Notify Tier4 posts (skip backfill: first time tier4 is seen, just seed IDs silently)
            if tier4_posts and self.webhook_tier4:
                tier4_first_run = self.is_first_run or not self.tier4_seeded
                print(f"🆕 Found {len(tier4_posts)} new Tier4 post(s)")
                for i, post in enumerate(tier4_posts):
                    post_id = post['id']
                    title = post.get('attributes', {}).get('title', 'Untitled')
                    post_url = f"https://www.patreon.com{post.get('attributes', {}).get('url', f'/posts/{post_id}')}"

                    if tier4_first_run:
                        self.notified_ids.add(post_id)
                        self.remember_post(post, now)
                        state_changed = True
                        print(f"📝 Saved (no backfill): {title}")
                    else:
                        if self.send_discord_notification(post_url, self.webhook_tier4):
                            self.notified_ids.add(post_id)
                            self.remember_post(post, now)
                            state_changed = True
                            print(f"✅ Notified (Tier4): {title}")
                        if i < len(tier4_posts) - 1:
                            time.sleep(3)
                self.tier4_seeded = True

            # Notify public/lowest tier posts
            if public_posts and self.webhook_public:
                print(f"🆕 Found {len(public_posts)} new public/lowest tier post(s)")
                for i, post in enumerate(public_posts):
                    post_id = post['id']
                    title = post.get('attributes', {}).get('title', 'Untitled')
                    post_url = f"https://www.patreon.com{post.get('attributes', {}).get('url', f'/posts/{post_id}')}"

                    if self.is_first_run:
                        self.notified_ids.add(post_id)
                        self.remember_post(post, now)
                        state_changed = True
                        print(f"📝 Saved (first run): {title}")
                    else:
                        if self.send_discord_notification(post_url, self.webhook_public):
                            self.notified_ids.add(post_id)
                            self.remember_post(post, now)
                            state_changed = True
                            print(f"✅ Notified (Public): {title}")
                        if i < len(public_posts) - 1:
                            time.sleep(3)

            if state_changed:
                self.save_notified_ids()
            else:
                print("✅ No new Patreon posts")

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
