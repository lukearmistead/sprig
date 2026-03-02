# 🌱 Sprig: Actually-personal personal finance

Sprig downloads transactions from all of your bank accounts, categorizes them with AI, and exports a CSV:

| date | description | amount | ✨ inferred_category | confidence | counterparty | account_name | account_last_four |
|------|-------------|--------|----------------------|------------|--------------|--------------|-------------------|
| 2025-11-15 | SAFEWAY | -87.32 | groceries | 0.95 | Safeway | Checking | 1234 |
| 2025-11-14 | SHELL GAS | -45.00 | transport | 0.92 | Shell | Credit Card | 5678 |
| 2025-11-12 | REI | -142.50 | shopping | 0.94 | REI | Credit Card | 5678 |

You define the categories. The AI applies them and can only use categories you wrote.

```yaml
categories:
  - name: groceries
    description: "Food and household supplies from grocery stores"
  - name: transport
    description: "Gas, parking, rideshares, public transit"
  - name: dining
    description: "Restaurants, coffee shops, bars, food delivery"
```

## Quickstart

### Step 1: Install Sprig

**macOS / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/lukearmistead/sprig/main/scripts/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/lukearmistead/sprig/main/scripts/install.ps1 | iex
```

**Or install from source:** `git clone https://github.com/lukearmistead/sprig.git && cd sprig && pip install -e .`

### Step 2: Set up your accounts

You'll need two free services:

1. **[Teller.io](https://teller.io)** - Connects to your bank accounts
   - Create a developer account and a new application
   - [Download your certificate](https://teller.io/settings/certificates) and drag `certificate.pem` and `private_key.pem` into the `~/Documents/Sprig/certs/` folder that Sprig opens for you
   - Copy your **APP_ID** from [Application Settings](https://teller.io/settings/application) and paste it into the config

2. **[Anthropic](https://console.anthropic.com)** - Powers AI categorization
   - Create an account and generate an API key, then paste it into the config
   - Cost: ~$0.10–0.50 per 1,000 transactions

### Step 3: Connect and sync

```bash
sprig sync
```

On first run, Sprig:
1. Opens your config file and certs folder for you to paste in keys and certificates
2. Opens your browser to connect your bank accounts
3. Fetches, categorizes, and exports your transactions

From now on, just run `sprig sync` whenever you want fresh data.

```
Fetching transactions from Teller
Categorizing 47 transaction(s) using Claude AI
Exported 47 transaction(s) to ~/Documents/Sprig/exports/transactions-2025-11-17.csv
```

## Configuration

### Manual overrides

To override a specific transaction's category, add it to your config:

```yaml
manual_categories:
  - transaction_id: txn_abc123
    category: dining
```

Manual overrides always take precedence over AI categorization.

### Recategorization

After changing your categories, delete `~/Documents/Sprig/sprig.db` and run `sprig sync` to recategorize all transactions.
