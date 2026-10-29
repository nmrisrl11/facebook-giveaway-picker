# 🎁 Facebook Group Giveaway Winner Picker

[![Developer: Nomer Israel](https://img.shields.io/badge/Developer-Nomer%20Israel-blue?logo=github)](https://github.com/nmrisrl11)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-orange?logo=buy-me-a-coffee)](https://buymeacoffee.com/nmrisrl11)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

An automated, fair, and reliable Python tool to pick giveaway winners from Facebook group posts—including **private groups**—by attaching directly to your active browser session via the **Chrome DevTools Protocol (CDP)**.

---

## 🌟 Why This Exists & How It Works

Scraping Facebook posts—especially inside private groups—is usually blocked by login walls, 2FA, and bot detection. Traditional web scrapers that ask for your password often trigger Facebook security checkpoints or account bans.

**This tool takes a different, secure approach:**
Instead of logging in headlessly, it connects to your **already open and logged-in Brave/Chrome browser** via Chrome DevTools Protocol (CDP).
- **Zero Credentials Needed**: Uses your active session and permissions safely.
- **Private Groups Supported**: Accesses any group your Facebook account is already a member of.
- **Modal Infinite-Scroll Engine**: Automatically locates internal scrollable post containers and continuously scrolls to load hundreds of comments.
- **Virtualization Protection**: Accumulates and saves comments in real-time as they appear so no entries are lost when Facebook unmounts off-screen comments.

---

## 📋 Giveaway Rules Enforced

1. **Number Range Filter**: Prompts for minimum and maximum integers (e.g., `1` to `300`). Any comment without a number in this range is automatically disqualified.
2. **1 Entry per Member**: If a member posts multiple comments, only their **first** valid comment is counted. All subsequent entries from that member are rejected.
3. **First-Come, First-Served on Duplicate Numbers**: If two or more members pick the exact same number, the member who commented first claims the number; subsequent members with that number are disqualified.
4. **Cryptographically Fair Draw**: Uses Python’s `secrets.SystemRandom` to randomly select the requested number of winners from the qualifying pool.
5. **Clean, Safe Output**: Formats the announcement without prohibited words like *"giveaway"* to prevent group moderation filters from flagging your post.
6. **Detailed Audit Logging**: Automatically saves a timestamped report in the `results/` folder documenting all eligible entries, disqualified comments with specific reasons, and selected winners.

---

## 🛠️ Prerequisites

- **OS**: Windows 10 / 11
- **Python**: 3.10 or newer
- **Browser**: [Brave Browser](https://brave.com/), [Google Chrome](https://www.google.com/chrome/), or [Microsoft Edge](https://www.microsoft.com/edge)
- **Git**: Installed for version control

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/nmrisrl11/facebook-giveaway-picker.git
cd facebook-giveaway-picker
```

### 2. Set Up Virtual Environment & Dependencies
```powershell
# Create virtual environment
python -m venv .venv

# Activate and install requirements
.venv\Scripts\pip install -r requirements.txt
```

---

## 🎮 How to Run

### Method A: 1-Click Automated Runner (Zero Setup!)

Simply double-click **`run_picker.bat`**.

The script will:
1. Check if your browser is already active on debug port `9222`.
2. If not, auto-detect your installed browsers (**Brave**, **Google Chrome**, **Microsoft Edge**) and ask which one has your active Facebook login.
3. Automatically launch (or restart) the browser with remote debugging enabled.
4. Prompt you for the giveaway details and pick your winners automatically!

---

### Method B: Manual Browser Launch (Optional Utility)

If you prefer to start your browser in debug mode first:
- Double-click **`start_browser_debug.bat`** (select Brave, Chrome, or Edge).
- Then run **`run_picker.bat`** (or `.venv\Scripts\python giveaway_picker.py`).

---

## 📥 Interactive Inputs

When prompted, provide:
- **Facebook giveaway link**: `https://www.facebook.com/groups/<group_id>/posts/<post_id>/`
- **Minimum number**: (e.g. `1`)
- **Maximum number**: (e.g. `300`)
- **Number of winners**: (e.g. `4`)

The tool will scroll through the comment container, apply the rules, draw the winners, and print the results immediately.

---

## 📤 Output Format

The output is formatted for easy copy-pasting directly into your Facebook announcement:

```text
Picked numbers:

[Number] - [Name]
[Number] - [Name]
[Number] - [Name]
[Number] - [Name]

🎉 Congratulations to all the winners!
🙏 Thank you so much to everyone who participated! Stay tuned for the next one!
```

---

## 📊 Audit Reports

Every run automatically creates a full audit record in:
📂 `results/giveaway_result_YYYYMMDD_HHMMSS.txt`

The report includes:
- Exact date, post URL, and number range
- Total comments scanned vs. valid unique entries
- Full list of qualifying participants and their chosen numbers
- Full list of disqualified participants with exact rejection reasons (out of range, multiple comments, duplicate numbers)
- Final selected winners

---

## 📁 Project Structure

```text
facebook-giveaway-picker/
├── .venv/                          # Python virtual environment (ignored by Git)
├── results/                        # Generated audit reports (ignored by Git)
├── giveaway_picker.py              # Main automation & winner selection script
├── start_browser_debug.bat         # Optional 1-click launcher for Brave/Chrome/Edge with remote debugging
├── run_picker.bat                  # 1-click launcher for the Python script
├── requirements.txt                # Python package dependencies (Playwright)
├── .gitignore                      # Prevents committing venv, caches, and audit logs
└── README.md                       # Documentation
```

---

## 🔒 Security & Privacy

- Remote debugging port `9222` only listens on `127.0.0.1` (**localhost**). It is never exposed to the local network or internet.
- Whenever you close Brave and reopen it from your normal shortcut, remote debugging is **automatically disabled**.
- All winner logs saved in `results/` are ignored by `.gitignore` to keep participant identities private.

---

## ☕ Support & Developer

Developed with ❤️ by **Nomer Israel**
- **GitHub**: [@nmrisrl11](https://github.com/nmrisrl11)
- **Support**: If this tool helped make your giveaways faster and easier, consider buying me a coffee:  
  👉 **[Buy Me a Coffee](https://buymeacoffee.com/nmrisrl11)**

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
