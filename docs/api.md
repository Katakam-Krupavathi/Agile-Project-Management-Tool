# API Reference

All endpoints are served under `/api/v1`. Interactive OpenAPI documentation is available at `/docs` (Swagger UI) and `/redoc`, and the exported schema is checked in at [docs/openapi.json](./openapi.json).

## Conventions

- **Error Envelope (RFC 7807)**: All errors return `Content-Type: application/problem+json` with `type`, `title`, `status`, `detail`, `instance`, and `code` (plus `errors[]` on `422`).
- **Cursor Pagination**: List endpoints accept `?limit=20&cursor=<opaque>` and return `{ "items": [...], "next_cursor": "...", "has_more": false }`.
- **Optimistic Concurrency**: `PATCH` endpoints on projects, stories, and tasks require `version`. A stale `version` returns `409 Conflict` (`code: "VERSION_CONFLICT"`).
- **CSRF**: All `POST`, `PATCH`, and `DELETE` requests (except `/auth/register` and `/auth/login`) require the `X-CSRF-Token` header matching the `agile_pm_csrf` cookie.

## Quick `curl` Examples

### 1. Health Check
```bash
curl -s http://localhost:8000/api/v1/health
```

### 2. Register & Log In (saving cookies and CSRF token)
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","name":"Dev User","password":"StrongPassword123"}'

CSRF=$(curl -s -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@example.com","password":"StrongPassword123"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['csrf_token'])")
```

### 3. Create a Project, Story, and Task
```bash
PROJECT_ID=$(curl -s -b cookies.txt -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"key":"DEMO","name":"Demo Project"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

STORY_ID=$(curl -s -b cookies.txt -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/stories" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"title":"Build onboarding flow","priority":"high"}' \
  | python -c "import sys, json; print(json.load(sys.stdin)['id'])")

curl -s -b cookies.txt -X POST "http://localhost:8000/api/v1/stories/$STORY_ID/tasks" \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: $CSRF" \
  -d '{"title":"Create welcome modal","estimate_hours":2.0}'
```

### 4. Fetch Project Tree with Rollups
```bash
curl -s -b cookies.txt "http://localhost:8000/api/v1/projects/$PROJECT_ID/tree"
```

### 5. Request an Async Markdown Report (Idempotent) & Poll Job
```bash
JOB_ID=$(curl -s -b cookies.txt -X POST "http://localhost:8000/api/v1/projects/$PROJECT_ID/reports" \
  -H "X-CSRF-Token: $CSRF" \
  -H "Idempotency-Key: sprint-1-report" \
  | python -c "import sys, json; print(json.load(sys.stdin)['job_id'])")

curl -s -b cookies.txt "http://localhost:8000/api/v1/jobs/$JOB_ID"
```

### 6. Stream Notifications via SSE
```bash
curl -N -b cookies.txt http://localhost:8000/api/v1/notifications/stream
```
