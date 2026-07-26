#!/usr/bin/env python3
"""One-off diagnostic: print recent posts' title + tiers array so we can see
whether the Patreon API's `tiers` field is cumulative (includes every tier
that can access the post) or just the single selected tier."""

import os
import requests

access_token = os.getenv('PATREON_ACCESS_TOKEN')
campaign_id = os.getenv('PATREON_CAMPAIGN_ID')

if not access_token or not campaign_id:
    raise SystemExit("PATREON_ACCESS_TOKEN / PATREON_CAMPAIGN_ID not set")

headers = {'Authorization': f'Bearer {access_token}'}
url = f'https://www.patreon.com/api/oauth2/v2/campaigns/{campaign_id}/posts'
params = {
    'fields[post]': 'title,url,published_at,tiers',
    'page[count]': 25,
    'sort': '-published_at'
}

response = requests.get(url, headers=headers, params=params)
response.raise_for_status()
data = response.json()

posts = data.get('data', [])
posts.sort(key=lambda x: int(x['id']), reverse=True)

for post in posts[:25]:
    attrs = post.get('attributes', {})
    title = attrs.get('title', 'Untitled')
    tiers = attrs.get('tiers', [])
    print(f"{post['id']}\t{tiers}\t{title}")
