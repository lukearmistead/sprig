# 🌱 Sprig

**Take control of your financial data.** Sprig connects to your bank accounts, downloads your transactions, and exports them to spreadsheets with AI-powered categorization—all stored locally on your computer.

## Why Use Sprig?

Most budgeting apps lock your data in their platforms. Sprig gives you:

- **Full ownership** - Your transaction data stays on your computer
- **Flexible analysis** - Use Excel, Google Sheets, or any tool you prefer
- **Automatic categorization** - Claude AI intelligently tags transactions (groceries, dining, utilities, etc.)
- **Privacy first** - No third-party servers, no data sharing, no tracking

**Perfect for:** Financial analysts, budget-conscious individuals, small business owners, or anyone who wants complete control over their financial data.

## What You'll Get

After running Sprig, you'll have a CSV file like this:

| date | description | amount | inferred_category | account_id |
|------|-------------|--------|-------------------|------------|
| 2025-11-15 | WHOLE FOODS | -87.32 | groceries | acc_xyz |
| 2025-11-14 | UBER EATS | -24.50 | dining | acc_xyz |
| 2025-11-13 | SHELL GAS | -45.00 | fuel | acc_xyz |
| 2025-11-12 | Paycheck Deposit | +2500.00 | income | acc_xyz |

Open it in Excel, Google Sheets, or any spreadsheet tool to analyze spending patterns, create budgets, or build financial reports.

---

## Quick Start

**Time to complete:** ~15 minutes

### What You'll Need

**Before you start**, gather these three things:

