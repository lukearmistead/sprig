# 🌱 Sprig

**Actually-personal personal finance**: Sprig connects to your bank accounts, downloads your transactions locally, buckets them into customizable AI-powered categories, and exports it all into a spreadsheet so you can budget your way.


You can use Sprig to download a CSV like this:

| id | date | description | amount | inferred_category | confidence | counterparty | account_name | account_subtype | account_last_four |
|----|------|-------------|--------|-------------------|------------|--------------|--------------|-----------------|-------------------|
| tx_abc123 | 2025-11-15 | SAFEWAY | -87.32 | groceries | 0.95 | Safeway | Checking | checking | 1234 |
| tx_abc124 | 2025-11-14 | SHELL GAS | -45.00 | transport | 0.92 | Shell | Credit Card | credit_card | 5678 |
| tx_abc125 | 2025-11-12 | REI | -142.50 | shopping | 0.94 | REI | Credit Card | credit_card | 5678 |

---

## Quickstart

**This is a quickstart guide to get you running quickly. More detailed instructions, troubleshooting, and customization options are available in the sections below.**

### Step 1: Install Sprig

**Option A: Download Standalone Executable (Easiest)**

Download the latest release for your platform from [GitHub Releases](https://github.com/lukearmistead/sprig/releases):
- **macOS**: `sprig`
- **Windows**: `sprig.exe`

Move the executable somewhere in your PATH (e.g., `/usr/local/bin` on macOS) or run it directly from the download location.

**macOS users:** The first time you run Sprig, macOS may block it because it's not from the App Store. To allow it:
1. Try to run `./sprig` — you'll see a security warning
2. Open **System Settings** → **Privacy & Security**
3. Scroll down to see "sprig was blocked from use"
4. Click **Open Anyway** and confirm

This only needs to be done once.

**Option B: Install with Python (For Developers)**

```bash
# Download Sprig
git clone https://github.com/lukearmistead/sprig.git
cd sprig

# Create isolated environment (recommended)
python -m venv venv

# Activate the environment
source venv/bin/activate
# On Windows, use: venv\Scripts\activate

# Install the package
pip install -e .
```

### Step 2: Set Up Your Accounts

You'll need accounts with two services (both free to start):

1. **Teller.io** - Connects securely to your bank accounts
   - Go to [teller.io](https://teller.io) and create a free developer account
   - Create a new application (use "Personal Project" for company name)
   - Go to [Certificate Settings](https://teller.io/settings/certificates), click "Create Certificate" and download the zip
   - Extract and save `certificate.pem` and `private_key.pem` to `~/.sprig/certs/`
   - Get your **APP_ID** from [Application Settings](https://teller.io/settings/application)

2. **Anthropic** - Powers AI transaction categorization (required)
   - Go to [console.anthropic.com](https://console.anthropic.com) and create an account
   - Create an API key (starts with `sk-ant-api03-`)
   - **Cost:** ~$0.10-0.50 per 1000 transactions ([see pricing](https://platform.claude.com/docs/en/build-with-claude/batch-processing#pricing))

### Step 3: Run Sprig

```bash
sprig sync
```

Sprig guides you through setup automatically:
1. **First run:** Opens `~/.sprig/config.yml` — add your `app_id` and `claude_key`
2. **Second run:** Opens browser to connect your bank accounts
3. **After that:** Fetches, categorizes, and exports your transactions

**Done!** Your transactions are in `~/.sprig/exports/transactions-YYYY-MM-DD.csv`.

**Want to customize categories?** Edit `~/.sprig/config.yml` to create your own categories (business expenses, coffee, etc.). [See customization guide below](#customizing-your-categories).

---

## How to Use Sprig

### The `sprig sync` Command

One command does everything:

```bash
sprig sync
```

**What it does:**
1. Checks for API credentials — opens config file if missing
2. Checks for connected accounts — opens browser to connect if none
3. Downloads transactions from your banks
4. Categorizes them with Claude AI
5. Exports to CSV
6. Offers to add another bank account

**What you'll see:**
```
Fetching transactions from Teller
Filtering transactions from 2024-01-01
Categorizing transactions
Categorizing 47 transaction(s) using Claude AI
   Processing in 1 batch(es) of up to 50 each
   Batch 1/1 (47 transactions)...
      Batch 1 complete: 47 categorized
Categorization complete
   Successfully categorized: 47 transactions
   Success rate: 100.0%
Exporting to CSV
Exported 47 transaction(s) to ~/.sprig/exports/transactions-2025-11-17.csv

Add another bank account? [y/N]
```

---

### Recategorization

After improving your categories in `~/.sprig/config.yml`, you can re-categorize transactions by:

1. **Delete the database and re-sync:**
   ```bash
   rm ~/.sprig/sprig.db
   sprig sync
   ```

2. **Or manually clear categories:** Use a SQLite tool to set `inferred_category` to NULL for transactions you want recategorized, then run `sprig categorize`.

---

### Default Transaction Categories

When Claude categorizes your transactions, it uses these 14 categories:

| Category | Examples |
|----------|----------|
| **dining** | Restaurants, cafes, food delivery |
| **groceries** | Supermarkets, convenience stores |
| **transport** | Gas, rideshares, parking, car maintenance |
| **travel** | Flights, hotels, vacation rentals |
| **shopping** | Clothing, electronics, retail |
| **home** | Rent, mortgage, property taxes |
| **utilities** | Electric, water, internet, phone |
| **health** | Medical, pharmacy, gym |
| **entertainment** | Streaming, movies, hobbies |
| **income** | Salary, refunds, reimbursements |
| **savings** | Investments, retirement contributions |
| **general** | Bank fees, donations, gifts |
| **transfers** | Credit card payments, loan payments |
| **undefined** | Unclear or unclassifiable transactions |

You can customize these by editing `~/.sprig/config.yml`.

---

### Customizing Your Categories

Sprig uses 14 default categories, but you can completely customize them to match your budgeting needs.

#### How to Change Categories

1. **Edit the config file** at `~/.sprig/config.yml`:
   - Open `~/.sprig/config.yml` with any text editor

2. **Modify categories** using this format:
```yaml
categories:
  - name: your_category_name
    description: "Detailed description to help AI classify transactions"
  - name: another_category
    description: "Another description explaining what belongs here"
```

3. **Apply your changes** by re-syncing (delete `~/.sprig/sprig.db` first to recategorize all transactions)

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
- **After changes**, delete `~/.sprig/sprig.db` and re-sync to apply new categories to existing transactions
- **Keep backups** - copy your `~/.sprig/config.yml` before making major changes

#### Why Customize?

- **Match your budget structure** - align with spreadsheet categories you already use
- **Specific tracking** - separate "coffee" from "dining" if you want to track caffeine spending
- **Business needs** - create categories for tax deduction tracking
- **Life changes** - add "baby_expenses" or "home_improvement" when your spending changes

### Your CSV Output

Every export includes these 10 columns:

| Column | What It Means |
|--------|---------------|
| `id` | Unique transaction ID (e.g., "tx_abc123") |
| `date` | When the transaction occurred (YYYY-MM-DD) |
| `description` | Merchant name as shown by your bank (e.g., "WHOLE FOODS") |
| `amount` | Dollar amount (negative = spent, positive = received) |
| `inferred_category` | LLM-assigned category (groceries, dining, transport, etc.) |
| `confidence` | LLM confidence score for the inferred_category from 0 to 1 (e.g., 0.95 = very confident, 0.45 = uncertain) |
| `counterparty` | Clean merchant name extracted from transaction details |
| `account_name` | Friendly account name (e.g., "Checking", "Credit Card") |
| `account_subtype` | Account type (checking, credit_card, savings, etc.) |
| `account_last_four` | Last 4 digits of account number for identification |

**Tip:** Sort by confidence in your spreadsheet to review transactions where the LLM was less certain about the categorization.

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
- **`sprig/cli.py`** - Single-command CLI entry point
- **`sprig/auth.py`** - Teller Connect authentication server
- **`sprig/categorize.py`** - Claude AI categorization
- **`sprig/database.py`** - SQLite operations
- **`sprig/export.py`** - CSV export
- **`sprig/fetch.py`** - Transaction fetching from Teller
- **`sprig/logger.py`** - Logging configuration
- **`sprig/teller_client.py`** - Teller API client with mTLS
- **`sprig/models/`** - Pydantic data models
- **`config.yml`** - Category definitions and settings

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
2. Move both files into `~/.sprig/certs/`

---

#### "Authentication failed" or "Invalid token"

**Problem:** Your bank connection expired or was revoked

**Solution:**
1. Run `sprig sync` — it will detect the missing connection and prompt you to reconnect

**Why this happens:** Bank connections can expire for security, or if you changed your bank password

---

#### "ModuleNotFoundError" or "No module named..."

**Problem:** Python dependencies aren't installed (only applies if using Python install)

**Solution:**
```bash
# Make sure you're in the Sprig directory
cd /path/to/sprig

# Activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install the package
pip install -e .
```

**Note:** This error doesn't apply if you're using the standalone executable.

---

#### "Configuration error" or "APP_ID not found"

**Problem:** Credentials not set up

**Solution:**
1. Run `sprig sync` — it will open `~/.sprig/config.yml` for you to add credentials
2. Add your Teller `app_id` and `claude_key`
3. Save the file and run `sprig sync` again

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
- Set `from_date` in `~/.sprig/config.yml` to a more recent date to process fewer transactions
- Run `sprig sync` multiple times - it only processes uncategorized transactions
- Wait a few minutes between runs if you hit limits

**What you'll see:**
```
Hit Claude API rate limit - this is normal with large transaction volumes
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
- **Claude API:** Required. ~$0.10-0.50 per 1000 transactions categorized. [See pricing](https://anthropic.com/pricing)

### Do I need to be technical to use this?

**For non-technical users:** Use the standalone executable - just download and run. You'll need:
- Basic comfort with terminal/command line
- Creating accounts on Teller.io and Anthropic
- Downloading certificate files to `~/.sprig/certs/`

**For technical users:** Use the Python install if you want to contribute or customize.

The credential setup (Teller and Claude accounts) is a one-time process. The Quick Start guide walks you through everything step-by-step.

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

Sprig requires a Claude API key for transaction categorization. You can minimize AI usage by:
- Adding manual category overrides in `~/.sprig/config.yml` for specific transactions
- Manual overrides take precedence over AI categorization
- Only transactions without manual overrides will be categorized by Claude AI

### Can I categorize old transactions?

Yes. Run `sprig sync` and Claude will automatically categorize any uncategorized transactions in your database.

### Can I change the categories Sprig uses?

Absolutely! Edit `~/.sprig/config.yml` to customize categories for your needs. You can:
- Rename existing categories (e.g., "transport" → "car_expenses")
- Add new categories (e.g., "coffee", "pet_care", "business_meals")
- Remove categories you don't need
- Update descriptions to improve categorization accuracy

After making changes, delete `~/.sprig/sprig.db` and run `sprig sync` to apply your new categories to all transactions.

### Where is my data stored?

All Sprig data is stored in `~/.sprig/`:

- **Transactions:** `~/.sprig/sprig.db` (SQLite database)
- **Exports:** `~/.sprig/exports/` (CSV files)
- **Config & credentials:** `~/.sprig/config.yml`
- **Certificates:** `~/.sprig/certs/`

To backup your data, copy the `~/.sprig/` folder.

### Can I run this on a schedule?

Yes! You can set up a cron job (Mac/Linux) or Task Scheduler (Windows) to run `sprig sync` daily.

Example cron (runs daily at 6 AM):
```
0 6 * * * /usr/local/bin/sprig sync
```

