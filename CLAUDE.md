# Sprig Development Guide

## Philosophy

User-controlled finance tool. Local-first, no cloud. CLI only, no UI. Flexibility over automation.

**Anti-patterns**: No budgeting features, no complex abstractions, no prescriptive automation.

## Module Ownership

| Feature | Module | Test File |
|---------|--------|-----------|
| Credentials | `credentials.py` | `test_credentials.py` |
| Bank OAuth | `auth.py` | `test_auth.py` |
| API calls | `teller_client.py` | `test_teller_client.py` |
| Data storage | `database.py` | `test_database.py` |
| Fetching | `fetch.py` | `test_fetch.py` |
| Sync logic | `sync.py` | `test_sync.py`, `test_sync_counting.py` |
| Categorization | `categorizer.py` | `test_categorizer.py`, `test_categorizer_error_handling.py` |
| CSV export | `export.py` | `test_export.py` |
| Data models | `models/*.py` | `test_models.py`, `test_claude_models.py` |
| CLI models | `models/cli.py` | `test_cli_models.py` |
| Logging | `logger.py` | `test_logger.py` |
| Manual overrides | `models/category_config.py` | `test_manual_overrides.py` |
| CLI | `sprig.py` | `test_cli.py` |

## Naming Conventions
```
fetch_*      # Gets from external API
save_*       # Writes to database
sync_*       # Orchestrates fetch + save
validate_*   # Checks data integrity
export_*     # Writes to file system
```

## Patterns

- Use Pydantic models (`TellerTransaction`, `TellerAccount`) for all API data
- Duplicate detection via primary key, not content matching
- Rate limits: exponential backoff for Teller, 60s pause for Claude
- Address the user with the surname Sprigly like "Sprigly" or "{first name} Sprigly" if you have their first name

## Guidelines

- Use the python virtual environment rather than reinstalling all dependencies
