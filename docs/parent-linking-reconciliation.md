# Parent-linking reconciliation

Verified: 5 November 2026

This is a school-facing reconciliation summary. It contains aggregate counts only and must not be completed or stored in a public repository with real student or parent data.

## Current aggregate

- Active students: 2,292
- Students with at least one parent link: 1,877
- Students without a parent link: 415
- Duplicate parent-student link groups: 0
- Orphan parent references: 0
- Orphan student references: 0
- Unlinked students with an admission-number username match: 0
- Inactive parent accounts without any student link: 392

The 392 inactive accounts are a separate population and must not be assigned to the 415 students without authoritative school confirmation.

## Unlinked students by class

| Academic year | Class | Section | Unlinked students |
|---|---:|:---:|---:|
| 2026-2027 | LKG | A | 2 |
| 2026-2027 | I | B | 46 |
| 2026-2027 | I | C | 47 |
| 2026-2027 | III | B | 2 |
| 2026-2027 | VII | A | 42 |
| 2026-2027 | VII | B | 43 |
| 2026-2027 | VII | D | 42 |
| 2026-2027 | XI | B | 42 |
| 2026-2027 | XI | C | 68 |
| 2026-2027 | XII | B | 29 |
| 2026-2027 | XII | C | 52 |
| **Total** |  |  | **415** |

## Secure mapping template

Create the working CSV only inside the school's approved encrypted storage. Do not commit a completed copy, send it through public chat, or include student names, phone numbers, addresses, passwords, or password hashes.

```csv
student_admission_no,approved_parent_username,relationship,account_action,school_verifier_role,verification_date,approval_reference
```

Allowed `relationship` values are `Father`, `Mother`, or `Guardian`. Allowed `account_action` values are:

- `LINK_EXISTING`: the approved parent account already exists and has been independently verified.
- `CREATE_AFTER_REVIEW`: the school has approved account creation, but the account must be created through the authorized process before linking.

Collect any parent contact information needed for account creation through the school's separate secure intake process, not in this mapping file.

## Validation and approval gates

1. The school verifies every admission number and parent relationship against its authoritative records.
2. A second authorized reviewer checks the mapping and sibling groupings.
3. Engineering performs a dry run that reports creates, links, skips, conflicts, and duplicates without printing personal data.
4. The school owner approves the exact production change set.
5. Operations creates and verifies a pre-change backup.
6. Changes run in one auditable transaction; any conflict rolls back the transaction.
7. Aggregate link, duplicate, orphan, and sibling checks run again after the change.
8. The school validates designated parent accounts before final acceptance.

No production relationship should be inferred from similar names, class membership, contact details, inactive accounts, or row order.
