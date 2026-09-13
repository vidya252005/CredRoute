# Lender routing

Active lender policy comes from `lender_policy_versions` (status `ACTIVE`). `lenders.policy` JSON is a copy of that version for catalog responses.

Admin flow:

```text
POST /admin/lenders/{id}/policies/draft
POST /admin/lenders/{id}/policies/{version}/activate
```

`PATCH /admin/lenders/{id}` still publishes a draft and activates it immediately (demo convenience).

Provider outcomes:

| Status | Meaning |
|--------|---------|
| success | Offer returned |
| ineligible | Hard policy miss |
| unknown | Timeout after send — do not assume failure |
| failed | Confirmed provider/protocol error |

A reconciliation worker (`reconcile_unknown_attempts`) resolves mock UNKNOWN rows. A real adapter would query the provider application reference instead of marking `RECONCILED_NO_EXTERNAL_STATE`.
