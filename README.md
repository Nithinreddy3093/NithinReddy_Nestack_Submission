# 🔗 Webhook Delivery Engine

**A reliable, persistent webhook delivery system built with Python and SQLite.**

A dependency-free Python implementation of the Nestack webhook assessment. The project separates event ingestion from webhook delivery using an API process and an independent worker. SQLite provides durable scheduling, retry management, and delivery attempt history without requiring a dedicated queue library.

## ✨ Features

- **REST API** — Create webhook events, list events, retrieve event details, and retry eligible dead events.
- **Independent Delivery Worker** — Processes queued events separately from the API.
- **Persistent Scheduling** — Uses SQLite to retain events, delivery attempts, statuses, and retry timestamps across restarts.
- **Automatic Retries** — Schedules failed deliveries using configurable retry intervals for local testing.
- **HMAC-SHA256 Signatures** — Signs outgoing webhook payloads using a shared secret.
- **Attempt History** — Records timestamps, HTTP status codes, and delivery outcomes.
- **Dead-Event Handling** — Marks events dead after four failed attempts in a delivery cycle.
- **Manual Retry** — Allows dead events to start a fresh delivery cycle while preserving previous attempt history.
- **Crash Recovery** — Makes abandoned delivery claims eligible for processing again after two minutes.
- **At-Least-Once Delivery** — Documents the narrow crash window in which a webhook may be delivered more than once.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.10+ | Application and worker logic |
| SQLite | Persistent event storage and scheduling |
| HTTP | Outgoing webhook requests |
| HMAC-SHA256 | Webhook request signing |
| JSON | Event payload serialization |
| REST API | Event creation and management |

## 🏗️ Architecture

The application separates event management from event delivery.

```text
                 ┌─────────────────────┐
                 │    API Client       │
                 └──────────┬──────────┘
                            │ HTTP
                 ┌──────────▼──────────┐
                 │    API Process      │
                 │      api.py         │
                 └──────────┬──────────┘
                            │
                 ┌──────────▼──────────┐
                 │    SQLite Database  │
                 │   Persistent Queue  │
                 └──────────┬──────────┘
                            │
                 ┌──────────▼──────────┐
                 │   Delivery Worker   │
                 │     worker.py       │
                 └──────────┬──────────┘
                            │ HTTP POST
                 ┌──────────▼──────────┐
                 │ Webhook Consumer    │
                 └─────────────────────┘
```

### Event Lifecycle

1. A client submits an event through the API.
2. The API stores the event in SQLite with a pending status.
3. The independent worker claims a due event.
4. The worker sends the event to the configured webhook URL.
5. A successful 2xx response marks the event delivered.
6. A failed response schedules a retry according to the configured policy.
7. After four failed attempts in a cycle, the event is marked dead.
8. An eligible dead event can be retried through the API, starting a new cycle.

## 🔌 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/events` | Create and queue a webhook event |
| GET | `/events` | List events |
| GET | `/events/{event-id}` | Retrieve an event and its attempt history |
| POST | `/events/{event-id}/retry` | Start a new delivery cycle for an eligible dead event |

### Create an Event

**Request**

```http
POST /events
Content-Type: application/json
```

```json
{
  "type": "payment.failed",
  "payload": {
    "payment_id": "p_123"
  },
  "webhook_url": "http://localhost:9000/webhook"
}
```

The API returns a `201 Created` response with a pending event.

### List Events

```http
GET /events
```

Returns the available webhook events.

### Retrieve an Event

```http
GET /events/{event-id}
```

Returns the event and its delivery attempt history. Each attempt includes its timestamp, HTTP status code when available, and outcome.

### Retry an Event

```http
POST /events/{event-id}/retry
```

A missing event returns `404`. Retrying an event that is not eligible for another cycle returns `400`.

## 🔁 Retry Policy

The default retry schedule is:

| Attempt | Delay before retry |
|---|---|
| Initial delivery | Immediate |
| Retry 1 | 30 seconds |
| Retry 2 | 5 minutes |
| Retry 3 | 30 minutes |
| After four failed attempts | Mark event dead |

The initial attempt plus three retries make up one delivery cycle.

For local testing, the retry delays can be overridden using these environment variables:

```powershell
$env:WEBHOOK_RETRY_DELAY_1 = "5"
$env:WEBHOOK_RETRY_DELAY_2 = "10"
$env:WEBHOOK_RETRY_DELAY_3 = "15"
```

