# Database Transaction Scoping Fix Plan

## Problem Statement

The codebase has a critical scoping issue with database cursor variables (`csr`) in multiple functions. The error "cannot access local variable 'csr' where it is not associated with a value" occurs when exceptions happen before cursor creation, causing the variable to be undefined in exception handlers.

## Root Cause

The problematic pattern appears throughout `UpdateDatabase.py`:

```python
try:
    csr = db_conn.cursor()  # Variable assigned here
    csr.execute("begin")
    # ... processing code ...
except Exception as error:
    _handle_transaction_processing_error(csr, error, ...)  # csr might be undefined
```

If `db_conn.cursor()` fails or any exception occurs before this line, `csr` remains undefined when the except block tries to use it.

## Current Impact

- **Functions Affected**: 8+ functions with identical pattern
- **Error Manifestation**: Only occurs under specific failure conditions (database connection issues, memory problems)
- **Severity**: High - causes application crashes in production

## Solution Overview

Implement a database transaction context manager that:
1. Safely handles cursor creation
2. Manages transaction lifecycle
3. Provides consistent error handling
4. Eliminates scoping issues

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

#### 1.1 Create Database Transaction Context Manager

Add to `database_commands.py`:

```python
from contextlib import contextmanager

@contextmanager
def database_transaction_context(db_conn: sqlite3.Connection, logger: logging.Logger):
    """Context manager for database transactions with proper error handling."""
    csr = None
    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        yield csr
        csr.execute("end")
        db_conn.commit()
    except Exception as e:
        if csr:
            try:
                csr.execute("rollback")
            except Exception as rollback_error:
                logger.error(f"Failed to rollback transaction: {rollback_error}")
        raise
    finally:
        if csr:
            csr.close()
```

#### 1.2 Update Error Handling Functions

Modify `_handle_transaction_processing_error` to work without direct cursor access:

```python
def _handle_transaction_processing_error(error: Exception, transaction_data: dict, tenant_id: int | None) -> None:
    """Handle errors without needing direct cursor access."""
    error_context = {
        "sort_code": transaction_data.get("sort_code"),
        "account_number": transaction_data.get("account_number"),
        "transaction_type": transaction_data.get("transaction_type"),
        "amount": transaction_data.get("amount"),
        "description": transaction_data.get("description"),
        "pay_date": transaction_data.get("pay_date"),
        "tenant_id": tenant_id,
    }

    log_database_error(logger, "database operation", error, error_context)
    logger.error("Database operation failed.")
```

### Phase 2: Critical Function Migration (Week 2)

#### 2.1 High-Priority Functions

**Priority 1 - Currently Failing:**
- `importBankOfScotlandTransactionsXMLFile` (main culprit)

**Priority 2 - High Risk:**
- `importBankOfScotlandBalancesXMLFile`
- `importQubeEndOfDayBalancesFile`

#### 2.2 Migration Pattern

**Before:**
```python
def problematic_function(db_conn, ...):
    try:
        csr = db_conn.cursor()
        csr.execute("begin")
        # ... processing ...
        csr.execute("end")
        db_conn.commit()
    except Exception as error:
        _handle_transaction_processing_error(csr, error, ...)
        return default_value
```

**After:**
```python
def fixed_function(db_conn, ...):
    try:
        with database_transaction_context(db_conn, logger) as csr:
            # ... processing ...
            pass  # Transaction management handled by context manager
    except Exception as error:
        # Handle error - csr guaranteed to be valid if we reach here
        _handle_transaction_processing_error(error, ...)
        return default_value
```

### Phase 3: Complete Migration (Week 3)

#### 3.1 Remaining Functions

Migrate all remaining functions with the same pattern:
- `importEstatesFile`
- `importBankAccounts`
- `importIrregularTransactionReferences`
- `addPropertyToDB`
- `addBlockToDB`
- `addTenantToDB`
- `importPropertiesFile`

#### 3.2 Batch Processing

Process functions in groups of 2-3 to maintain code review quality.

### Phase 4: Testing & Validation (Week 4)

#### 4.1 Unit Tests

Create comprehensive tests for:
- Cursor creation failures
- Transaction rollback scenarios
- Resource cleanup verification
- Error message accuracy

#### 4.2 Integration Tests

Test end-to-end scenarios:
- Database connection failures
- Memory exhaustion conditions
- Network interruption scenarios

#### 4.3 Regression Testing

Verify existing functionality remains intact:
- All existing tests pass
- Performance benchmarks maintained
- Error handling behavior preserved

## Benefits

### 1. Eliminates Critical Bug
- No more "csr not associated with a value" errors
- Application stability improved

### 2. Architectural Improvements
- Consistent transaction management
- Better separation of concerns
- Centralized error handling

### 3. Maintainability
- DRY principle applied
- Easier to modify error handling
- Self-documenting code patterns

### 4. Reliability
- Automatic resource cleanup
- Guaranteed transaction integrity
- Proper error recovery

## Risk Mitigation

### 1. Gradual Rollout
- Phase-by-phase implementation
- Each phase thoroughly tested
- Rollback plan for each change

### 2. Backward Compatibility
- Context manager is additive, not replacing
- Existing DatabaseCommand pattern preserved
- No breaking changes to public APIs

### 3. Monitoring
- Comprehensive logging added
- Error tracking implemented
- Performance monitoring maintained

## Success Criteria

1. **Zero Scoping Errors**: No more "csr not associated" exceptions
2. **Test Coverage**: 100% test coverage for new patterns
3. **Performance**: No degradation in database operation speed
4. **Maintainability**: Code is more readable and maintainable
5. **Reliability**: Improved error handling and recovery

## Timeline

- **Week 1**: Infrastructure setup and critical fixes
- **Week 2**: High-priority function migration
- **Week 3**: Complete migration and optimization
- **Week 4**: Testing, validation, and deployment

## Dependencies

- Python 3.8+ (for context manager support)
- Existing `database_commands.py` module
- Current logging infrastructure
- SQLite database connection patterns

## Post-Implementation

### 1. Documentation
- Update code documentation
- Add examples for new pattern
- Create migration guide for similar issues

### 2. Training
- Team training on new patterns
- Code review guidelines updated
- Best practices documentation

### 3. Monitoring
- Error tracking dashboards
- Performance monitoring
- Success metrics tracking

This plan provides a systematic, low-risk approach to eliminating the critical scoping issue while improving the overall database architecture.