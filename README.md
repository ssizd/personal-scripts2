# Pixiv & X Discord Notifier

Monitors Pixiv and X accounts for new posts and sends notifications to Discord.

## Features

- Monitors Pixiv account for new artworks
- Monitors X (Twitter) account for new tweets
- Sends link-only notifications to Discord
- Runs every 3 minutes via GitHub Actions
- Prevents duplicate notifications

## Setup

### 1. Create Discord Webhook

1. Go to your Discord server settings
2. Navigate to Integrations → Webhooks
3. Click "New Webhook"
4. Copy the webhook URL

### 2. Get API Credentials

#### Pixiv:
```bash
# Use the token from your previous setup
PIXIV_USER_ID=your_user_id
PIXIV_REFRESH_TOKEN=your_refresh_token
```

#### X (Twitter):
- Use the same API credentials from your Pixiv to X bot

### 3. GitHub Repository Setup

1. Create a new public repository on GitHub
2. Push this code to the repository
3. Go to Repository → Settings → Secrets and variables → Actions
4. Add the following secrets:

   - `DISCORD_WEBHOOK_URL` - Your Discord webhook URL
   - `PIXIV_USER_ID` - Pixiv user ID to monitor
   - `PIXIV_REFRESH_TOKEN` - Pixiv refresh token
   - `TWITTER_API_KEY` - X API key
   - `TWITTER_API_SECRET` - X API secret
   - `TWITTER_ACCESS_TOKEN` - X access token
   - `TWITTER_ACCESS_TOKEN_SECRET` - X access token secret
   - `TWITTER_BEARER_TOKEN` - X bearer token
   - `TWITTER_USERNAME` - X username to monitor (without @)

5. Go to Settings → Actions → General
6. Under "Workflow permissions", select "Read and write permissions"

### 4. Enable GitHub Actions

Go to the Actions tab and enable the workflow.

## How It Works

1. Every 3 minutes, GitHub Actions runs the script
2. Checks Pixiv for new artworks (latest 5)
3. Checks X for new tweets (latest 5, excluding retweets/replies)
4. Sends Discord notifications for new posts (link only)
5. Saves notified IDs to prevent duplicates

## Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your credentials

# Run the notifier
python discord_notifier.py
```

## Notification Format

**Pixiv:**
```
**New Pixiv Post**
https://www.pixiv.net/artworks/[ID]
```

**X:**
```
**New X Post**
https://twitter.com/[username]/status/[ID]
```

## Changing Check Frequency

Edit `.github/workflows/notify.yml`:

```yaml
# Every 5 minutes
- cron: '*/5 * * * *'

# Every 10 minutes
- cron: '*/10 * * * *'

# Every 15 minutes
- cron: '*/15 * * * *'
```

Note: GitHub Actions cron has a minimum interval of 1 minute, but may have delays during high-traffic periods.

## License

MIT License
