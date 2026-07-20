# Webhook Delivery Engine

A dependency-free Python implementation of the Nestack webhook assessment. The API and delivery worker are separate processes; SQLite provides durable scheduling without a queue library.

## Run

Requires Python 3.10+. Open two terminals in this directory:

```powershell
python api.py
```

```powershell
$env:WEBHOOK_SIGNING_SECRET = "replace-with-a-long-random-secret"
python worker.py
```

The API listens at `http://localhost:8000`.

## API

```powershell
# Queue an event; the worker attempts it immediately
Invoke-RestMethod http://localhost:8000/events -Method Post -ContentType 'application/json' -Body '{"type":"payment.failed","payload":{"payment_id":"p_123"},"webhook_url":"http://localhost:9000/webhook"}'

Invoke-RestMethod http://localhost:8000/events
Invoke-RestMethod http://localhost:8000/events/<event-id>
Invoke-RestMethod http://localhost:8000/events/<event-id>/retry -Method Post
```

`POST /events` returns a `201` pending event. `GET /events` returns all events, while `GET /events/:id` returns an event with its `attempts` array. Each attempt has `attempted_at`, `http_status` (or `null`), and `outcome`. Retrying a non-dead event gives `400`; a missing event gives `404`.

## Delivery behavior

The independently running worker atomically claims due rows from SQLite, then sends them as HTTP POST requests. A 2xx response marks an event `delivered`; non-2xx responses, timeouts, and network errors are failures. The fixed default retry intervals are 30 seconds, then 5 minutes, then 30 minutes. Four failed deliveries in a cycle (the initial attempt plus three retries) mark the event `dead`.

`POST /events/:id/retry` retains the previous attempt audit history but begins a fresh four-attempt cycle. For quick local tests only, the three schedule values can be overridden in seconds with `WEBHOOK_RETRY_DELAY_1`, `WEBHOOK_RETRY_DELAY_2`, and `WEBHOOK_RETRY_DELAY_3`; leave them unset for the required schedule.

## HMAC signature verification

The outgoing body is canonical compact JSON with `id`, `type`, `payload`, and `created_at`. `X-Webhook-Signature` is a lowercase hexadecimal HMAC-SHA256 of the exact UTF-8 body, keyed with `WEBHOOK_SIGNING_SECRET`.

```python
import hashlib, hmac
expected = hmac.new(secret.encode(), raw_request_body, hashlib.sha256).hexdigest()
valid = hmac.compare_digest(expected, request.headers["X-Webhook-Signature"])
```

The default secret (`change-me-in-production`) is for development only. Set a unique deployment secret.

## Restart behavior

`webhooks.db` stores all events, attempt history, statuses, and next-attempt timestamps. Restarts do not discard pending retries: the worker resumes them when running again. A worker crash after a delivery is claimed but before the outcome is written makes its claim eligible again after two minutes. This gives at-least-once delivery in that narrow crash window, so webhook consumers should use the event `id` for idempotency.

## Deployment link

Not deployed yet — add the live deployment URL here before assessment submission.