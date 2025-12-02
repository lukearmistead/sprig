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

**Anti-patterns to Avoid**:
- No UI (pure CLI tool)
- No budgeting features (user control > automation)
- No cloud storage (local SQLite only)
- No complex abstractions (simple functions > frameworks)

## Module Ownership Map

| Feature | Primary Module | Secondary | Test File | When to Extend Here |
|---------|---------------|-----------|-----------|---------------------|
| Credentials | `credentials.py` | - | `test_credentials.py` | Keyring storage, migration, credential access |
| Bank OAuth | `auth.py` | `credentials.py` | `test_auth.py` | Teller Connect, token management |
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

### Gap-Filling Transaction Syncing
```python
# Sprig intelligently fills gaps in transaction history to minimize API calls
def sync_transactions_for_account(...):
    """Sync transactions using gap-filling strategy.

    Desired window: from_date (or earliest existing) to yesterday
    Only fetches missing ranges:
    1. Gap before earliest transaction (if from_date < earliest)
    2. Gap after latest transaction (if latest < yesterday)
    """
    if full:
        # Full sync: fetch everything
        transactions = client.get_transactions(token, account_id)
    else:
        # Find gaps in the desired window
        earliest_db, latest_db = db.get_transaction_date_range(account_id)
        yesterday = (datetime.now() - timedelta(days=1)).date()
        window_start = cutoff_date if cutoff_date else earliest_db

        if earliest_db is None:
            # No existing data: fetch from window_start to yesterday
            transactions = client.get_transactions(token, account_id, window_start)
        else:
            transactions = []

            # Gap 1: Fill before earliest (if needed)
            if window_start and window_start < earliest_db:
                early_txns = client.get_transactions(token, account_id, window_start)
                early_txns = [t for t in early_txns if date.fromisoformat(t['date']) < earliest_db]
                transactions.extend(early_txns)

            # Gap 2: Fill after latest (if needed)
            if latest_db < yesterday:
                late_txns = client.get_transactions(token, account_id, latest_db)
                transactions.extend(late_txns)

    for transaction_data in transactions:
        db.insert_record("transactions", TellerTransaction(**transaction_data).model_dump())
```

**Key Benefits:**
- Only fetches missing transaction ranges
- Reduces Teller API calls by ~95% on subsequent syncs
- Handles backfill (from_date before earliest) and updates (after latest)
- Reduces token usage (fewer transactions to categorize)

**Database Method:**
```python
def get_transaction_date_range(self, account_id: str):
    """Get earliest and latest transaction dates for an account."""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute(
            "SELECT MIN(date), MAX(date) FROM transactions WHERE account_id = ?",
            (account_id,)
        )
        min_date, max_date = cursor.fetchone()
        if min_date and max_date:
            return date.fromisoformat(min_date), date.fromisoformat(max_date)
        return None, None
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
- Secure credential storage via system keyring
- Teller OAuth flow via browser
- mTLS authentication with certificates
- Gap-filling transaction sync (only fetches missing date ranges)
- Transaction sync with duplicate prevention
- `--full` flag for complete resync when needed
- Automatic backfill and forward-fill of transaction gaps
- Date-filtered syncing with --from-date parameter
- CSV export with timestamps and account details
- Configurable batch sizes for API cost management
- Manual category overrides in config.yml
- Confidence scoring for AI categorizations

### Not Implemented Yet ❌
- Account fingerprinting for duplicate prevention

## Simplified Credential Management Patterns

### DRY Configuration Pattern
```python
# sprig/credentials.py - Data-driven credential management
CREDENTIALS = {
    "app_id": TellerAppId,           # Validates with Pydantic model
    "claude_api_key": ClaudeAPIKey,  # Validates with Pydantic model  
    "cert_path": CertPath,           # Validates with Pydantic model
    "key_path": KeyPath,             # Validates with Pydantic model
    "access_tokens": None,           # No validation model
    "database_path": None,           # No validation model
    "environment": Environment,      # Validates with Pydantic model
}

def store_credential(key: str, value: str) -> bool:
    """Store credential with automatic validation."""
    if not value:
        return True
    
    # Use Pydantic validation if available
    model_class = CREDENTIALS.get(key)
    if model_class:
        model_class(value=value)  # Let ValidationError propagate
    
    keyring.set_password(SERVICE_NAME, key, value)
    return True
```

### Clean Function Interfaces
```python
# sprig/credentials.py - Clean API instead of global imports
def set_app_id(app_id: str) -> bool:
    """Set Teller APP_ID with validation."""
    return store_credential(KEY_APP_ID, app_id)

def set_claude_api_key(api_key: str) -> bool:
    """Set Claude API key with validation."""
    return store_credential(KEY_CLAUDE_API_KEY, api_key)

def get_claude_api_key() -> Optional[ClaudeAPIKey]:
    """Get validated Claude API key."""
    raw = get(KEY_CLAUDE_API_KEY)
    return ClaudeAPIKey(value=raw) if raw else None
