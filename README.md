# 🌱 Sprig

Sprig is a lightweight Python CLI tool that securely connects to your bank accounts via [Teller.io](https://teller.io), downloads your transaction data, and exports it to CSV files with intelligent categorization powered by Claude.

## ✨ Key Features

- 🏦 **Secure Bank Connection** - Connect to 5,000+ banks via Teller.io's secure API
- 🤖 **AI-Powered Categorization** - Automatically categorize transactions using Claude AI
- 📊 **CSV Export** - Export your data to CSV for analysis in Excel, Google Sheets, or other tools
- 🔒 **Privacy First** - All data stored locally in SQLite
- 🛠️ **Developer Friendly** - Clean Python codebase with comprehensive tests

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- A [Teller.io developer account](https://teller.io) (free)
- [Claude API key](https://console.anthropic.com) (optional, for categorization)

### Installation

```bash
git clone https://github.com/lukearmistead/sprig.git
cd sprig
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Setup

```bash
# 1. Configure your Teller APP_ID and Claude API key
cp .env.example .env
# Edit .env with your credentials

# 2. Download certificates from Teller dashboard to certs/ directory
# 3. Connect your bank accounts
python sprig.py auth

# 4. Sync and export your data
python sprig.py sync
python sprig.py export
```

Your transactions will be exported to `exports/transactions-YYYY-MM-DD.csv`!

---

## 🔧 Configuration

### Teller.io Setup

1. **Create a Teller Developer Account**
   - Sign up at [teller.io](https://teller.io)
   - Create a new application in the dashboard
   - Note your `APP_ID` from the application settings
   - Download certificate and private key files to `certs/` directory

2. **Environment Variables**

Edit your `.env` file:

```env
# Teller.io Configuration
APP_ID=your_teller_app_id_here
CERT_PATH=certs/certificate.pem
KEY_PATH=certs/private_key.pem

# Claude AI (Optional - for transaction categorization)
CLAUDE_API_KEY=sk-ant-api03-your_key_here

# Database
DATABASE_PATH=sprig.db
ENVIRONMENT=development
```

**Note**: `ACCESS_TOKENS` are automatically managed by the `auth` command.

---

## 📖 Commands

```bash
python sprig.py auth                               # Connect bank accounts
python sprig.py sync                               # Download and categorize transactions  
python sprig.py sync --recategorize                # Recategorize ALL transactions with updated AI
python sprig.py export                             # Export to CSV
python sprig.py export -o /path/to/file.csv        # Export to custom location
```

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

### Transaction Categories

Sprig uses Teller's official category system with enhanced descriptions:

- **dining** - Restaurants, cafes, food delivery
- **groceries** - Supermarkets, food stores
- **fuel** - Gas stations, vehicle fuel
- **transport** - Public transit, rideshares
- **entertainment** - Movies, concerts, games
- **health** - Medical expenses, pharmacy
- **utilities** - Electricity, water, internet
- And 25+ more categories...

Categories can be customized in `config.yml`.

### CSV Output Format

The exported CSV includes these columns:
- Transaction ID, Account ID, Amount, Description, Date
- Transaction Type, Status, Running Balance
- **inferred_category** - AI-categorized transaction type
- Raw transaction details and metadata

---

## 👨‍💻 Developer Guide

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
1. Fork repo → create feature branch → add tests → submit PR
2. Follow functional programming style with type safety
3. See "good first issue" labels for beginner tasks

---

## 🔒 Security & Privacy

- **Local storage only** - SQLite database, no cloud storage
- **Certificates** - Store in `certs/` directory, never commit to git
- **Environment files** - Add `.env`, `certs/`, and `sprig.db` to `.gitignore`

---

## 🆘 Troubleshooting

**Certificate errors:** Download certificates from Teller dashboard to `certs/` directory  
**Authentication failures:** Re-run `python sprig.py auth`  
**Import errors:** Activate virtual environment: `source venv/bin/activate`

Need help? Check [GitHub Issues](https://github.com/lukearmistead/sprig/issues)

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Teller.io](https://teller.io) - Secure bank connectivity
- [Anthropic Claude](https://claude.ai) - AI-powered transaction categorization
- The open source community for excellent Python libraries

---

<div align="center">
  <sub>Built with ❤️ for financial transparency and data ownership</sub>
</div>
