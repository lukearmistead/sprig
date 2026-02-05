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
git clone https://github.com/lukearmistead/sprig.git
cd sprig
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
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
   - **Cost:** ~$0.10-0.50 per 1000 transactions ([see pricing](https://anthropic.com/pricing))

### Step 3: Configure

Run `sprig connect` once to generate the default config file, then open it and fill in your credentials:

```bash
sprig connect          # creates ~/.sprig/config.yml, then exits (app_id not set yet)
```

```yaml
# ~/.sprig/config.yml
app_id: "app_your_id_here"
claude_key: "sk-ant-api03-your_key_here"
```

> **Note:** Standalone executables use `~/Documents/Sprig/config.yml` instead of `~/.sprig/config.yml`.

### Step 4: Connect Your Banks

```bash
sprig connect
```

A browser opens for secure bank login via Teller. Your access tokens are saved automatically to `config.yml`.

### Step 5: Get Your Data

```bash
sprig sync
```

**Done!** Your transactions are in `~/.sprig/exports/transactions-YYYY-MM-DD.csv`.

**Want to customize categories?** Edit the `categories` section in `~/.sprig/config.yml`. [See customization guide below](#customizing-your-categories).

**Note:** Set `from_date` in `config.yml` to control how far back transactions are fetched (default: 2024-01-01).

---

## How to Use Sprig

Sprig has two commands. All configuration lives in `~/.sprig/config.yml`.

### `sprig connect` - Connect Your Banks

**When to use:** First time setup, or when adding new bank accounts.

**What it does:**
- Opens your browser to Teller's secure login page
- You select your bank and log in (Sprig never sees your password)
- Saves the access token to `config.yml`

**What you'll see:**
```
Starting Teller authentication (app: app_abc123)
Opening browser to http://localhost:8001
Please complete the bank authentication in your browser...
Successfully added 2 account(s)!
```

You can run `sprig connect` multiple times to add more bank accounts.

---

### `sprig sync` - Fetch, Categorize, and Export

**When to use:** Daily, weekly, or whenever you want fresh transaction data.

**What it does:**
1. Connects to your banks and downloads recent transactions
2. Applies any manual category overrides from `config.yml`
3. Categorizes remaining transactions using Claude AI
4. Exports everything to CSV at `~/.sprig/exports/transactions-YYYY-MM-DD.csv`

**What you'll see:**
```
Fetching transactions from Teller
Categorizing transactions
Categorizing 47 transaction(s) using Claude AI
   Processing in 5 batch(es) of up to 50 each
   Batch 1/5 (10 transactions)...
      Batch 1 complete: 10 categorized
Categorization complete
   Successfully categorized: 47 transactions
   Success rate: 100.0%
Exporting to CSV
```

---

### Configuration

Everything is in `~/.sprig/config.yml`:

```yaml
# Teller API credentials
app_id: "app_your_id_here"
environment: development
cert_path: certs/certificate.pem
key_path: certs/private_key.pem

# Claude API key for transaction categorization
claude_key: "sk-ant-api03-your_key_here"

# Access tokens (populated automatically by sprig connect)
access_tokens: []

# Only fetch transactions after this date
from_date: "2024-01-01"

# Number of transactions per Claude API call
batch_size: 50

# Transaction categories for AI classification
categories:
  - name: dining
    description: "Restaurants, bars, cafes, food delivery"
  # ... more categories
```

> **Security note:** `config.yml` contains your API keys in plaintext. Don't commit it to version control.

---

### Recategorization

After improving your categories in `config.yml`, re-categorize transactions by deleting the database and re-syncing:

```bash
rm ~/.sprig/sprig.db
sprig sync
```

Or use a SQLite tool to set `inferred_category` to NULL for specific transactions, then run `sprig sync`.

---

### Default Transaction Categories

Claude categorizes transactions into these 14 categories:

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

Customize these by editing `config.yml`.

---

### Customizing Your Categories

#### How to Change Categories

1. Open `~/.sprig/config.yml` with any text editor

2. Modify the `categories` section:
```yaml
categories:
  - name: your_category_name
    description: "Detailed description to help AI classify transactions"
  - name: another_category
    description: "Another description explaining what belongs here"
```

3. Delete `~/.sprig/sprig.db` and run `sprig sync` to apply new categories

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

#### Tips

- **Category names** should be simple, lowercase, with underscores (no spaces)
- **Descriptions** should be detailed — Claude uses them to decide where transactions go
- **Manual overrides** let you pin specific transactions to a category regardless of what Claude thinks. Add them to `config.yml`:
```yaml
manual_categories:
  - transaction_id: txn_abc123
    category: dining
```

### Your CSV Output

Every export includes these 10 columns:

| Column | What It Means |
|--------|---------------|
| `id` | Unique transaction ID (e.g., "tx_abc123") |
| `date` | When the transaction occurred (YYYY-MM-DD) |
| `description` | Merchant name as shown by your bank (e.g., "WHOLE FOODS") |
| `amount` | Dollar amount (negative = spent, positive = received) |
| `inferred_category` | AI-assigned category (groceries, dining, transport, etc.) |
| `confidence` | AI confidence score from 0 to 1 (0.95 = very confident, 0.45 = uncertain) |
| `counterparty` | Clean merchant name extracted from transaction details |
| `account_name` | Friendly account name (e.g., "Checking", "Credit Card") |
| `account_subtype` | Account type (checking, credit_card, savings, etc.) |
| `account_last_four` | Last 4 digits of account number for identification |

**Tip:** Sort by confidence in your spreadsheet to review transactions where the AI was less certain.

---

## Developer Guide

### Development Setup
```bash
pip install -e .
python -m pytest
ruff check .
```

### Project Structure
- **`sprig/cli.py`** - CLI entry point (`connect`, `sync`)
- **`sprig/auth.py`** - Teller Connect authentication server
- **`sprig/categorize.py`** - Claude AI categorization
- **`sprig/database.py`** - SQLite operations
- **`sprig/export.py`** - CSV export
- **`sprig/fetch.py`** - Transaction fetching from Teller
- **`sprig/teller_client.py`** - Teller API client with mTLS
- **`sprig/paths.py`** - Path utilities (install-type detection)
- **`sprig/models/`** - Pydantic data models
- **`config.yml`** - Default configuration template

### Contributing
1. Clone repo → create feature branch → add tests → submit PR
2. Run tests with `pytest` and linting with `ruff check .`

---

## Troubleshooting

### "Certificate error" or "No such file"

Sprig can't find your Teller certificate files.

1. Download `certificate.pem` and `private_key.pem` from [Certificate Settings](https://teller.io/settings/certificates)
2. Move both files to `~/.sprig/certs/`
3. Verify `cert_path` and `key_path` in `config.yml` point to the right location

---

### "Authentication failed" or "Invalid token"

Your bank connection expired or was revoked. Run `sprig connect` again to reconnect.

Bank connections can expire for security, or if you changed your bank password.

---

### "Missing required config"

Your `config.yml` is missing `app_id`, `claude_key`, or access tokens.

1. Open `~/.sprig/config.yml` and fill in `app_id` and `claude_key`
2. Run `sprig connect` to get access tokens

---

### "ModuleNotFoundError" (Python install only)

```bash
cd /path/to/sprig
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e .
```

---

### API Rate Limits

Large transaction volumes may hit Claude API rate limits.

- Set `from_date` in `config.yml` to a more recent date to process fewer transactions
- Run `sprig sync` multiple times — it only processes uncategorized transactions
- Wait a few minutes between runs if you hit limits

---

**Still stuck?** Check [GitHub Issues](https://github.com/lukearmistead/sprig/issues) or create a new issue.

---

## FAQ

### Is my banking data secure?

**Yes.** Everything stays on your computer. Sprig uses Teller.io for secure bank connections with mTLS certificates. Your bank login credentials are only entered on your bank's official website.

### How much does it cost?

- **Sprig:** Free and open source
- **Teller.io:** Free tier includes 100 bank connections. [See teller.io](https://teller.io)
- **Claude API:** ~$0.10-0.50 per 1000 transactions. [See pricing](https://anthropic.com/pricing)

### What banks are supported?

Teller.io supports 5,000+ banks including Chase, Bank of America, Wells Fargo, Citi, credit unions, and online banks like Ally and Discover.

### Where is my data stored?

All Sprig data is in `~/.sprig/` (or `~/Documents/Sprig/` for standalone executables):

- **Database:** `sprig.db`
- **Exports:** `exports/`
- **Certificates:** `certs/`
- **Configuration & credentials:** `config.yml`

### Can I run this on a schedule?

Yes. Set up a cron job or Task Scheduler to run `sprig sync` automatically.

```
0 6 * * * /usr/local/bin/sprig sync
```
