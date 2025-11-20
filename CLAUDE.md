# CLAUDE.md - Sprig Development Guide

This file guides Claude when working on Sprig - "Actually-personal personal finance"

## Quick Start Checklist
- [ ] Run tests before any change: `python -m pytest tests/`
- [ ] Check module ownership map below before creating files
- [ ] Write failing test first (see Testing Patterns)
- [ ] Implement in existing module when possible
- [ ] Run full test suite before committing

## Sprig Philosophy & Context

**Core Vision**: User-controlled finance tool that prioritizes flexibility over prescriptive automation. Users own their data locally and define their own categories.

**Current Focus**: Solving duplicate account issues from re-authentication using fingerprinting (institution_id + account_type + last4).

**Anti-patterns to Avoid**:
- No UI (pure CLI tool)
- No budgeting features (user control > automation)
- No cloud storage (local SQLite only)
- No complex abstractions (simple functions > frameworks)

## Module Ownership Map

| Feature | Primary Module | Secondary | Test File | When to Extend Here |
|---------|---------------|-----------|-----------|---------------------|
| Bank OAuth | `auth.py` | - | `test_auth.py` | Teller Connect, token management |
| API calls | `teller_client.py` | - | `test_teller_client.py` | mTLS, HTTP requests, retries |
| Data storage | `database.py` | - | `test_database.py` | Schema, CRUD, SQL queries |
| Sync logic | `sync.py` | `database.py` | `test_sync.py` | Orchestration, duplicate detection |
| Categorization | `categorizer.py` | - | `test_categorizer.py` | Claude API, prompts, batching |
| CSV export | `export.py` | `database.py` | `test_export.py` | File I/O, formatting |
| Data models | `models/*.py` | - | `test_models.py`, `test_claude_models.py` | Pydantic validation, types |
| Claude API | `models/claude.py` | - | `test_claude.py` | Claude response parsing |
| CLI | `sprig.py` | all modules | - | Commands, argument parsing |

**Decision Tree for New Code**:
```
Is it about...
├── Fetching from Teller? → teller_client.py
├── Storing/reading data? → database.py
├── Validating API response? → models/teller.py
├── Orchestrating sync? → sync.py
├── AI categorization? → categorizer.py
└── New domain entirely? → Consider new module (rare!)
```

## Sprig-Specific Patterns

### Transaction Handling
```python
# ALWAYS use TellerTransaction for validation
from sprig.models.teller import TellerTransaction

def save_transaction(self, transaction: TellerTransaction, account_id: str) -> bool:
    """Save transaction if not duplicate. Returns True if saved."""
    # Check for duplicates via primary key
    existing = self.connection.execute(
        "SELECT id FROM transactions WHERE id = ?",
        (transaction.id,)
    ).fetchone()

    if existing:
        return False

    # Insert with all Teller fields preserved
    self.connection.execute("""
        INSERT INTO transactions (
            id, account_id, amount, date, description,
            status, details, type, running_balance, inferred_category
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        transaction.id, account_id, transaction.amount,
        transaction.date, transaction.description,
        transaction.status, transaction.details,
        transaction.type, transaction.running_balance, None  # inferred_category added later by categorizer
    ))
    return True
```

### Account Fingerprinting (Current Problem)
```python
# How we're solving duplicate accounts from re-auth
def get_account_fingerprint(account: TellerAccount) -> str:
    """Create stable identifier across re-enrollments."""
    return f"{account.institution.id}:{account.type}:{account.last_four}"

def find_or_create_account(self, account: TellerAccount) -> str:
    """Return account_id, reusing existing if fingerprint matches."""
    fingerprint = get_account_fingerprint(account)

    # Check for existing account with same fingerprint
    existing = self.connection.execute(
        "SELECT id FROM accounts WHERE fingerprint = ?",
        (fingerprint,)
    ).fetchone()

    if existing:
        return existing[0]

    # Create new account with fingerprint
    return self.create_account(account, fingerprint)
```

