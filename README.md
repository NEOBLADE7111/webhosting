# 👑 NAGI x HOSTING x BOT (God-Level Edition)

Welcome to the most powerful and professional Telegram Hosting Bot. This platform allows users to host their Python and Node.js projects with one click, while giving Admins absolute "God-Level" control over the entire system.

---

## 🚀 Key Features

### 💎 For Users:
*   **🚀 One-Click Deploy**: Upload `.py`, `.js`, or `.zip` files and the bot handles the rest.
*   **🐙 GitHub Cloning**: Instant deployment from public/private repositories.
*   **🖥 Web Editor**: A full browser-based IDE to edit files, manage Envs, and view logs.
*   **📸 Snapshots**: One-click code backups and rollbacks.
*   **💳 Wallet & Referrals**: Earn credits via referrals to upgrade hosting plans.
*   **📖 Help Center**: Built-in guide for new users.

### 🛡️ For Admins (God Mode):
*   **📂 Global Oversight**: View and manage EVERY project running on the server.
*   **🛡 NAGI Shield**: Manage a global blacklist of dangerous code patterns (rm -rf, etc.).
*   **📢 Channel Manager**: Dynnamic Force Subscription system (Add/Edit/Delete channels).
*   **🎁 Gift Factory**: Generate bulk PRO/VIP gift codes for users.
*   **📊 Revenue Dashboard**: Track total users, VIPs, and system performance.
*   **🕵️ User Peek**: Access any user's project console for support.

---

## 🛠 System Requirements
*   **Python**: 3.10 or 3.11 (Recommended)
*   **Memory**: 1GB RAM minimum (2GB+ Recommended for serious hosting)
*   **OS**: Ubuntu 20.04/22.04 (VPS) or Windows 10/11 (Local)
*   **NGROK**: Required for the Web Editor access.

---

## 💻 How to Host (Local PC)

1.  **Install Python**: Download from [python.org](https://python.org).
2.  **Clone Source**: Download and extract the source folder.
3.  **Install Requirements**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Configure `.env`**: Create a `.env` file and fill in your details:
    ```env
    BOT_TOKEN=your_telegram_bot_token
    ADMIN_ID=your_id
    NGROK_AUTH=your_ngrok_authtoken
    GEMINI_API_KEY=your_gemini_key
    LOG_CHANNEL_ID=your_private_channel_id
    WEB_URL=http://localhost:8000
    ```
5.  **Run the Bot**:
    ```bash
    python main.py
    ```

---

## 🌐 How to Host (VPS - Ubuntu)

Hosting on a VPS ensures your bot stays online 24/7. Follow these exact steps:

### 1️⃣ Prepare the VPS
Connect to your VPS via SSH and run:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv screen -y
```

### 2️⃣ Clone & Setup
```bash
git clone <your_repo_link> god_host
cd god_host
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3️⃣ Configure Environment
Edit the `.env` file using `nano`:
```bash
nano .env
```
Paste your configuration (similar to Local setup). **Note:** Set `WEB_URL` to your VPS IP, e.g., `http://123.45.67.89:8000`.

### 4️⃣ Run in Background
Use `screen` to keep the bot running after you close the terminal:
```bash
screen -S hostingbot
source venv/bin/activate
python3 main.py
```
*   **To Exit Screen**: Press `CTRL + A` then `D`.
*   **To Re-enter Screen**: Type `screen -r hostingbot`.

---

## ⚙️ Environment Variables Explained

| Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Your Bot Token from @BotFather. |
| `ADMIN_ID` | Your numeric Telegram ID (use @userinfobot). |
| `NGROK_AUTH` | Authtoken from your ngrok.com dashboard. |
| `GEMINI_API_KEY` | API Key from Google AI Studio (for source analysis). |
| `LOG_CHANNEL_ID` | Private channel ID (must start with -100). |
| `WEB_URL` | The URL where the Web Editor will be accessible. |

---

## 📜 Support
Created by **Elite Developers** for the **God-Level Hosting** community.
Join: [@AbdulBotzOfficial](https://t.me/AbdulBotzOfficial)
👑 **Designed for Ultimate Control.**
