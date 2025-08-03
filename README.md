
# Sir Tim the Timely

A Discord bot to help MIT first-year students keep track of important deadlines and orientation tasks.

## Features

- **Automatic Deadline Updates:** Scrapes deadlines from MIT’s official First Year website.
- **Reminders:** Sends reminders 24 hours and 6 hours before deadlines, plus a weekly digest.
- **Role Pinging:** You can set a role to be pinged for reminders.
- **Natural Language Search:** Ask questions like “When is the housing application due?” or “What’s due this week?”
- **Admin Tools:** Add, remove, or list roles that can use admin commands, set reminder channels, and manually trigger scraping.

## Setup

1. **Requirements:** Python 3.9+, Discord bot token, (optional) Google AI Studio API key for chat features.
2. **Install:**
  ```bash
  git clone <repository-url>
  cd "Sir Tim the Timely"
  pip install -r requirements.txt
  ```
3. **Configure:**
  - Copy `.env.example` to `.env` and add your Discord bot token.
4. **Run:**
  ```bash
  python setup_database.py
  python main.py
  ```
5. **Discord Setup:**
  - Use `/admin reminderchannel` to set the reminder channel.
  - Use `/admin setrole @YourRole` to set the ping role.
  - Use `/admin testdigest` to test the weekly digest.

## Target Users

- MIT first-year students
- Families and orientation coordinators
- Anyone at MIT who wants deadline reminders

## Data Sources

- [MIT First Year Deadlines](https://firstyear.mit.edu/orientation/countdown-to-campus-before-you-arrive/critical-summer-actions-and-deadlines/)
- Manual entry for backup

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License. See [LICENSE](LICENSE).

## Support

- Discord: [Support server link]
- Email: tim-support@mit.edu
- GitHub Issues

---

*"Punctuality is the politeness of princes and the duty of students."* - Sir Tim the Timely
- **Announcement System**: Broadcast important updates to all servers
