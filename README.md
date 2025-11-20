# 🌱 Sprig

**Actually-personal personal finance**: Sprig connects to your bank accounts, downloads your transactions locally, buckets them into customizable AI-powered categories, and exports it all into a spreadsheet so you can budget your way.


You can use Sprig to download a CSV like this:

| id | date | description | amount | inferred_category | counterparty | account_name | account_subtype | account_last_four |
|----|------|-------------|--------|-------------------|--------------|--------------|-----------------|-------------------|
| tx_abc123 | 2025-11-15 | WHOLE FOODS | -87.32 | groceries | Whole Foods Market | Checking | checking | 1234 |
| tx_abc124 | 2025-11-14 | UBER EATS | -24.50 | dining | Uber Eats | Checking | checking | 1234 |
| tx_abc125 | 2025-11-13 | SHELL GAS | -45.00 | transport | Shell | Credit Card | credit_card | 5678 |
| tx_abc126 | 2025-11-12 | Paycheck Deposit | +2500.00 | income | Acme Corp | Checking | checking | 1234 |

---

## Quick Setup Guide

**This is a quickstart guide to get you running quickly. More detailed instructions, troubleshooting, and customization options are available in the sections below.**

### Step 1: Install Sprig

```bash
# Download Sprig
git clone https://github.com/lukearmistead/sprig.git
cd sprig

# Create isolated environment (recommended)
python -m venv venv

# Activate the environment
source venv/bin/activate
# On Windows, use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Set Up Your Accounts

You'll need accounts with two services (both free to start):

1. **Teller.io** - Connects securely to your bank accounts
   - Go to [teller.io](https://teller.io) and create a free developer account
   - Create a new application (use "Personal Project" for company name)
   - Download your certificates:
     - Go to [Certificate Settings](https://teller.io/settings/certificates)
     - Click "Create Certificate" and download the zip file
     - Extract it and move `certificate.pem` and `private_key.pem` to the `certs/` folder in Sprig
   - Get your **APP_ID** from [Application Settings](https://teller.io/settings/application)
   - **Save these** - you'll enter them when you run `sprig auth` in Step 3

2. **Anthropic** - Powers AI transaction categorization (optional but recommended)
   - Go to [console.anthropic.com](https://console.anthropic.com) and create an account
   - Create an API key (starts with `sk-ant-`)
   - **Cost:** ~$0.10-0.50 per 1000 transactions (~$1-5/month for most users)
   - **Save this** - you'll enter it when you run `sprig auth` in Step 3

### Step 3: Set Up and Connect Your Banks

```bash
python sprig.py auth
```

**What happens:**
1. **First run:** You'll be prompted to enter:
   - Your Teller APP_ID
   - Your Claude API key
   - Certificate paths (defaults to `certs/certificate.pem` and `certs/private_key.pem`)
2. **Then:** A browser opens to Teller's secure login
3. Select your bank, log in normally, and authorize access
4. Sprig automatically saves your bank connection

**To stop:** Press Control-C in your terminal when finished.

### Step 4: Get Your Data

```bash
# Download and categorize recent transactions (last 30 days to start)
python sprig.py sync --from-date 2024-10-20

# Export to spreadsheet
python sprig.py export
```

**Done!** Your transactions are in `exports/transactions-YYYY-MM-DD.csv`.

**Want to customize categories?** You can edit `config.yml` to create your own categories (business expenses, coffee, etc.) and then run `python sprig.py sync --recategorize` to apply them. [See customization guide below](#customizing-your-categories).

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
Starting Teller authentication (app: app_abc123, environment: development)
Opening browser to http://localhost:8001
Please complete the bank authentication in your browser...
Successfully added 2 account(s)!
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
Starting sync for 2 access token(s)
Categorizing 47 uncategorized transaction(s) using Claude AI
   Processing in 5 batch(es) of up to 10 transactions each
   Processing batch 1/5 (10 transactions)...
      Batch 1 complete: 10 categorized
   Processing batch 2/5 (10 transactions)...
      Batch 2 complete: 10 categorized
   [... continues for remaining batches ...]
Successfully synced 2 valid token(s)
Categorization complete
   Successfully categorized: 47 transactions
   Success rate: 100.0%
```

