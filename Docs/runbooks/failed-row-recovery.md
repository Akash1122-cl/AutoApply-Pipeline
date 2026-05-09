# Failed Row Recovery Runbook

## Overview

This runbook provides step-by-step procedures for safely recovering `FAILED` rows in the AutoApply pipeline while preserving idempotency and auditability.

## Prerequisites

- Access to the Google Sheets tracker
- Python environment with AutoApply codebase
- Understanding of pipeline states and checkpoints
- Recovery service permissions

## Recovery Service Components

### Core Files
- `src/orchestrator/recovery_service.py` - Main recovery logic
- `src/shared/sheets_gateway.py` - Sheet interface
- `src/shared/run_logger.py` - Audit logging

### Key Classes
- `RecoveryService` - Main recovery operations
- `RecoveryAction` - Enum of recovery actions
- `RecoveryMetadata` - Audit trail data

## Recovery Procedures

### 1. Initial Assessment

#### 1.1 Get Failed Rows
```python
from src.orchestrator.recovery_service import RecoveryService
from src.shared.sheets_gateway import SheetsGateway
from src.shared.run_logger import RunLogger

sheets = SheetsGateway()
logger = RunLogger()
recovery = RecoveryService(sheets, logger)

failed_rows = recovery.get_failed_rows()
print(f"Found {len(failed_rows)} failed rows")
```

#### 1.2 Inspect Individual Row
```python
row_id = "your_row_id"
details = recovery.inspect_row_error(row_id)
print(json.dumps(details, indent=2))
```

#### 1.3 Check Safe Recovery Actions
```python
safe_actions = recovery.get_safe_recovery_actions(row_id)
print("Safe actions:", [action.value for action in safe_actions])
```

### 2. External Outcome Verification

Before any recovery action, verify external outcomes:

```python
verification = recovery.verify_external_outcome(row_id)
print("Verification:", verification)

# If recommendation is "manual_review_required", do NOT proceed with automated recovery
if verification["recommendation"] == "manual_review_required":
    print("Manual review required - external action detected")
```

### 3. Recovery Actions

#### 3.1 Retry Same Checkpoint
Use for transient failures (timeouts, network issues, rate limits):

```python
result = recovery.recover_row(
    row_id=row_id,
    action=RecoveryAction.RETRY_SAME_CHECKPOINT,
    recovered_by="operator_name",
    recovery_reason="Network timeout resolved"
)
```

#### 3.2 Reset to CP1
Use when human action is missing or invalid:

```python
result = recovery.recover_row(
    row_id=row_id,
    action=RecoveryAction.RESET_TO_CP1,
    recovered_by="operator_name",
    recovery_reason="Missing human action - reset for review"
)
```

#### 3.3 Reset to CP2
Use when CP2 approval is missing:

```python
result = recovery.recover_row(
    row_id=row_id,
    action=RecoveryAction.RESET_TO_CP2,
    recovered_by="operator_name",
    recovery_reason="CP2 approval missing - reset for approval"
)
```

#### 3.4 Reset to Contact Discovery
Use for contact discovery failures:

```python
result = recovery.recover_row(
    row_id=row_id,
    action=RecoveryAction.RESET_TO_CONTACT_DISCOVERY,
    recovered_by="operator_name",
    recovery_reason="Contact enrichment failed - retry discovery"
)
```

#### 3.5 Reset to Content Generation
Use for content generation failures:

```python
result = recovery.recover_row(
    row_id=row_id,
    action=RecoveryAction.RESET_TO_CONTENT_GENERATION,
    recovered_by="operator_name",
    recovery_reason="CV generation failed - retry content creation"
)
```

#### 3.6 Manual Review
Use for complex issues or when external actions detected:

```python
result = recovery.recover_row(
    row_id=row_id,
    action=RecoveryAction.MANUAL_REVIEW,
    recovered_by="operator_name",
    recovery_reason="Complex failure requires manual investigation"
)
```

## Error Pattern Analysis

### Common Failure Types and Recommended Actions

#### Network/Timeout Errors
- **Pattern**: "timeout", "network", "connection"
- **Action**: `RETRY_SAME_CHECKPOINT`
- **Notes**: Usually transient, safe to retry

#### API Rate Limits
- **Pattern**: "rate_limit", "429", "quota"
- **Action**: `RETRY_SAME_CHECKPOINT` or wait for quota reset
- **Notes**: Check quota status before retry

#### Contact Discovery Failures
- **Pattern**: "contact", "enrichment", "email_not_found"
- **Action**: `RESET_TO_CONTACT_DISCOVERY` or `MANUAL_REVIEW`
- **Notes**: May require manual research

#### Content Generation Failures
- **Pattern**: "content", "cv", "email", "generation"
- **Action**: `RESET_TO_CONTENT_GENERATION`
- **Notes**: Check LLM quota and content policies

