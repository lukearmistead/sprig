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

1. **Clone the repository**
   ```bash
   git clone https://github.com/lukearmistead/sprig.git
   cd sprig
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure your credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials (see setup guide below)
   ```

4. **Run your first sync**
   ```bash
   python sprig.py sync
   ```

5. **Export to CSV**
   ```bash
   python sprig.py export
   ```

Your transactions will be exported to `exports/transactions-YYYY-MM-DD.csv`!

---

## 🔧 Detailed Setup

### Getting Teller.io Credentials

1. **Create a Teller Developer Account**
   - Sign up at [teller.io](https://teller.io)
   - Create a new application in the dashboard
   - Note your `APP_ID` from the application settings

2. **Download Certificates**
   - Download the certificate and private key files from your Teller dashboard
   - Place them in the `certs/` directory:
     ```
     certs/
     ├── certificate.pem
     └── private_key.pem
     ```

3. **Get Access Tokens**

   **Option A: Using Built-in Auth (Recommended)**
   ```bash
   python sprig.py auth
   ```
   This opens a browser window where you can connect your bank accounts. Access tokens are automatically saved to your `.env` file.

   **Option B: Manual Token Setup**
   - Use Teller's demo tools or Connect widget to authenticate
   - Copy the access tokens and add them to your `.env` file

### Configure Environment Variables

Edit your `.env` file with your credentials:

```env
# Teller.io Configuration
APP_ID=your_teller_app_id_here
ACCESS_TOKENS=token1,token2,token3
CERT_PATH=certs/certificate.pem
KEY_PATH=certs/private_key.pem

# Claude AI (Optional - for transaction categorization)
CLAUDE_API_KEY=sk-ant-api03-your_key_here

# Database
DATABASE_PATH=sprig.db
ENVIRONMENT=development
```

### Claude API Key (Optional)

For AI categorization, get an API key from [console.anthropic.com](https://console.anthropic.com) and add as `CLAUDE_API_KEY` in `.env`. Without this, transactions sync but aren't categorized.

---

## 📖 Usage

### Available Commands

**Sync transactions and categorize**
```bash
python sprig.py sync
```
Downloads new transactions from all connected accounts and categorizes them using Claude AI.

**Export to CSV**
```bash
python sprig.py export
```
Exports all transactions to a CSV file in the `exports/` directory.

**Export to custom location**
```bash
python sprig.py export -o /path/to/my-transactions.csv
```

**Authenticate new bank accounts**
```bash
python sprig.py auth
```
Opens a browser to connect additional bank accounts via Teller Connect.

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
**Authentication failures:** Re-run `python sprig.py auth` for fresh tokens  
**Claude API errors:** Check API key starts with `sk-ant-` (categorization is optional)  
**Import errors:** Activate virtual environment: `source venv/bin/activate`

Need help? Check [GitHub Issues](https://github.com/lukearmistead/sprig/issues) or [Teller.io Docs](https://teller.io/docs)

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
