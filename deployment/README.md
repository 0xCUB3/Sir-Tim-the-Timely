# Raspberry Pi Deployment Guide for Sir Tim the Timely

This guide will help you set up continuous deployment from GitHub to your Raspberry Pi.

## Prerequisites

- Raspberry Pi with Raspberry Pi OS
- SSH access to your Pi
- GitHub repository with Sir Tim the Timely code

## Step 1: Initial Raspberry Pi Setup

### 1.1 Run the Setup Script

```bash
# On your Raspberry Pi, download and run the setup script
curl -sSL https://raw.githubusercontent.com/0xCUB3/Sir-Tim-the-Timely/main/deployment/setup_pi.sh | bash
```

Or manually:

```bash
# Clone the repository
git clone https://github.com/0xCUB3/Sir-Tim-the-Timely.git
cd Sir-Tim-the-Timely

# Make setup script executable and run it
chmod +x deployment/setup_pi.sh
./deployment/setup_pi.sh
```

### 1.2 Configure Environment Variables

Edit the `.env` file with your actual tokens:

```bash
nano /home/pi/Sir-Tim-the-Timely/.env
```

Add your Discord bot token and Gemini API key:
```
TOKEN=your_actual_discord_token
GEMINI_API_KEY=your_actual_gemini_api_key
```

### 1.3 Test the Bot

```bash
# Start the bot manually first to test
cd /home/pi/Sir-Tim-the-Timely
source venv/bin/activate
python main.py
```

If everything works, stop it with `Ctrl+C` and proceed to the service setup.

## Step 2: Set Up Systemd Service

### 2.1 Start the Service

```bash
systemctl --user start sir-tim-bot
systemctl --user enable sir-tim-bot
```

### 2.2 Check Service Status

```bash
systemctl --user status sir-tim-bot
```

### 2.3 View Logs

```bash
journalctl --user -u sir-tim-bot -f
```

## Step 3: Set Up SSH for GitHub Actions

### 3.1 Generate SSH Key (if you don't have one)

```bash
# On your Raspberry Pi
ssh-keygen -t rsa -b 4096 -C "github-actions@yourpi"
```

### 3.2 Add Public Key to Authorized Keys

```bash
cat ~/.ssh/id_rsa.pub >> ~/.ssh/authorized_keys
```

### 3.3 Get the Private Key

```bash
cat ~/.ssh/id_rsa
```

Copy this entire private key (including `-----BEGIN` and `-----END` lines).

## Step 4: Configure GitHub Secrets

Go to your GitHub repository → Settings → Secrets and variables → Actions

Add these secrets:

| Secret Name | Description | Example Value |
|-------------|-------------|---------------|
| `PI_HOST` | Your Pi's IP address or hostname | `192.168.1.100` or `mypi.local` |
| `PI_USERNAME` | SSH username (usually 'pi') | `pi` |
| `PI_SSH_KEY` | Private SSH key from Step 3.3 | `-----BEGIN RSA PRIVATE KEY-----\n...` |
| `PI_PORT` | SSH port (optional, defaults to 22) | `22` |
| `PI_BOT_PATH` | Path to bot directory on Pi | `/home/pi/Sir-Tim-the-Timely` |

## Step 5: Test Deployment

### 5.1 Make a Test Commit

```bash
# Make a small change and push
echo "# Test deployment" >> README.md
git add README.md
git commit -m "Test: Trigger deployment"
git push origin main
```

### 5.2 Monitor GitHub Actions

1. Go to your GitHub repository
2. Click on the "Actions" tab
3. Watch the deployment workflow run

### 5.3 Check Deployment on Pi

```bash
# Check if the bot restarted
systemctl --user status sir-tim-bot

# View recent logs
journalctl --user -u sir-tim-bot --since "5 minutes ago"
```

## Troubleshooting

### Common Issues

#### 1. SSH Connection Failed
- Check that your Pi is accessible: `ssh pi@your-pi-ip`
- Verify the IP address in GitHub secrets
- Ensure SSH key is correct

#### 2. Service Won't Start
```bash
# Check service logs
journalctl --user -u sir-tim-bot -n 50

# Check if dependencies are installed
cd /home/pi/Sir-Tim-the-Timely
source venv/bin/activate
pip list
```

#### 3. Database Issues
```bash
# Check database permissions
ls -la /home/pi/Sir-Tim-the-Timely/data/

# Recreate database if needed
rm /home/pi/Sir-Tim-the-Timely/data/deadlines.db
systemctl --user restart sir-tim-bot
```

#### 4. Environment Variables Not Loading
```bash
# Check .env file
cat /home/pi/Sir-Tim-the-Timely/.env

# Update systemd service if needed
systemctl --user daemon-reload
systemctl --user restart sir-tim-bot
```

### Manual Commands

```bash
# Start bot
systemctl --user start sir-tim-bot

# Stop bot
systemctl --user stop sir-tim-bot

# Restart bot
systemctl --user restart sir-tim-bot

# View logs (live)
journalctl --user -u sir-tim-bot -f

# View recent logs
journalctl --user -u sir-tim-bot --since "1 hour ago"

# Check bot status
systemctl --user status sir-tim-bot

# Reload systemd config
systemctl --user daemon-reload
```

### Updating Dependencies

If you add new Python packages:

```bash
cd /home/pi/Sir-Tim-the-Timely
source venv/bin/activate
pip install -r requirements.txt
systemctl --user restart sir-tim-bot
```

## Workflow Explanation

The GitHub Actions workflow does the following:

1. **Test Job**: Runs on every push/PR
   - Checks Python syntax
   - Tests database initialization
   - Validates dependencies

2. **Deploy Job**: Runs only on main branch pushes
   - Connects to Pi via SSH
   - Stops the bot service
   - Backs up current version
   - Pulls latest code
   - Installs dependencies
   - Restarts the service
   - Verifies deployment success

## Security Considerations

- SSH keys should be kept secure
- Consider using a dedicated SSH user for deployments
- Regularly update your Raspberry Pi OS
- Monitor deployment logs for any issues

## Customization

You can modify the deployment workflow by editing `.github/workflows/deploy.yml` to:
- Change deployment conditions
- Add additional testing steps
- Customize the deployment script
- Add notifications on deployment success/failure

Happy deploying! 🤖🚀
