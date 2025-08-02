# Sir Tim the Timely - MIT Deadline Discord Bot

A sophisticated Discord bot built with Hikari and Hikari-Arc that helps MIT first-year students stay on top of critical summer deadlines and orientation tasks.

## 🚀 Features

### 📅 Simple Deadline Management
- **Automatic Deadline Scraping**: Fetches and updates deadlines from MIT's official First Year website
- **AI-Enhanced Chat**: Natural language queries about deadlines using Gemini AI
- **Smart Deadline Display**: Clean, easy-to-read deadline information

### 🔔 Simple Reminders
- **24-Hour Reminders**: Get notified 24 hours before deadlines
- **6-Hour Reminders**: Final reminder 6 hours before deadlines  
- **Weekly Digest**: Sunday morning summary with a funny motivational quote
- **Role Pinging**: Configure a role to be pinged for all reminders

### 🤖 AI-Powered Natural Language Interface (Gemini 2.0 Flash Lite)
- **Natural Language Queries**: Ask questions like "When is the housing application due?" or "What do I need to do before July?"
- **Deadline Discovery**: "What deadlines are coming up this week?"
- **Contextual Help**: AI understands MIT-specific terminology and provides relevant guidance
- **Smart Summarization**: Get concise summaries of complex deadline requirements
- **Ultra-Concise Title Enhancement**: Batch processes all deadline titles in a single API call for maximum efficiency

### 💬 Simple Commands

#### Main Commands
- `/tim [query]` - Main command for all deadline interactions
  - No query: Shows upcoming deadlines
  - With query: Natural language search (e.g., "housing deadlines", "what's due this week?")
- `/urgent` - Show urgent deadlines (next 3 days)
- `/setup` - One-click setup with smart defaults

#### Chat Functionality
- **Natural Language Chat**: Just mention the bot or ask about deadlines in any channel where it's enabled
- **Smart Responses**: The bot understands context and provides helpful deadline information

#### Admin Commands (Server Administrators Only)
- `/admin reminderchannel` - Set the current channel for reminders and weekly digest
- `/admin setrole <role>` - Set the role to ping for reminders and digest
- `/admin testreminder` - Test the reminder system in current channel
- `/admin testdigest` - Test the weekly digest in current channel
- `/admin scrape` - Manually trigger deadline scraping from MIT website
- `/admin status` - Show bot status and statistics

### 📊 Dashboard & Analytics
- **Progress Tracking**: Visual progress bars for multi-step deadlines
- **Statistics**: Server-wide deadline statistics (anonymized)
- **Export Options**: Export personal deadline calendar to Google Calendar/iCal

### 🏫 MIT-Specific Features
- **FPOP Integration**: Special handling for Pre-Orientation Program deadlines
- **International Student Support**: Highlighted deadlines specific to international students
- **Transfer Credit Deadlines**: Special alerts for AP/IB/Transfer credit deadlines
- **Advanced Standing Exam Schedule**: Dedicated commands for ASE information
- **Emergency Contact Reminders**: Special handling for critical safety-related deadlines

### 🔧 Administrative Features
- **Deadline Override**: Admins can manually add/edit deadline information
- **Smart Duplicate Detection**: Automatically identifies and prevents recurring deadline duplicates
- **Database Cleanup**: Remove old deadlines and merge duplicates with admin commands
- **Email Formatting**: Automatically formats email addresses in descriptions with backticks and fixes spacing
- **Announcement System**: Broadcast important updates to all servers
- **Usage Analytics**: Track which deadlines are most queried
- **Error Monitoring**: Automatic alerts when website scraping fails

## 🛠 Technical Stack

- **Bot Framework**: Hikari (2.3.3+) with Hikari-Arc command handler
- **AI Integration**: 
  - Google AI Studio API (Gemini 2.0 Flash Lite) for deadline enhancements and natural language processing
- **Database**: SQLite with async support (aiosqlite)
- **Web Scraping**: aiohttp + BeautifulSoup4 for MIT website parsing
- **Task Scheduling**: Built-in Hikari-Arc loops for periodic tasks
- **Configuration**: python-dotenv for environment management

## 📋 Simple Setup

### What You Need
- Python 3.9+
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Google AI Studio API Key (optional, for chat features)

### 5-Minute Setup

1. **Install**
```bash
git clone <repository-url>
cd "Sir Tim the Timely"
pip install -r requirements.txt
```

2. **Configure**
```bash
cp .env.example .env
# Edit .env and add your Discord bot token:
# TOKEN=your_discord_bot_token_here
```

3. **Run**
```bash
python setup_database.py
python main.py
```

4. **Setup in Discord**
```
/admin reminderchannel    # Set reminder channel
/admin setrole @YourRole  # Set role to ping (optional)
/admin testdigest         # Test it works
```

**That's it!** See [SIMPLE_SETUP.md](SIMPLE_SETUP.md) for detailed guide.

## 🎯 Target Users

- **Primary**: MIT Class of 2029 first-year students
- **Secondary**: MIT families and orientation coordinators
- **Tertiary**: Other MIT community members tracking deadlines

## 🔄 Data Sources

- **Primary**: https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/
- **Backup**: Manual deadline entry system
- **Updates**: Automatic checks every 6 hours with intelligent duplicate prevention
- **Enhancement**: AI-powered batch title optimization creating 50-character action-oriented phrases (single API call per scrape)

## 📈 Roadmap

### Phase 1 (Current)
- ✅ Basic deadline scraping and storage
- ✅ Core slash commands
- ✅ AI-powered natural language queries
- ✅ Daily reminder system

### Phase 2 (Planned)
- [ ] Multi-server support with server-specific configurations
- [ ] Advanced analytics and reporting
- [ ] Machine learning for deadline importance prediction

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
pip install -r requirements-dev.txt
pre-commit install
```

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Discord**: Join our support server [link]
- **Email**: tim-support@mit.edu
- **Issues**: GitHub Issues for bug reports and feature requests

## 🙏 Acknowledgments

- MIT Office of the First Year for providing comprehensive deadline information
- Hikari and Hikari-Arc developers for excellent Discord bot frameworks
- Google AI Studio team for powerful natural language processing capabilities

---

*"Punctuality is the politeness of princes and the duty of students."* - Sir Tim the Timely
