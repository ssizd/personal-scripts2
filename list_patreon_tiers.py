#!/usr/bin/env python3
"""One-off helper: print this campaign's tiers (id, title, price) so you can
identify the numeric tier ID to put in PATREON_TIER4_TIER_ID etc.
Not used by the notifier itself."""

import os
import requests

access_token = os.getenv('PATREON_ACCESS_TOKEN')
campaign_id = os.getenv('PATREON_CAMPAIGN_ID')

if not access_token or not campaign_id:
    raise SystemExit("PATREON_ACCESS_TOKEN / PATREON_CAMPAIGN_ID not set")

url = f'https://www.patreon.com/api/oauth2/v2/campaigns/{campaign_id}'
params = {
    'include': 'tiers',
    'fields[tier]': 'title,amount_cents,published'
}
headers = {'Authorization': f'Bearer {access_token}'}

response = requests.get(url, headers=headers, params=params)
response.raise_for_status()
data = response.json()

tiers = [item for item in data.get('included', []) if item.get('type') == 'tier']
if not tiers:
    print("No tiers found in response.")
else:
    print(f"{'ID':<15} {'Price':<10} {'Title'}")
    print("-" * 50)
    for tier in tiers:
        attrs = tier.get('attributes', {})
        price = attrs.get('amount_cents')
        price_str = f"${price / 100:.2f}" if price is not None else "?"
        print(f"{tier['id']:<15} {price_str:<10} {attrs.get('title', '(untitled)')}")