These values are expressed in seconds. Leave the variables unset to use the required default schedule.

## 🔐 HMAC-SHA256 Signature Verification

Each outgoing webhook includes an `X-Webhook-Signature` header containing a lowercase hexadecimal HMAC-SHA256 signature of the exact UTF-8 request body.

The canonical JSON body contains:

- `id`
- `type`
- `payload`
- `created_at`

The receiving application can verify the signature as follows:

```python
import hashlib
import hmac

expected = hmac.new(
    secret.encode(),
    raw_request_body,
    hashlib.sha256
).hexdigest()

valid = hmac.compare_digest(
    expected,
    request.headers["X-Webhook-Signature"]
)
```

Verification must use the original raw request body rather than a parsed and re-serialized JSON representation.

Configure a unique, strong signing secret in the environment. Never use the development default in production.

## 💾 Persistence and Crash Recovery

SQLite stores:

- Webhook events
- Event statuses
- Delivery attempt history
- Scheduled retry timestamps

The worker resumes pending retries after a restart.

If a worker crashes after claiming an event but before recording its delivery outcome, the claim becomes eligible again after two minutes.

This creates a narrow at-least-once delivery window: a webhook may be delivered more than once if the consumer processes the request before the worker crashes. Consumers should use the event ID as an idempotency key.

## 🚀 Getting Started

### Prerequisites

- Python 3.10 or later
- PowerShell on Windows, or a compatible terminal on other operating systems

### 1. Clone the Repository

```bash
git clone https://github.com/Nithinreddy3093/NithinReddy_Nestack_Submission.git
cd NithinReddy_Nestack_Submission
```

### 2. Start the API

Open the first terminal:

```bash
python api.py
```

The API listens at:

`http://localhost:8000`

### 3. Configure the Signing Secret

Open a second PowerShell terminal:

```powershell
$env:WEBHOOK_SIGNING_SECRET = "replace-with-a-long-random-secret"
```

### 4. Start the Worker

In the same second terminal:

```bash
python worker.py
```

Keep both processes running while testing event delivery.

## 🧪 Testing the API

With the API and worker running, submit an event from PowerShell:

```powershell
Invoke-RestMethod `
  http://localhost:8000/events `
  -Method Post `
  -ContentType 'application/json' `
  -Body '{"type":"payment.failed","payload":{"payment_id":"p_123"},"webhook_url":"http://localhost:9000/webhook"}'
```

Use the following commands to inspect events:

```powershell
Invoke-RestMethod http://localhost:8000/events
```

Retrieve an individual event:

```powershell
Invoke-RestMethod http://localhost:8000/events/YOUR_EVENT_ID
```

Replace `YOUR_EVENT_ID` with the ID returned when creating the event.

To test delivery successfully, run a webhook receiver at the URL supplied in the event request.

## 📁 Project Structure

```text
NithinReddy_Nestack_Submission/
├── outputs/          # Assessment outputs
├── work/             # Supporting work files
├── api.py            # Event management API
├── worker.py         # Independent webhook delivery worker
├── database.py       # SQLite persistence and scheduling
├── requirements.txt  # Python dependencies
├── render.yaml       # Render deployment configuration
├── README.md         # Project documentation
└── .gitignore
```

## ☁️ Deployment

The repository includes a `render.yaml` configuration file. The application has not yet been confirmed as deployed.

Before deploying, configure the API and worker as separate processes, ensure the SQLite database is stored on persistent storage, and provide the signing secret through environment variables.

**Live deployment:** Not yet available.

## 🔒 Security Considerations

- Use a strong, unique webhook signing secret.
- Verify HMAC signatures using constant-time comparison.
- Validate webhook destinations to reduce server-side request forgery (SSRF) risks.
- Protect API endpoints against unauthorized event creation and retries.
- Use HTTPS for production webhook delivery.
- Implement idempotency at webhook consumers.
- Avoid logging sensitive payload data or secrets.

## 👨‍💻 Author

**Nithin Reddy**

GitHub: [@Nithinreddy3093](https://github.com/Nithinreddy3093)

## 📄 License

No license has been specified. Add a `LICENSE` file if you intend to permit reuse or redistribution.

---

**Built for the Nestack webhook assessment.**

A lightweight, persistent webhook delivery engine designed around reliable scheduling, observable delivery attempts, and verifiable request signatures.
