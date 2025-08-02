# Simple Setup Guide for Sir Tim the Timely

This bot is designed to be **simple and easy to use**. Here's everything you need to know:

## 🚀 Quick Setup (5 minutes)

### 1. Install and Run
```bash
git clone <repository-url>
cd "Sir Tim the Timely"
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Discord bot token
python setup_database.py
python main.py
```

### 2. Configure in Discord
1. **Set reminder channel**: `/admin reminderchannel` (run this in the channel where you want reminders)
2. **Set role to ping**: `/admin setrole @YourRole` (optional - role that gets pinged for reminders)
3. **Test it works**: `/admin testdigest` to see a sample weekly digest

## 📋 What the Bot Does

### Automatic Reminders
- **24 hours before deadlines**: Gets your attention
- **6 hours before deadlines**: Final warning
- **Weekly digest (Sunday 9 AM)**: Summary of upcoming week + funny motivational quote

### Simple Commands
- `/tim` - See upcoming deadlines
- `/tim housing deadlines` - Search for specific deadlines
- `/urgent` - See what's due in next 3 days

### Chat Features
- Just mention the bot or ask about deadlines in chat
- It understands natural language and responds helpfully

## 🔧 Admin Commands

- `/admin reminderchannel` - Set where reminders go
- `/admin setrole @role` - Set role to ping for reminders
- `/admin testreminder` - Test reminder system
- `/admin testdigest` - Test weekly digest
- `/admin status` - Check bot status

## 🎯 Environment Variables

Only **required** setting:
```
TOKEN=your_discord_bot_token
```

**Optional** settings:
```
GEMINI_API_KEY=your_api_key          # For AI chat features
REMINDER_ROLE_ID=role_id             # Role to ping (can set via command)
WEEKLY_DIGEST_TIME=09:00             # When to send Sunday digest
DEFAULT_TIMEZONE=US/Eastern          # Timezone for deadlines
```

## 🎉 That's It!

The bot will:
- ✅ Automatically scrape MIT deadlines
- ✅ Send 24hr and 6hr reminders
- ✅ Send weekly digest every Sunday morning
- ✅ Respond to chat questions about deadlines
- ✅ Keep everything simple and easy to use

No complex configuration needed - it just works!