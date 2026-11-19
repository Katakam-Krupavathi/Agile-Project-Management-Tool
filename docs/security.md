# Security Architecture & Honest Limitations

## Implemented Controls

- **Password Storage**: Argon2id hashing via `argon2-cffi` (`PasswordHasher` defaults). Plaintext passwords are never logged or returned in responses.
- **Session Cookies**: Signed, time-limited tokens (`itsdangerous.URLSafeTimedSerializer`) stored in `httpOnly`, `SameSite=Lax` cookies (`Secure` configurable via `SESSION_COOKIE_SECURE`).
- **CSRF Protection**: Double-submit cookie pattern (`agile_pm_csrf` cookie matched against `X-CSRF-Token` header via constant-time `hmac.compare_digest`) enforced on every mutating endpoint (`POST`, `PATCH`, `DELETE`).
- **Brute-Force Defense**: Sliding-window login rate limiter keyed by client IP + normalized email (`5` failed attempts per `60s` → `429 Too Many Requests` with `Retry-After` header in RFC 7807 format).
- **Authorization & Anti-Enumeration**: Centralized `require_project_role` / `require_story_role` / `require_task_role` dependencies on every scoped route. Non-members receive `404` instead of `403` to avoid leaking resource existence. Last-owner removal and demotion are blocked (`409`).
- **Input Validation & Payload Limits**: Pydantic v2 schemas enforce field types, regex patterns (`^[A-Z]{2,5}$` project keys), and strict max lengths on all inputs. `RequestSizeLimitMiddleware` rejects bodies exceeding `MAX_REQUEST_BODY_BYTES` (default `1 MB`) with `413` in RFC 7807 format.
- **HTTP Security Headers & CORS**: `SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, and `Content-Security-Policy` on API routes. CORS uses an explicit `CORS_ORIGINS` allow-list.
- **Secrets & Dependency Auditing**: Secrets are loaded strictly via environment variables (`.env` gitignored). CI runs `pip-audit` and `npm audit --audit-level=high` on every push.

## Honest Limitations

1. **SQLite Single-Writer Ceiling**: SQLite WAL supports concurrent readers, but only one writer at a time. Under heavy multi-instance load, write contention would require moving to PostgreSQL.
2. **In-Memory Rate Limiter**: The login rate limiter is stored in-process memory; restarting the API resets counters, and multi-replica deployments would require a shared store (e.g., Redis).
3. **No Email Verification or Password Reset**: Registration activates accounts immediately and `ConsoleMailer` logs emails to stdout rather than delivering via SMTP/SES.
4. **No MFA or SSO/OAuth**: Authentication is password-only; production deployments for larger organizations should add TOTP MFA and OIDC/SAML SSO.
5. **Stateless Cookie Revocation**: Signed cookies expire after `SESSION_MAX_AGE_SECONDS` (7 days) and are cleared on logout, but there is no server-side session revocation table to invalidate a stolen cookie prior to expiry.