#### ATS Failures
- **Pattern**: "ats", "score", "optimization"
- **Action**: `MANUAL_REVIEW` if revision_count >= 2
- **Notes**: ATS loop cap prevents excessive retries

#### Validation Errors
- **Pattern**: "validation", "schema", "format"
- **Action**: `MANUAL_REVIEW`
- **Notes**: Usually data quality issues

## Batch Recovery Procedures

### 1. Analyze Failure Patterns
```python
recovery_report = recovery.get_recovery_queue_report()
print("Failure patterns:", recovery_report["failure_patterns"])
print("Recommended actions:", recovery_report["recommended_actions"])
```

### 2. Prioritize Recovery Actions
1. **High Priority**: Network timeouts, API rate limits
2. **Medium Priority**: Contact discovery, content generation
3. **Low Priority**: Validation errors, ATS failures

### 3. Execute Batch Recovery
```python
# Example: Recover all timeout failures
failed_rows = recovery.get_failed_rows()
timeout_rows = [row for row in failed_rows if "timeout" in row.get("notes", "").lower()]

for row in timeout_rows:
    safe_actions = recovery.get_safe_recovery_actions(row["row_id"])
    if RecoveryAction.RETRY_SAME_CHECKPOINT in safe_actions:
        result = recovery.recover_row(
            row_id=row["row_id"],
            action=RecoveryAction.RETRY_SAME_CHECKPOINT,
            recovered_by="batch_recovery",
            recovery_reason="Batch recovery of timeout failures"
        )
        print(f"Recovered {row['row_id']}: {result['success']}")
```

## Safety Checks

### Pre-Recovery Checklist
- [ ] Verify row exists and is in FAILED status
- [ ] Check external outcome verification
- [ ] Confirm safe recovery actions available
- [ ] Review error notes and failure context
- [ ] Check revision count for ATS failures

### Post-Recovery Verification
- [ ] Confirm row status updated correctly
- [ ] Verify recovery metadata logged
- [ ] Check for any side effects
- [ ] Monitor subsequent pipeline execution

## Audit Trail

All recovery actions are automatically logged with:
- Recovery timestamp
- Operator identity
- Recovery reason
- Original status and error
- Recovery action taken
- New status

### Viewing Recovery History
```python
# Recovery metadata is stored in the row's recovery_metadata field
row = sheets.get_row_by_id(row_id)
recovery_metadata = row.get("recovery_metadata", "")
print("Recovery history:", recovery_metadata)
```

## Monitoring and Alerting

### Recovery Queue Metrics
- Failed rows count
- Human review queue size
- Recovery success rate
- Common failure patterns

### Alert Thresholds
- Failed rows > 10: WARNING
- Failed rows > 25: CRITICAL
- Recovery success rate < 80%: WARNING
- Recovery success rate < 60%: CRITICAL

## Emergency Procedures

### Large-Scale Failures
1. **Stop**: Pause pipeline execution
2. **Assess**: Identify root cause
3. **Isolate**: Separate affected rows
4. **Recover**: Apply batch recovery procedures
5. **Monitor**: Watch for recurrence

### Data Corruption
1. **Backup**: Export current sheet state
2. **Identify**: Locate corrupted rows
3. **Restore**: Revert to last known good state
4. **Validate**: Verify data integrity
5. **Resume**: Restart pipeline carefully

## Troubleshooting

### Common Issues

#### Recovery Service Errors
- **Issue**: "Row not found" error
- **Solution**: Verify row_id exists and is accessible

#### Permission Denied
- **Issue**: Cannot update sheet rows
- **Solution**: Check sheet permissions and service account access

#### Invalid Recovery Action
- **Issue**: "Cannot apply action to status" error
- **Solution**: Use `get_safe_recovery_actions()` to validate

#### External Action Detected
- **Issue**: Verification recommends manual review
- **Solution**: Investigate external systems before proceeding

### Debug Mode
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Best Practices

1. **Always verify external outcomes** before automated recovery
2. **Use safe recovery actions** recommended by the service
3. **Document recovery reasons** clearly for audit purposes
4. **Monitor recovery success rates** and adjust procedures
5. **Test recovery procedures** in non-production environment
6. **Keep recovery metadata** for troubleshooting and compliance

## Related Documentation

- [Phase-wise Implementation Plan](../Phasewise-Implementation.md)
- [State Machine Specification](../contracts/state-machine-spec.md)
- [Data Contracts](../contracts/data-contracts.md)
- [Operations Guide](../operations/operations-guide.md)

## Support Contacts

- **Technical Lead**: [Contact information]
- **Operations Team**: [Contact information]
- **Emergency Escalation**: [Contact information]