### API Error Handling
```python
# Teller API pattern (rate limits, mTLS)
def fetch_with_retry(self, endpoint: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            response = self.session.get(
                f"{self.base_url}/{endpoint}",
                cert=(self.cert_path, self.key_path),
                timeout=30
            )

            if response.status_code == 429:  # Rate limited
                time.sleep(2 ** attempt)  # Exponential backoff
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.SSLError as e:
            raise ConfigError(f"mTLS cert issue: {e}")

    raise TellerAPIError(f"Max retries exceeded for {endpoint}")

# Claude API pattern (batch processing with rate limit handling)
def categorize_transactions(self, transactions: List[TellerTransaction]) -> Dict:
    """Categorize in configurable batches with rate limit handling.

    Returns:
        dict: Maps transaction_id to (category, confidence) tuple
              e.g., {"txn_123": ("dining", 0.95), "txn_124": ("groceries", 0.88)}
    """
    batch_size = self.config.get('batch_size', 10)  # Reduced default
    results = {}

    for i in range(0, len(transactions), batch_size):
        batch = transactions[i:i + batch_size]
        try:
            response = self.claude_client.categorize(batch)
            results.update(response)
        except Exception as e:
            error_str = str(e)

            # Handle rate limits with longer delays
            if "rate_limit_error" in error_str or "rate limit" in error_str.lower():
                logger.warning(f"⏳ Hit API rate limit - waiting 60 seconds...")
                time.sleep(60)
                # Retry once with longer delay
                try:
                    response = self.claude_client.categorize(batch)
                    results.update(response)
                except Exception:
                    # Give up on this batch to preserve progress
                    logger.error(f"Rate limit persists, skipping batch {i}")
            else:
                # Non-rate-limit errors: mark as ('general', low confidence)
                logger.warning(f"Batch {i} failed: {e}")
                for txn in batch:
                    results[txn.id] = ('general', 0.5)

    return results
```

## Testing Patterns for Sprig

### Test Structure Template
```python
# tests/test_feature.py
import pytest
from unittest.mock import Mock, patch
from sprig.feature import function_under_test

class TestFeatureName:
    """Group related tests in classes."""

    @pytest.fixture
    def mock_database(self):
        """Reusable test fixtures."""
        db = Mock()
        db.fetch_transactions.return_value = [
            TellerTransaction(id="tx_123", amount=-25.00, ...)
        ]
        return db

    def test_should_describe_expected_behavior(self, mock_database):
        """Test names are specifications."""
        # Arrange
        expected_category = "dining"

        # Act
        result = function_under_test(mock_database)

        # Assert
        assert result.category == expected_category
```

### Mocking External Services
```python
# Mock Teller API
@patch('sprig.teller_client.requests.get')
def test_fetch_accounts_handles_rate_limit(mock_get):
    # Simulate 429 then success
    mock_get.side_effect = [
        Mock(status_code=429),
        Mock(status_code=200, json=lambda: {"accounts": []})
    ]

    client = TellerClient(config)
    accounts = client.fetch_accounts()

    assert mock_get.call_count == 2  # Retried once
    assert accounts == []

# Mock Claude API with rate limit handling
@patch('sprig.categorizer.anthropic.Anthropic')
def test_categorize_handles_rate_limits(mock_claude):
    # Simulate rate limit error
    mock_claude.return_value.messages.create.side_effect = Exception("rate_limit_error: Too many requests")

    categorizer = Categorizer(config)
    
    # Should raise exception to stop categorization (not fallback)
    with pytest.raises(Exception, match="rate_limit_error"):
        categorizer.categorize_batch([transaction])

@patch('sprig.categorizer.anthropic.Anthropic')  
def test_categorize_handles_other_api_errors(mock_claude):
    mock_claude.return_value.messages.create.side_effect = Exception("Network error")

    categorizer = Categorizer(config)
    result = categorizer.categorize_batch([transaction])

    # Should return empty dict on non-rate-limit errors
    assert result == {}

# Use real SQLite for database tests
def test_database_prevents_duplicates(tmp_path):
    db_path = tmp_path / "test.db"
    db = SprigDatabase(db_path)

    transaction = TellerTransaction(id="tx_123", ...)

    # First insert succeeds
    assert db.save_transaction(transaction, "acc_1") == True

    # Duplicate fails
    assert db.save_transaction(transaction, "acc_1") == False
```

