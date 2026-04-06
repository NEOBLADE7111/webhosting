#!/bin/bash

echo "🚀 Starting God-Level Hosting Bot VPS Setup..."

# 1. Update System
echo "🔄 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# 2. Install Dependencies
echo "📦 Installing Python, Venv, and Screen..."
sudo apt install python3-pip python3-venv screen -y

# 3. Create Virtual Environment
echo "🐍 Setting up Python Virtual Environment..."
python3 -m venv venv
source venv/bin/activate

# 4. Install Requirements
echo "📥 Installing Bot Requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# 5. Reminder
echo "------------------------------------------------"
echo "✅ SETUP COMPLETE!"
echo "------------------------------------------------"
echo "👉 NEXT STEPS:"
echo "1. Edit your .env file: nano .env"
echo "2. Run the bot in background: screen -S hostingbot"
echo "3. Start the bot: source venv/bin/activate && python3 main.py"
echo "------------------------------------------------"