**Time:** Usually 10-30 seconds depending on transaction volume

**Options:**
```bash
python sprig.py sync --from-date 2024-11-01  # Only sync from this date onwards (reduces API costs)
python sprig.py sync --batch-size 5          # Smaller batches (gentler on rate limits)
python sprig.py sync --recategorize          # Clear and recategorize all transactions
```

---

#### 3. `python sprig.py export` - Create Your Spreadsheet

**When to use:** After syncing, whenever you want to analyze your data

**What it does:**
- Reads all transactions from the database
- Creates a CSV file with all your transaction data
- Saves it to `exports/transactions-YYYY-MM-DD.csv`

**What you'll see:**
```
Starting export to exports/transactions-2025-11-17.csv
Exported 347 transaction(s) to exports/transactions-2025-11-17.csv
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

### Default Transaction Categories

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

---

### Customizing Your Categories

Sprig uses 13 default categories, but you can completely customize them to match your budgeting needs.

#### How to Change Categories

1. **Edit the config file** in your Sprig directory:
   - Open `config.yml` with any text editor

2. **Modify categories** using this format:
```yaml
categories:
  - name: your_category_name
    description: "Detailed description to help AI classify transactions"
  - name: another_category
    description: "Another description explaining what belongs here"
```

3. **Apply your changes** by recategorizing all transactions:
```bash
python sprig.py sync --recategorize
```

#### Example Customizations

**For Business Owners:**
```yaml
categories:
  - name: office_supplies
    description: "Pens, paper, computers, software, and business equipment"
  - name: marketing
    description: "Advertising, social media, website costs, and promotional materials"
  - name: professional_services
    description: "Legal fees, accounting, consultants, and business services"
```

**For Families:**
```yaml
categories:
  - name: kids_activities
    description: "Sports fees, music lessons, school supplies, and children's activities"
  - name: household
    description: "Cleaning supplies, laundry, home maintenance, and family necessities"
  - name: education
    description: "Tuition, books, school fees, and learning-related expenses"
```

**For Detailed Budgeters:**
```yaml
categories:
  - name: coffee_drinks
    description: "Coffee shops, Starbucks, espresso, and caffeine purchases"
  - name: takeout_lunch
    description: "Weekday lunch purchases and quick meal delivery"
  - name: weekend_dining
    description: "Restaurants, bars, and social dining experiences"
