# Discord Data Analyzer - Your Own Year in Review

## So you have been cucked by Discord's Recap Feature? 

So have I, and I didn't believe their bullshit lie about "we aren't allowed to collect that data". So I made my own. 

If you are in a GDPR-protected region of the world (basically Europe and a few other places), you can force Discord to hand over ALL your data. Here's how to get your recap:

---

## Step 1: Request Your Data from Discord

1. **Open Discord**
2. **Click the gear icon** (⚙️) next to your username at the bottom-left to open **User Settings**
3. Scroll down to **Privacy & Safety**
4. Scroll allllll the way down until you see **Request all of my Data**
5. Click that button and confirm

**Now wait 30 days.** Yes, really. They have 30 days to comply with GDPR requests. Go touch some grass.

After up to 30 days, you'll get an email with a download link.

---

## IMPORTANT PRIVACY WARNING

**DO NOT SHARE THAT DOWNLOAD LINK WITH ANYONE. DO NOT SHARE THE FILES.**

This data package contains:
- Every message you've ever sent
- Every file you've ever uploaded
- Every server you've been in
- Your login history
- Your payment info
- **LITERALLY EVERYTHING**

Treat it like your bank password. Seriously.

---

## Step 2: Extract Your Data

1. **Download the file** from the email link (it'll be a `.zip` file)
2. **Right-click the .zip file** and select "Extract All..." or "Extract Here"
3. You'll get a folder with a bunch of subfolders like:
   - `Account`
   - `Activities`
   - `Messages` ← This is the important one
   - `Servers`
   - And a bunch of other stuff

---

## Step 3: Set Up the Analyzer

### Download This Project

1. Click the green **"Code"** button at the top of this page
2. Select **"Download ZIP"**
3. Extract the ZIP file somewhere convenient (like your Desktop)

### Set Up Your Files

You need to put the analyzer scripts **inside** your Discord data folder. Here's what it should look like:

```
Discord_Package_Extracted/
├── Account/
├── Activities/
├── Messages/          ← Your Discord messages are here
├── Servers/
├── CreateWebsite_v1.py    ← Put this here
├── ExtractData_v3.py      ← Put this here
└── start.bat              ← Put this here
```

**In other words:** Copy `CreateWebsite_v1.py`, `ExtractData_v3.py`, and `start.bat` into the SAME folder where you see the `Messages` folder.

---

## Step 4: Update Your User ID

**⚠️ CRITICAL STEP - DON'T SKIP THIS**

Open `ExtractData_v3.py` and `CreateWebsite_v1.py` in any text editor (Notepad works fine). At the very top, you'll see this line:

```python
USER_ID = "YOUR_USER_ID_HERE"  # Replace with your Discord user ID
```

You need to replace that with **YOUR** Discord User ID.

### How to Get Your Discord User ID:

1. Open Discord
2. Go to **User Settings** (gear icon ⚙️)
3. Go to **Advanced** (scroll down on the left sidebar)
4. Enable **Developer Mode** (toggle it on)
5. Close settings
6. **Right-click your own username** anywhere (in a chat, server member list, your profile, etc.)
7. Click **"Copy User ID"** at the bottom
8. Paste that number into the script where it says `USER_ID = "..."`

**Example:**
```python
USER_ID = "123456789012345678"  ← Replace with YOUR ID
```

Save the file. Do this for BOTH files. 

**Still confused?** Google "how to get my discord user id" - there are tons of guides with pictures.

---

## Step 5: Run the Analyzer

### The Easy Way (Recommended)

**Just double-click `start.bat`**

That's it. The script will:
1. Check if you have Python installed
2. If not, it'll try to download a portable version.
3. Analyze all your messages from 2025
4. Generate a stats website
5. Open it in your browser automatically

**Wait for it to finish.** Depending on how much you talk, this might take a few minutes. The script will show you progress as it goes.

If you're on Mac or Linux, or the .bat file doesnt work, you'll need to run the Python scripts directly:
```bash
python3 ExtractData_v3.py
python3 CreateWebsite_v1.py --serve
```

---

## Step 6: View Your Stats!

Once the script finishes:
- A browser window should open automatically
- You'll see your beautiful stats dashboard
- Scroll through and enjoy your data!

The website includes:
- 📈 Total messages sent in 2025
- 🏆 Your most active servers
- 💬 Your most active DMs
- 😀 Your most-used emotes
- 📎 File types you've shared
- And more!

### Want to View It Again Later?

Just open `discord_stats.html` in any browser. No internet required - it's all local.

---

## Advanced Usage

### Want to Analyze a Different Year?

Open `ExtractData_v3.py` and change this line at the top:
```python
TARGET_YEAR = 2025  # Change this for future years!
```

Then run it again.

### Want to Query the Database?

After running the analyzer, you'll have a `discord_analysis.db` file. You can explore it:

```bash
python ExtractData_v3.py --query
```

This lets you run SQL queries to dig deeper into your data.

**Example queries:**
- Top 50 emotes: `SELECT emote_name, usage_count FROM emotes ORDER BY usage_count DESC LIMIT 50`
- Find specific server: `SELECT * FROM channels WHERE server_name LIKE '%ServerName%'`
- File type breakdown: `SELECT extension, count FROM file_types ORDER BY count DESC`

---

## Troubleshooting

### "Python not found"
- Just say "Yes" when `start.bat` asks to download Python
- Or install Python from [python.org](https://www.python.org/downloads/)

### "Messages folder not found"
- Make sure the scripts are in the SAME folder as your `Messages` folder
- Check your folder structure matches Step 3

### "No data found in database"
- Did you update your User ID in the script?
- Is your Messages folder actually from your Discord GDPR export?
- Did the analyzer finish successfully?

### Numbers seem wrong
- Make sure you updated YOUR User ID in the script
- The analyzer only counts messages from 2025 by default
- Check `TARGET_YEAR` in the script if you want other years

### Website doesn't open
- Manually open `discord_stats.html` in any browser
- Or run: `python CreateWebsite_v1.py --serve`

---

## Contributing

Found a bug? Want to add features? PRs welcome!

---

## Legal Stuff

This tool analyzes YOUR OWN data that Discord gave you. It doesn't scrape Discord, doesn't violate ToS, and doesn't access anyone else's data. It's just a fancy calculator for your personal GDPR export.

**Use responsibly. Don't be a creep.**

---

**Enjoy your stats, and remember: Discord had this data all along. They just didn't want to show it to you.**