1. **Python 3.8+** ([Download here](https://www.python.org/downloads/))
   - Check if you have it: Open terminal/command prompt and run `python --version`

2. **Teller.io Account** ([Sign up free](https://teller.io))
   - This service securely connects to your bank (used by fintech apps)
   - You'll need: APP_ID and certificate files from your Teller dashboard

3. **Claude API Key** ([Get one here](https://console.anthropic.com)) - *Optional*
   - Only needed if you want AI to categorize your transactions
   - Without it, Sprig still downloads transactions but won't auto-categorize

### Step 1: Install Sprig

Open your terminal or command prompt and run:

```bash
# Download Sprig
git clone https://github.com/lukearmistead/sprig.git
cd sprig

# Create isolated environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Your Accounts

```bash
# Copy the example configuration file
cp .env.example .env

# Open .env in any text editor and fill in:
# - APP_ID from your Teller dashboard
# - CLAUDE_API_KEY from Anthropic (optional)
```

**Important:** Download your certificate files from Teller and save them in a `certs/` folder.

### Step 3: Connect Your Banks

```bash
python sprig.py auth
```

**What happens:** A browser window opens with Teller's secure connection flow. Select your bank, log in, and authorize access. Sprig saves your connection details automatically.

### Step 4: Get Your Transactions

```bash
# Download and categorize transactions
python sprig.py sync

# Export to CSV
python sprig.py export
```

**Done!** Your transactions are now in `exports/transactions-YYYY-MM-DD.csv`. Open it with Excel, Google Sheets, or any spreadsheet tool.

---

## Detailed Configuration

### Getting Your Teller Credentials

**Step-by-step:**

1. Go to [teller.io](https://teller.io) and create a free developer account
2. Click "Create Application" in your dashboard
3. Copy your **APP_ID** (looks like `app_xxxxxxxxxxxxx`)
4. Download your **certificate.pem** and **private_key.pem** files
5. Create a folder called `certs/` in your Sprig directory
6. Move both certificate files into the `certs/` folder

### Your .env File Explained

Open the `.env` file and customize these settings:

```env
# Required: Your Teller credentials
APP_ID=app_xxxxxxxxxxxxx           # From Teller dashboard
CERT_PATH=certs/certificate.pem    # Path to your certificate
KEY_PATH=certs/private_key.pem     # Path to your private key

# Optional: AI categorization
CLAUDE_API_KEY=sk-ant-api03-...    # From console.anthropic.com

# Database location (default is fine)
DATABASE_PATH=sprig.db

# Logging level: DEBUG, INFO, WARNING, ERROR
# LOG_LEVEL=INFO
```

**Tip:** Bank connections (ACCESS_TOKENS) are added automatically when you run `python sprig.py auth`. You don't need to edit them manually.

---

## How to Use Sprig

### Three Simple Commands

#### 1. `python sprig.py auth` - Connect Your Banks

**When to use:** First time setup, or when adding new bank accounts

**What it does:**
- Opens your browser to Teller's secure login page
- You select your bank and log in (Sprig never sees your password)
- Saves the connection so you can download transactions

**What you'll see:**
```
🔐 Starting Teller authentication (app: app_abc123, environment: development)
🌐 Opening browser to http://localhost:8001
Please complete the bank authentication in your browser...
✅ Successfully added 2 account(s)!
```

---

#### 2. `python sprig.py sync` - Download Transactions

**When to use:** Daily, weekly, or whenever you want fresh transaction data

**What it does:**
- Connects to your banks and downloads recent transactions
- Stores them in a local database (sprig.db)
- If you have Claude API configured, automatically categorizes transactions

**What you'll see:**
```
🔄 Starting sync for 2 access token(s)
🤖 Categorizing 47 transaction(s) using Claude AI
✅ Successfully synced 2 valid token(s)
✅ Categorization complete
```

**Time:** Usually 10-30 seconds depending on transaction volume

---

#### 3. `python sprig.py export` - Create Your Spreadsheet

**When to use:** After syncing, whenever you want to analyze your data

**What it does:**
- Reads all transactions from the database
- Creates a CSV file with all your transaction data
- Saves it to `exports/transactions-YYYY-MM-DD.csv`

**What you'll see:**
```
📊 Starting export to exports/transactions-2025-11-17.csv
✅ Exported 347 transaction(s) to exports/transactions-2025-11-17.csv
```

**Optional:** Export to a custom location:
```bash
python sprig.py export -o ~/Documents/my-finances.csv
```

---

### Recategorization

After improving your categories or prompts, use `--recategorize` to re-run AI categorization on all transactions:

```bash
# Update your categories in config.yml, then:
python sprig.py sync --recategorize

# This will:
# 1. Clear all existing categories
# 2. Re-categorize every transaction with updated AI
# 3. Apply your improved category definitions
```

---

### Understanding Transaction Categories

When Claude categorizes your transactions, it uses these categories:

| Category | Examples |
|----------|----------|
| **groceries** | Whole Foods, Trader Joe's, Safeway |
| **dining** | Restaurants, cafes, UberEats, DoorDash |
| **fuel** | Shell, Chevron, gas stations |
| **transport** | Uber, Lyft, public transit, parking |
| **entertainment** | Netflix, Spotify, movie theaters |
| **utilities** | Electric bill, water, internet, phone |
| **shopping** | Amazon, Target, clothing stores |
| **health** | Doctor visits, pharmacy, gym |
| **income** | Paychecks, refunds, transfers in |

**Plus more categories!** You can customize these by editing `config.yml` in the Sprig directory.

### Your CSV Output

Every export includes these columns:

| Column | What It Means |
|--------|---------------|
| `id` | Unique transaction ID |
| `account_id` | Which account this came from |
| `amount` | Dollar amount (negative = spent, positive = received) |
| `description` | Merchant name (e.g., "WHOLE FOODS") |
| `date` | When the transaction occurred |
| `type` | Transaction type (card_payment, ach, wire, etc.) |
| `status` | Transaction status (posted, pending, etc.) |
| `details` | Additional transaction details (JSON) |
| `running_balance` | Your balance after this transaction |
| `links` | Related links and references (JSON) |
| `inferred_category` | AI-assigned category (groceries, dining, etc.) |
| `created_at` | When this record was added to your database |

Set `LOG_LEVEL=DEBUG` in `.env` for detailed operation logs.

---

## Developer Guide

### Development Setup
```bash
# Install dependencies and run tests
pip install -r requirements.txt
python -m pytest
ruff check .  # Linting
```

### Project Structure
- **`sprig/auth.py`** - Teller Connect authentication server
- **`sprig/database.py`** - SQLite operations
- **`sprig/teller_client.py`** - Teller API client with mTLS
- **`sprig/categorizer.py`** - Claude AI categorization  
- **`sprig/sync.py`** - Transaction sync orchestration
- **`sprig/export.py`** - CSV export
- **`sprig/models/`** - Pydantic data models
- **`config.yml`** - Category definitions

### Contributing
1. Clone repo → create feature branch → add tests → submit PR
2. Follow functional programming style with type safety
3. Run tests with `pytest` and linting with `ruff check .`

---

## Troubleshooting

### Common Issues

#### "Certificate error" or "No such file"

**Problem:** Sprig can't find your Teller certificate files

**Solution:**
1. Go to your [Teller dashboard](https://teller.io)
2. Download `certificate.pem` and `private_key.pem`
3. Create a `certs/` folder in your Sprig directory
4. Move both files into `certs/`

---

#### "Authentication failed" or "Invalid token"

**Problem:** Your bank connection expired or was revoked

**Solution:**
1. Run `python sprig.py auth` again to reconnect
2. Or, remove old tokens from `.env` (the ACCESS_TOKENS line)

**Why this happens:** Bank connections can expire for security, or if you changed your bank password

---

#### "ModuleNotFoundError" or "No module named..."

**Problem:** Python dependencies aren't installed

**Solution:**
```bash
# Make sure you're in the Sprig directory
cd /path/to/sprig

# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

#### "Configuration error: APP_ID not found"

**Problem:** Your `.env` file is missing or incomplete

**Solution:**
1. Make sure `.env` exists in your Sprig folder
2. Open it and add your `APP_ID=app_xxxxx` from Teller
3. Check that there are no extra spaces or quotes

---

#### Sync is slow or timing out

**Problem:** Too many transactions or slow network

**Solution:**
- Normal: 100-500 transactions takes 10-30 seconds
- Large datasets: 1000+ transactions may take 1-2 minutes
- Set `LOG_LEVEL=DEBUG` in `.env` to see progress details

---

**Still stuck?** Check [GitHub Issues](https://github.com/lukearmistead/sprig/issues) or create a new issue with:
- The error message you're seeing
- What command you ran
- Your LOG_LEVEL=DEBUG output (remove any sensitive data!)

---

## Frequently Asked Questions

### Is my banking data secure?

**Yes.** Sprig stores everything locally on your computer. Your transactions never leave your machine. We use:
- **Teller.io** for secure bank connections (bank-grade security)
- **Local SQLite database** (no cloud storage)
- **mTLS certificates** (encrypted communication)

Your bank login credentials are only entered on your bank's official website, never in Sprig.

### How much does it cost?

- **Sprig:** Free and open source
- **Teller.io:** Free tier includes 100 transactions/month. [See pricing](https://teller.io/pricing)
- **Claude API:** Optional. ~$0.10-0.50 per 1000 transactions categorized. [See pricing](https://anthropic.com/pricing)

### Do I need to be technical to use this?

You need basic comfort with:
- Running terminal/command line commands
- Editing text files (like .env)
- Installing software

If you can install Python and copy/paste commands, you can use Sprig. The Quick Start guide walks you through everything.

### What banks are supported?

Teller.io supports 5,000+ banks including:
- Major banks: Chase, Bank of America, Wells Fargo, Citi
- Credit unions
- Online banks: Ally, Marcus, Discover

Check [Teller's bank list](https://teller.io/institutions) for your specific bank.

### Can I use this for business accounts?

Yes! Sprig works with both personal and business bank accounts, as long as they're supported by Teller.io.

### How often should I sync?

Up to you! Common patterns:
- **Daily:** Get yesterday's transactions each morning
- **Weekly:** Sunday night to review the week's spending
- **Monthly:** End of month for budgeting and reports

Teller.io's free tier limits you to 100 transactions per month of syncing.

### What if I don't want AI categorization?

Just skip adding `CLAUDE_API_KEY` to your `.env` file. Sprig will:
- Still download all your transactions
- Still export to CSV
- Leave the `inferred_category` column empty (you can categorize manually in Excel)

### Can I categorize old transactions?

Yes. Once you add `CLAUDE_API_KEY`, run `python sprig.py sync` and Claude will automatically categorize any uncategorized transactions in your database.

### Where is my data stored?

- **Transactions:** `sprig.db` (SQLite database in your Sprig folder)
- **Exports:** `exports/` folder (CSV files)
- **Configuration:** `.env` file
- **Certificates:** `certs/` folder

To backup your data, just copy the `sprig.db` file.

### Can I run this on a schedule?

Yes! You can set up a cron job (Mac/Linux) or Task Scheduler (Windows) to run `python sprig.py sync && python sprig.py export` daily.

Example cron (runs daily at 6 AM):
```
0 6 * * * cd /path/to/sprig && source venv/bin/activate && python sprig.py sync && python sprig.py export
```