```

### Simplified Auth Flow
```python
# sprig.py - Single function handles all credential setup
def setup_credentials() -> bool:
    """Setup or update credentials with user-friendly prompts."""
    # Get current values
    current_app_id = credentials.get_app_id()
    current_claude_key = credentials.get_claude_api_key()
    
    # Show current values with masking
    app_id_prompt = f"Teller APP_ID (current: {current_app_id.value if current_app_id else 'none'}): "
    claude_prompt = f"Claude API Key (current: {credentials.mask(current_claude_key.value if current_claude_key else None, 12)}): "
    
    # Allow keeping existing values
    app_id = input(app_id_prompt).strip() or (current_app_id.value if current_app_id else None)
    claude_key = input(claude_prompt).strip() or (current_claude_key.value if current_claude_key else None)
    
    # Validate and store (Pydantic errors propagate)
    credentials.set_app_id(app_id)
    credentials.set_claude_api_key(claude_key)
    
    return True
```

### Mandatory Claude API Key
```python
# sprig/sync.py - Simplified logic, no graceful fallback
def sync_all_accounts(recategorize: bool = False, from_date: str = None, batch_size: int = 10):
    """Sync all accounts. Claude API key is mandatory."""
    # Fail fast if Claude not configured
    try:
        claude_categorizer = ClaudeCategorizer()
    except ValueError as e:
        logger.error(f"Claude API key is required: {e}")
        logger.error("Run 'python sprig.py auth' to set up credentials")
        raise ValueError("Claude API key not configured")
    
    # Continue with sync knowing Claude is available
    categorize_uncategorized_transactions(claude_categorizer, batch_size)
```

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

### Credential Storage

Sprig stores credentials securely in your system keyring:
- **macOS**: Keychain
- **Linux**: Secret Service (GNOME Keyring, KWallet)  
- **Windows**: Credential Locker

**Simple setup flow**: `sprig auth` prompts for credentials, shows current values, and validates automatically:
- **Teller APP_ID** (format: `app_xxx` with 21 characters after prefix)
- **Claude API Key** (format: `sk-ant-api03-xxx` with 95 characters after prefix)
- **Certificate paths** (defaults to `certs/certificate.pem` and `certs/private_key.pem`)

**User-friendly features**:
- Shows current credential values with security masking
- Press Enter to keep existing values  
- Automatic format validation with clear error messages
- Bank access tokens added automatically during OAuth

### Category Configuration (`config.yml`)
```yaml
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

# Manual category overrides (optional)
manual_categories:
  - transaction_id: txn_abc123
    category: dining
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
- [ ] Run `sprig auth` to verify credentials (shows current values with masking)
- [ ] Check certificate files exist in `certs/` folder
- [ ] Verify credential formats automatically validated by Pydantic
- [ ] Check `sprig.db` with sqlite3 CLI for data issues
- [ ] Test Teller connectivity with existing access tokens
- [ ] Verify Claude API key works (mandatory for categorization)

## When In Doubt

1. **Does this already exist?** Check module map
2. **Can I extend existing code?** Usually yes
3. **Is there a test for this?** Write one first
4. **Is this the simplest solution?** Refactor if not
5. **Can I use existing patterns?** DRY configuration, clean function interfaces, Pydantic validation
6. **Does this match Sprig's philosophy?** User control > automation, simplicity > enterprise complexity
7. **Would Luke approve?** Keep it pragmatic and readable

## Common Commands Reference

```bash
# Development
python -m pytest tests/ -v           # Run all tests verbose
python -m pytest tests/ -k "category" # Run tests matching "category"
python -m pytest --cov=sprig         # Coverage report
ruff check .                          # Linting and code formatting

# Usage
python sprig.py auth                             # Setup credentials and authenticate banks
python sprig.py sync                             # Gap-filling sync (fetches only missing date ranges)
python sprig.py sync --full                      # Full resync (fetch all transactions, useful for first run)
python sprig.py sync --from-date 2024-11-01     # Backfill from specific date and forward-fill to yesterday
python sprig.py sync --batch-size 5              # Gentler API usage (default: 10)
python sprig.py sync --recategorize              # Clear and recategorize all transactions
python sprig.py export                           # Export to CSV
python sprig.py export -o my-transactions.csv    # Export to custom file

# Full workflow
python sprig.py sync && python sprig.py export

# Manual category overrides (edit config.yml):
# manual_categories:
#   - transaction_id: txn_abc123
#     category: dining
# Then run: python sprig.py sync

# Rate limit management strategies
python sprig.py sync --from-date 2024-11-01 --batch-size 5   # Very conservative
python sprig.py sync --from-date 2024-11-01                  # Recent transactions only
python sprig.py sync                                         # Resume categorization

# Debugging
sqlite3 sprig.db "SELECT * FROM transactions LIMIT 10;"
sqlite3 sprig.db "SELECT DISTINCT inferred_category FROM transactions;"
python -c "from sprig import credentials; print(credentials.get_app_id())"
```