### Test Data Fixtures
```python
# tests/fixtures.py
def sample_teller_account():
    return {
        "id": "acc_test123",
        "institution": {"id": "chase", "name": "Chase"},
        "name": "Checking",
        "type": "checking",
        "subtype": "checking",
        "last_four": "1234",
        "balance": {"current": 1000.00}
    }

def sample_transaction():
    return {
        "id": "tx_test456",
        "account_id": "acc_test123",
        "amount": -25.50,
        "description": "COFFEE SHOP SF",
        "date": "2024-01-15",
        "type": "card_payment",
        "status": "posted",
        "details": {"counterparty": {"name": "Corner Coffee"}}
    }

def sample_transaction_view():
    """Complete transaction data for categorization."""
    from sprig.models import TransactionView
    return TransactionView(
        id="tx_test456",
        date="2024-01-15",
        description="COFFEE SHOP SF",
        amount=-25.50,
        inferred_category=None,
        confidence=None,  # Set after categorization
        counterparty="Corner Coffee",
        account_name="Checking",
        account_subtype="checking",
        account_last_four="1234"
    )

def sample_uncategorized_db_row():
    """Database row format from get_uncategorized_transactions()."""
    return (
        "tx_test456",      # id
        "COFFEE SHOP SF",  # description
        -25.50,            # amount
        "2024-01-15",      # date
        "card_payment",    # type
        "acc_test123",     # account_id
        "Checking",        # account name
        "checking",        # account subtype
        "Corner Coffee",   # counterparty
        "1234"             # last_four
    )
```

## Current Implementation Status

### Working Features ✅
- Teller OAuth flow via browser
- mTLS authentication with certificates
- Transaction sync with duplicate prevention
- Claude categorization with batch processing and rate limit handling
- CSV export with timestamps and account details
- Configurable batch sizes for API cost management
- Date-filtered syncing with --days parameter

### Active Problems 🔧
1. **Duplicate Accounts**: Re-authentication creates new account IDs
   - Solution: Fingerprinting with (institution_id, type, last4)
   - Status: Design documented, implementation pending

2. **Category Optimization**: Ongoing improvements to categorization accuracy
   - Current: 14 categories in `config.yml`
   - Recent: Added account context (name, subtype, last4) to categorization
   - Recent: Enhanced TransactionView model with all relevant fields
   - Recent: Added confidence scoring (0-1) to identify uncertain categorizations

### Recent Improvements ✨
- **Confidence Scoring**: AI provides 0-1 confidence score for each categorization; sort by confidence in CSV to review uncertain transactions
- **Category Overrides**: Override miscategorized transactions in `config.yml` for persistence across syncs
- **Rate Limit Handling**: Intelligent retry logic with longer delays for API limits
- **Configurable Batch Sizes**: `--batch-size` parameter for API cost management
- **Enhanced Context**: Account details (name, subtype, last4) included in categorization
- **Better Logging**: Clear rate limit messages and user guidance
- **Progress Preservation**: Sync succeeds even if categorization hits limits

### Not Implemented Yet ❌
- `--full` flag for complete resync
- Account fingerprinting for duplicate prevention

## Clean Code Principles Applied

### Single Responsibility
```python
# Good: Each function has ONE job
def fetch_accounts(self, token: str) -> List[TellerAccount]:
    """Only fetches accounts from API."""

def save_accounts(self, accounts: List[TellerAccount]) -> None:
    """Only saves accounts to database."""

def sync_accounts(self, token: str) -> None:
    """Orchestrates fetch + save."""
    accounts = self.fetch_accounts(token)
    self.save_accounts(accounts)
```

### Meaningful Names
```python
# Sprig conventions
fetch_*      # Gets from external API
save_*       # Writes to database
sync_*       # Orchestrates fetch + save
validate_*   # Checks data integrity
export_*     # Writes to file system
```

### Small Functions (5-20 lines)
```python
# Extract complex logic into helpers
def categorize_transaction(self, txn: TellerTransaction) -> str:
    prompt = self._build_prompt(txn)
    response = self._call_claude(prompt)
    return self._validate_category(response)

def _build_prompt(self, txn: TellerTransaction) -> str:
    return f"Categorize: {txn.description} ${txn.amount}"

def _validate_category(self, category: str) -> str:
    return category if category in VALID_CATEGORIES else 'general'
```

## Configuration & Secrets

### Required `.env` Structure
```bash
# Teller Configuration
APP_ID=app_xxx
ACCESS_TOKENS=test_tok_xxx,test_tok_yyy  # Comma-separated
CERT_PATH=certs/certificate.pem
KEY_PATH=certs/private_key.pem

# Claude Configuration
ANTHROPIC_API_KEY=sk-ant-xxx

# Optional
DATABASE_PATH=sprig.db  # Defaults to ./sprig.db
EXPORT_DIR=exports      # Defaults to ./exports
```

