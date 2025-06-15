# Sir Tim the Timely - MIT Deadline Discord Bot

A sophisticated Discord bot built with Hikari and Hikari-Arc that helps MIT first-year students stay on top of critical summer deadlines and orientation tasks.

## 🚀 Features

### 📅 Deadline Management
- **Automatic Deadline Scraping**: Periodically fetches and updates deadlines from MIT's official First Year website
- **AI-Enhanced Title Generation**: Uses Gemini 2.0 Flash Lite with efficient batch processing to create ultra-concise, action-oriented deadline titles
- **Smart Deadline Parsing**: Extracts dates, descriptions, and links from the MIT deadlines page
- **Deadline Categories**: Organizes deadlines by type (Medical, Academic, Housing, Financial, etc.)
- **Time Zone Support**: All deadlines displayed in EDT/EST with user timezone conversion

### 🔔 Intelligent Reminders
- **Automated Daily Reminders**: Daily digest of upcoming deadlines (configurable times)
- **Urgency-Based Notifications**: Different reminder frequencies based on deadline proximity
  - 2 weeks before: Weekly reminders
  - 1 week before: Every 2 days
  - 3 days before: Daily reminders
  - 1 day before: Multiple reminders
- **Personalized Reminders**: Users can set custom reminders for specific deadlines
- **Smart Filtering**: Only reminds about relevant deadlines (e.g., no FPOP reminders if not applicable)

### 🤖 AI-Powered Natural Language Interface (Gemini 2.0 Flash Lite)
- **Natural Language Queries**: Ask questions like "When is the housing application due?" or "What do I need to do before July?"
- **Deadline Discovery**: "What deadlines are coming up this week?"
- **Contextual Help**: AI understands MIT-specific terminology and provides relevant guidance
- **Smart Summarization**: Get concise summaries of complex deadline requirements
- **Ultra-Concise Title Enhancement**: Batch processes all deadline titles in a single API call for maximum efficiency

### 💬 Interactive Commands

#### Slash Commands
- `/deadlines list [category] [month]` - List all or filtered deadlines
- `/deadlines search <query>` - Search deadlines with natural language
- `/deadlines next [days]` - Show deadlines in the next X days (default: 7)
- `/deadlines remind <deadline_id> <time>` - Set personal reminder
- `/deadlines help` - Show detailed help and FAQ

#### Utility Commands
- `/timezone set <timezone>` - Set your timezone for accurate deadline times
- `/preferences` - Manage notification preferences
- `/status` - Show bot status and last data update
- `/feedback <message>` - Send feedback to bot developers

#### Admin Commands (Server Administrators Only)
- `/admin scrape` - Manually trigger deadline scraping from MIT website
- `/admin cleanup` - Clean up old deadlines and find potential duplicates
- `/admin mergedeadlines <keep_id> <remove_id>` - Merge duplicate deadlines
- `/admin adddeadline` - Add a custom deadline to the database
- `/admin reminderchannel` - Set the current channel for daily reminders
- `/admin status` - Show detailed bot status and statistics

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
- **Announcement System**: Broadcast important updates to all servers
- **Usage Analytics**: Track which deadlines are most queried
- **Error Monitoring**: Automatic alerts when website scraping fails

## 🛠 Technical Stack

- **Bot Framework**: Hikari (2.3.3+) with Hikari-Arc command handler
- **AI Integration**: Google AI Studio API (Gemini 2.0 Flash Lite)
- **Database**: SQLite with async support (aiosqlite)
- **Web Scraping**: aiohttp + BeautifulSoup4 for MIT website parsing
- **Task Scheduling**: Built-in Hikari-Arc loops for periodic tasks
- **Configuration**: python-dotenv for environment management

## 📋 Installation & Setup

### Prerequisites
- Python 3.9+
- Discord Bot Token with appropriate permissions
- Google AI Studio API Key

### Required Discord Permissions
- `bot` (Essential for bot functionality)
- `applications.commands` (Required for slash commands)
- `guilds` (Read server information)
- `guilds.members.read` (Read member information for personalization)
- `messages.read` (Read messages in channels)

### Installation Steps

1. **Clone and Install Dependencies**
```bash
git clone <repository-url>
cd "Sir Tim the Timely"
pip install -r requirements.txt
```

2. **Environment Configuration**
```bash
cp .env.example .env
# Edit .env with your tokens:
# TOKEN=your_discord_bot_token
# GEMINI_API_KEY=your_google_ai_studio_api_key
```

3. **Database Setup**
```bash
python setup_database.py
```

4. **Run the Bot**
```bash
python main.py
```

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
