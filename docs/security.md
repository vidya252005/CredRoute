# Security

- PAN lookup uses HMAC-SHA256 (`PAN_HMAC_SECRET`). Only a masked PAN is stored or returned.
- `JWT_SECRET` and `PAN_HMAC_SECRET` fail closed when `ENVIRONMENT=production`.
- Admin exists only if you set `ADMIN_EMAIL` and `ADMIN_PASSWORD` locally.
- Application list is owner-scoped. Sandbox evaluates (no login) stay readable by id for the demo.
- Owned applications are owner or admin only.
- Compose defaults are local-only. Use a secret manager for any hosted demo.
