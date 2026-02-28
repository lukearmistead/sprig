# 🌱 Sprig: Actually-personal personal finance

Sprig connects to your bank accounts, downloads your transactions locally, buckets them into customizable AI-powered categories, and exports it all into a CSV like this:

| id | date | description | amount | inferred_category | confidence | counterparty | account_name | account_subtype | account_last_four |
|----|------|-------------|--------|-------------------|------------|--------------|--------------|-----------------|-------------------|
| tx_abc123 | 2025-11-15 | SAFEWAY | -87.32 | groceries | 0.95 | Safeway | Checking | checking | 1234 |
| tx_abc124 | 2025-11-14 | SHELL GAS | -45.00 | transport | 0.92 | Shell | Credit Card | credit_card | 5678 |
| tx_abc125 | 2025-11-12 | REI | -142.50 | shopping | 0.94 | REI | Credit Card | credit_card | 5678 |

---

## Quickstart

### Step 1: Install Sprig

**Option A: Install via command line (Easiest)**

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/lukearmistead/sprig/main/scripts/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/lukearmistead/sprig/main/scripts/install.ps1 | iex
```

This downloads the latest binary to `~/.local/bin` and adds it to your PATH.

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
   - Extract and save `certificate.pem` and `private_key.pem` to `~/Documents/Sprig/certs/`
   - Get your **APP_ID** from [Application Settings](https://teller.io/settings/application)

2. **Anthropic** - Powers AI transaction categorization (required)
   - Go to [console.anthropic.com](https://console.anthropic.com) and create an account
   - Create an API key (starts with `sk-ant-api03-`)
   - **Cost:** ~$0.10-0.50 per 1000 transactions ([see pricing](https://platform.claude.com/docs/en/build-with-claude/batch-processing#pricing))

---

## Usage

### Running Sprig

```bash
sprig sync
```

Sprig guides you through setup automatically:
1. **First run:** Opens `~/Documents/Sprig/config.yml` — add your `app_id` and `claude_key`
2. **Second run:** Opens browser to connect your bank accounts
3. **After that:** Fetches, categorizes, and exports your transactions

Your transactions are exported to `~/Documents/Sprig/exports/transactions-YYYY-MM-DD.csv`.

```
Fetching transactions from Teller
Categorizing 47 transaction(s) using Claude AI
Exported 47 transaction(s) to ~/Documents/Sprig/exports/transactions-2025-11-17.csv
Add another bank account? [y/N]
```

### Categorization

Sprig uses Claude AI to categorize each transaction into one of your configured categories. Each transaction gets a category, a confidence score, and a counterparty name.

To manually override a specific transaction, add it to `manual_categories` in your config:

```yaml
manual_categories:
  - transaction_id: txn_abc123
    category: dining
```

Manual overrides are applied before AI categorization and always take precedence.

### Recategorization

After improving your categories in `~/Documents/Sprig/config.yml`, re-categorize transactions by:

1. **Delete the database and re-sync:**
   ```bash
   rm ~/Documents/Sprig/sprig.db
   sprig sync
   ```

2. **Or manually clear categories:** Use a SQLite tool to set `inferred_category` to NULL for transactions you want recategorized, then run `sprig categorize`.

---

### Customizing Your Categories

Edit `~/Documents/Sprig/config.yml` to customize categories using this format:

```yaml
categories:
  - name: your_category_name
    description: "Detailed description to help AI classify transactions"
  - name: another_category
    description: "Another description explaining what belongs here"
```

After changing categories, delete `~/Documents/Sprig/sprig.db` and re-sync to apply them.