```

#### Important Notes

- **Category names** should be simple, lowercase, with underscores (no spaces)
- **Descriptions** should be detailed - Claude uses them to make categorization decisions
- **After changes**, always run `--recategorize` to apply new categories to existing transactions
- **Keep backups** - copy your `config.yml` before making major changes

#### Why Customize?

- **Match your budget structure** - align with spreadsheet categories you already use
- **Specific tracking** - separate "coffee" from "dining" if you want to track caffeine spending
- **Business needs** - create categories for tax deduction tracking
- **Life changes** - add "baby_expenses" or "home_improvement" when your spending changes

### Your CSV Output

Every export includes these 9 columns:

| Column | What It Means |
|--------|---------------|
| `id` | Unique transaction ID (e.g., "tx_abc123") |
| `date` | When the transaction occurred (YYYY-MM-DD) |
| `description` | Merchant name as shown by your bank (e.g., "WHOLE FOODS") |
| `amount` | Dollar amount (negative = spent, positive = received) |
| `inferred_category` | AI-assigned category (groceries, dining, transport, etc.) |
| `counterparty` | Clean merchant name extracted from transaction details |
| `account_name` | Friendly account name (e.g., "Checking", "Credit Card") |
| `account_subtype` | Account type (checking, credit_card, savings, etc.) |
| `account_last_four` | Last 4 digits of account number for identification |

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
1. Download `certificate.pem` and `private_key.pem` from [Certificate Settings](https://teller.io/settings/certificates)
2. Move both files into the `certs/` folder in your Sprig directory

---

#### "Authentication failed" or "Invalid token"

**Problem:** Your bank connection expired or was revoked

**Solution:**
1. Run `python sprig.py auth` again to reconnect your banks

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

#### "Configuration error" or "APP_ID not found"

**Problem:** Credentials not set up

**Solution:**
1. Run `python sprig.py auth` - it will prompt you to enter credentials
2. Make sure you enter your Teller APP_ID and Claude API key correctly
3. Your credentials are stored securely in your system keyring

---

#### Sync is slow or timing out

**Problem:** Too many transactions or slow network

**Solution:**
- Normal: 100-500 transactions takes 10-30 seconds
- Large datasets: 1000+ transactions may take 1-2 minutes
- Set `LOG_LEVEL=DEBUG` in `.env` to see progress details

#### API Rate Limits

**Problem:** Large transaction volumes may hit Claude API rate limits

**Solutions:**
- Use `--from-date YYYY-MM-DD` to process recent transactions first
- Use `--batch-size 5` for smaller, gentler API requests
- Run `sync` multiple times - it only processes uncategorized transactions
- Wait a few minutes between runs if you hit limits

**What you'll see:**
```
Hit Claude API rate limit - this is normal with large transaction volumes
Tip: Use '--from-date YYYY-MM-DD' flag to sync fewer transactions and reduce API costs
Waiting 60 seconds for rate limit to reset...
```

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
- **Teller.io:** Free tier includes 100 bank connections (accounts). [See teller.io](https://teller.io) for current pricing
- **Claude API:** Optional. ~$0.10-0.50 per 1000 transactions categorized. [See pricing](https://anthropic.com/pricing)

### Do I need to be technical to use this?

**For technical users:** You'll be able to figure out the setup without much trouble.

**For non-technical users:** You'll need basic comfort with:
- Running terminal/command line commands
- Editing text files (like .env)
- Creating accounts on websites (Teller, Anthropic)
- Installing software

If you can install Python and copy/paste commands, you can use Sprig. The most involved step is getting the credentials set up in your .env file. The Quick Start guide walks you through everything step-by-step.

**Note:** Non-technical users may find the credential setup (Teller and Claude accounts) to be the most challenging part, but it's a one-time setup.

### What banks are supported?

Teller.io supports 5,000+ banks including:
- Major banks: Chase, Bank of America, Wells Fargo, Citi
- Credit unions
- Online banks: Ally, Marcus, Discover

Check teller.io for supported banks and institutions.

### Can I use this for business accounts?

Yes! Sprig works with both personal and business bank accounts, as long as they're supported by Teller.io.

### How often should I sync?

Up to you! Common patterns:
- **Daily:** Get yesterday's transactions each morning
- **Weekly:** Sunday night to review the week's spending
- **Monthly:** End of month for budgeting and reports

Teller.io's free tier includes 100 bank connections (individual accounts you can connect).

### What if I don't want AI categorization?

When running `python sprig.py auth` for the first time, press Enter when prompted for the Claude API key (leaving it blank). Sprig will:
- Still download all your transactions
- Still export to CSV
- Leave the `inferred_category` column empty (you can categorize manually in Excel)

You can add the Claude API key later by running `python sprig.py auth` again.

### Can I categorize old transactions?

Yes. Once you add your Claude API key (via `python sprig.py auth`), run `python sprig.py sync` and Claude will automatically categorize any uncategorized transactions in your database.

### Can I change the categories Sprig uses?

Absolutely! Edit the `config.yml` file in your Sprig directory to customize categories for your needs. You can:
- Rename existing categories (e.g., "transport" → "car_expenses")
- Add new categories (e.g., "coffee", "pet_care", "business_meals")
- Remove categories you don't need
- Update descriptions to improve categorization accuracy

After making changes, run `python sprig.py sync --recategorize` to apply your new categories to all existing transactions.

### Where is my data stored?

- **Transactions:** `sprig.db` (SQLite database in your Sprig folder)
- **Exports:** `exports/` folder (CSV files)
- **Credentials:** Secure system keyring (macOS Keychain, Windows Credential Locker, Linux Secret Service)
- **Certificates:** `certs/` folder
- **Category config:** `config.yml` file

To backup your data, just copy the `sprig.db` file.

### Can I run this on a schedule?

Yes! You can set up a cron job (Mac/Linux) or Task Scheduler (Windows) to run `python sprig.py sync && python sprig.py export` daily.

Example cron (runs daily at 6 AM):
```
0 6 * * * cd /path/to/sprig && source venv/bin/activate && python sprig.py sync && python sprig.py export
```