### Category Configuration (`config.yml`)
```yaml
# Sprig Transaction Categories Configuration
# This file defines the 14 categories used for transaction classification.
categories:
  - name: dining
    description: "Restaurants, bars, cafes, food delivery, and any prepared food or drinks consumed outside the home"
  - name: groceries
    description: "Supermarkets, food stores, household essentials, and anything you consume or use at home"
  - name: transport
    description: "Gas, fuel, parking, tolls, rideshares, public transit, car insurance, maintenance, and local transportation"
  - name: travel
    description: "Flights, hotels, vacation rentals, car rentals, and expenses specifically for trips away from home"
  - name: shopping
    description: "Clothing, electronics, furniture, books, sporting goods, and general retail purchases"
  - name: home
    description: "Rent, mortgage, property taxes, home insurance, repairs, maintenance, and core housing costs"
  - name: utilities
    description: "Electricity, gas, water, trash, internet, phone bills, and essential home services"
  - name: health
    description: "Medical care, pharmacy, dental, vision, therapy, health insurance, gym memberships, and wellness"
  - name: entertainment
    description: "Movies, concerts, streaming services, games, hobbies, ski passes, and leisure activities"
  - name: income
    description: "Salary, refunds, cash back, reimbursements, and any money flowing into your accounts"
  - name: savings
    description: "Investments, retirement contributions, transfers to savings, and building wealth for the future"
  - name: general
    description: "Bank fees, charitable donations, gifts, professional services, and anything that doesn't fit elsewhere"
  - name: transfers
    description: "Credit card payments, loan payments, interest charges, account transfers, and internal money movements between your accounts"
  - name: undefined
    description: "Truly unclassifiable transactions with unclear merchants or purposes that cannot be determined from available information"
```

## Development Workflow

### Adding New Functionality
1. **Check module ownership map** - Where does this belong?
2. **Write failing test** with expected behavior
3. **Check existing patterns** in that module
4. **Implement minimally** to pass test
5. **Refactor** if needed
6. **Update CLAUDE.md** if patterns change

### Before Creating New Files
Ask:
- Is this a new domain or extension of existing?
- Would this exceed 300 lines in existing module?
- Does this require new dependencies?

Only create new modules for genuinely orthogonal concerns.

### Debugging Checklist
- [ ] Verify `.env` has all required keys
- [ ] Check certificate paths are absolute
- [ ] Run with `--verbose` flag for detailed logs
- [ ] Check `sprig.db` with sqlite3 CLI
- [ ] Verify Teller token with: `curl -H "Authorization: Bearer $TOKEN"`
- [ ] Test Claude key with simple prompt

## When In Doubt

1. **Does this already exist?** Check module map
2. **Can I extend existing code?** Usually yes
3. **Is there a test for this?** Write one first
4. **Is this the simplest solution?** Refactor if not
5. **Does this match Sprig's philosophy?** User control > automation
6. **Would Luke approve?** Keep it pragmatic, not enterprise-y

## Common Commands Reference

```bash
# Development
python -m pytest tests/ -v           # Run all tests verbose
python -m pytest tests/ -k "category" # Run tests matching "category"
python -m pytest --cov=sprig         # Coverage report
ruff check .                          # Linting and code formatting

# Usage
python sprig.py auth                 # Authenticate banks
python sprig.py sync                 # Sync + categorize
python sprig.py sync --days 7        # Sync recent transactions only
python sprig.py sync --batch-size 5  # Gentler API usage (default: 10)
python sprig.py sync --recategorize  # Clear and recategorize all
python sprig.py export               # Export to CSV with account context
python sprig.py sync && python sprig.py export  # Full workflow

# Category overrides (edit config.yml):
# category_overrides:
#   - transaction_id: txn_abc123
#     category: dining
# Then run: python sprig.py sync

# Rate limit management strategies
python sprig.py sync --days 1 --batch-size 5   # Very conservative
python sprig.py sync --days 7                  # Recent transactions
python sprig.py sync                           # Resume categorization

# Debugging
sqlite3 sprig.db "SELECT * FROM transactions LIMIT 10;"
sqlite3 sprig.db "SELECT DISTINCT inferred_category FROM transactions;"
python -c "from sprig.config import Config; Config().validate()"
```
