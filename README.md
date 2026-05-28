# Pythia

> **Ask your database a question. Get a SQL query, a plain-English answer, and a chart — instantly.**

Pythia is a natural-language analytics backend that puts an LLM in the seat of a junior data analyst. Users type a question in English; the service inspects the connected database, writes the SQL, executes it, and returns the answer along with a suggested visualisation. It was built to democratise data — to let anyone in an organisation explore data without writing SQL, waiting on the analytics team, or learning a BI tool.

---

## Table of Contents

- [Why "Pythia"?](#why-pythia)
- [Features](#features)
- [Architecture](#architecture)
- [Repository Layout](#repository-layout)
- [How It Works](#how-it-works)
- [API Reference](#api-reference)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Security Notes](#security-notes)
- [Roadmap](#roadmap)
- [License](#license)

---

## Why "Pythia"?

In ancient Greece, the **Pythia** was the high priestess of the Oracle at Delphi — the figure people travelled across the known world to consult. They came with questions in plain language and walked away with answers. That is exactly what this project does for data: you ask in natural language, the oracle (the LLM, grounded in your schema) answers.

The name is short, memorable, easy to say in any language, and pairs nicely with Python without naming the underlying tech stack.

A few alternates worth considering, if you'd like to A/B the brand:

| Name | Rationale |
|---|---|
| **Pythia** *(recommended)* | Oracle / question-and-answer metaphor; pairs neatly with Python. |
| **Augur** | Roman diviner — reads patterns and tells you what they mean. |
| **Lumen** | "Light"; an analytics tool illuminates what the data is hiding. |
| **Querio** | Playful nod to "query"; sounds like a product name. |
| **AskWell** | Plainly descriptive — you ask, it answers well. |

The rest of this README uses **Pythia**.

---

## Features

- **Natural-language → SQL.** Ask a question, get an executable SQL query back.
- **End-to-end analytics response.** Every NL question returns four things:
  1. The SQL query that was run
  2. A direct, plain-English answer
  3. A recommended chart type (bar, pie, line, scatter, area, table)
  4. JSON visualization data ready to be fed into a charting library
- **Schema-grounded prompts.** The LLM is shown only the tables and columns that exist; it can't invent fields.
- **Role-based BI dashboards.** Prefab KPI bundles for marketing, finance, fraud, support, product, retail and VIP teams.
- **CSV ingestion.** Upload a CSV and have it persisted as a table you can immediately query in natural language.
- **Question suggestions.** Given a table, the service can propose four useful analytical questions to bootstrap exploration.
- **Pluggable databases.** A companion `connect_db` service supports PostgreSQL, MySQL, SQLite and Snowflake out of the box.
- **Deploy anywhere.** Run locally with Uvicorn, package as a Docker image, or deploy to AWS Lambda via SAM — all from the same codebase.

---

## Architecture

```
                       ┌────────────────────────────┐
                       │         Frontend           │
                       │   (dashboard / chat UI)    │
                       └─────────────┬──────────────┘
                                     │  HTTPS / JSON
                                     ▼
   ┌─────────────────────────────────────────────────────────────┐
   │                    Pythia API (FastAPI)                     │
   │                                                             │
   │   /convert-nl-to-sql   /bi-dashboard-data   /questions/     │
   │   /createtable/        /execute_query/      /tables_in_…/   │
   │                                                             │
   │           ┌──────────────────────────────────┐              │
   │           │  Instructor + OpenAI (GPT-4)     │              │
   │           │  → typed JSON responses          │              │
   │           └──────────────────────────────────┘              │
   │                                                             │
   │           ┌──────────────────────────────────┐              │
   │           │  SQLAlchemy / psycopg2           │              │
   │           └──────────────────────────────────┘              │
   └─────────────┬──────────────────────────┬────────────────────┘
                 ▼                          ▼
       ┌──────────────────┐        ┌─────────────────────┐
       │   Demo DB        │        │   BI / User DB      │
       │ (Postgres)       │        │ (Postgres/MySQL/    │
       │                  │        │  SQLite/Snowflake)  │
       └──────────────────┘        └─────────────────────┘
```

There are **two Python services** in this repo:

- **`app/`** — the main API. NL→SQL, BI dashboards, CSV upload, question suggestions.
- **`connect_db/`** — a small connector service that accepts arbitrary database credentials and reports back the list of tables. Useful as an onboarding step before the main API is pointed at a customer database.

---

## Repository Layout

```
.
├── app/                          # Main FastAPI service
│   ├── main.py                   # All HTTP routes + the NL→SQL pipeline
│   ├── gunicorn.conf.py          # Production Gunicorn config
│   ├── secrets.yaml              # OpenAI + DB credentials (DO NOT COMMIT)
│   ├── Dockerfile                # Container build for the main API
│   ├── requirements.txt          # Pinned Python dependencies
│   ├── utils/
│   │   ├── database.py           # Engine setup + query helpers
│   │   ├── response_model.py     # Pydantic schemas (used as LLM response models)
│   │   ├── extract_schema.py     # One-off: export full DB schema + data to XLSX
│   │   ├── delete_table.py       # CLI: drop a single table (with confirmation)
│   │   └── delete_all.py         # CLI: drop ALL tables in the demo DB
│   └── misc/
│       ├── db_connector.py       # Helpers for building connection strings
│       └── decoder.py            # JWT decode helper
│
├── connect_db/                   # Small connection-test service
│   ├── main.py                   # /connect and /snowflake endpoints
│   ├── Dockerfile
│   └── requirements.txt
│
├── template.yaml                 # AWS SAM template (Lambda + HTTP API)
├── samconfig.toml                # SAM CLI deploy parameters
├── Dockerfile                    # Root-level Dockerfile for the main API
├── LICENSE                       # MIT
└── README.md                     # You are here
```

---

## How It Works

The flagship endpoint is `POST /convert-nl-to-sql`. It runs a four-step pipeline:

1. **Table selection.** The LLM is given the user's question and the complete list of tables in the database. It returns the subset of tables relevant to the question. If nothing is relevant, it returns an empty list and the request is rejected.
2. **Schema enrichment.** For each relevant table, the service introspects the live database (SQLAlchemy inspector, with a raw `information_schema` fallback) and gathers column names and data types.
3. **Query generation.** The LLM is given the user's question *and* the enriched schema. It is asked, in a single call, to return:
   - a syntactically valid SQL query,
   - a direct plain-English answer,
   - a recommended chart type, and
   - JSON visualization data.
   `instructor` enforces the JSON shape via the `Nltosql` Pydantic schema, so the response is always parseable.
4. **Execution.** The generated SQL is run against the connected database via `pandas.read_sql`, and the combined result is returned to the caller.

Every LLM call uses `temperature=0` for deterministic outputs, and the prompts forbid the model from inventing columns that aren't in the schema.

---

## API Reference

All endpoints are exposed by the FastAPI app in [`app/main.py`](app/main.py). Interactive docs are available at `/docs` (Swagger) and `/redoc` once the server is running.

### `POST /convert-nl-to-sql`
Translate a natural-language question into SQL, execute it, and return analytics + visualization data.

**Request**
```json
{ "prompt": "What were our top 5 products by revenue last quarter?" }
```

**Response**
```json
{
  "sql_query": "SELECT product_name, SUM(revenue) AS total ...",
  "natural_language": "The top 5 products by revenue last quarter were ...",
  "chart_type": "bar",
  "visualization_data": { "labels": ["..."], "values": ["..."] }
}
```

### `POST /bi-dashboard-data`
Generate a SQL-query bundle for one or more dashboard roles. Pass `"overview"` to get every role.

**Request**
```json
{ "roles": ["marketing", "fraud"] }
```

Supported roles: `marketing`, `vip`, `fraud`, `product`, `finance`, `support`, `retail`, `overview`.

### `GET /tables_in_creation_order/`
Return the names of every table in the BI database.

### `GET /execute_query/?table_name=<name>`
Return a 5-row JSON preview of the requested table.

### `GET /questions/?table_name=<name>`
Have the LLM propose four analytical questions that would be interesting to ask about the named table.

### `POST /createtable/`
Multipart upload — persist a CSV file as a table in the demo database.

**Form fields:** `table_name` (str), `file` (CSV upload).

### `POST /connect` (`connect_db` service)
Validate database credentials and return the list of tables visible to that user. Supports PostgreSQL, MySQL and SQLite.

### `POST /snowflake` (`connect_db` service)
Same as `/connect` but for Snowflake.

---

## Getting Started

### Prerequisites
- Python **3.10+** (the main app) / **3.9+** (the `connect_db` helper)
- A PostgreSQL database (any RDBMS will work for NL→SQL; PostgreSQL is what the BI flow expects)
- An OpenAI API key with access to GPT-4

### Local install
```bash
git clone <repo-url> pythia
cd pythia

# Main API
python -m venv .venv && source .venv/bin/activate
pip install -r app/requirements.txt

# Provide your secrets
cp app/secrets.yaml.example app/secrets.yaml   # then edit
```

### Run it
```bash
cd app
uvicorn main:app --reload --port 8000
# or, production-style:
gunicorn main:app -c gunicorn.conf.py
```

Browse to `http://localhost:8000/docs` and try the endpoints.

### Run the `connect_db` helper
```bash
cd connect_db
pip install -r requirements.txt
uvicorn main:app --port 8080
```

---

## Configuration

Configuration is loaded from `app/secrets.yaml` at startup. The schema is:

```yaml
OPENAI_API_KEY: sk-...

# BI / analytics database
bidbname:   <database name>
biuser:     <user>
bipassword: <password>
bihost:     <host>
port:       5432

# Demo database (used by /convert-nl-to-sql and CSV ingestion)
demodbname:   <database name>
demouser:     <user>
demopassword: <password>
demohost:     <host>
```

> **Never commit `secrets.yaml`.** It is `.gitignored` for a reason. Distribute a redacted `secrets.yaml.example` instead.

---

## Deployment

### Docker
```bash
# From the repo root
docker build -t pythia .
docker run -p 8000:8000 --env-file .env pythia
```

There are two Dockerfiles:
- **`/Dockerfile`** — slim Uvicorn deployment (`python:3.10-slim`).
- **`/app/Dockerfile`** — Gunicorn + Uvicorn worker class (`python:3.11`), recommended for production.

### AWS Lambda (SAM)
The app ships with [`template.yaml`](template.yaml) and [`samconfig.toml`](samconfig.toml) for one-command deployment:
```bash
sam build
sam deploy --guided   # first time only
sam deploy
```
This provisions:
- An HTTP API Gateway in front of the function,
- A Python 3.10 Lambda (1024 MB memory, 600 s timeout, 5 GB ephemeral),
- A `live` autopublished alias.

`Mangum` is used to adapt FastAPI to Lambda's event/context model — see the bottom of [`app/main.py`](app/main.py).

---

## Security Notes

A few things to keep in mind before running this in production:

1. **Move secrets out of YAML.** Prefer environment variables or a secret manager (AWS Secrets Manager, GCP Secret Manager, Doppler, etc.). The YAML file is fine for local development.
2. **Tighten CORS.** [`app/main.py`](app/main.py) currently allows `*`. Replace with an explicit allow-list of frontend origins.
3. **Constrain generated SQL.** The LLM is constrained by prompt and schema but not by syntax. Consider running queries inside a read-only role, or piping them through a SQL parser/limiter before execution.
4. **Add authentication.** Endpoints are unauthenticated. The `decoder.py` helper is the stub of a JWT auth path — wire it into a FastAPI dependency before exposing the service.

---

## Roadmap

- [ ] Read-only DB role + SQL allow-list for generated queries
- [ ] First-class auth (JWT or OAuth2) gating every route
- [ ] Pluggable model layer (Claude, local Llama, etc.) — today the code hardcodes OpenAI
- [ ] Caching layer for repeated NL prompts
- [ ] Conversation memory: follow-up questions like *"and just for last month?"*
- [ ] Native chart rendering (using the `ChartVisual` model)

---

## License

[MIT](LICENSE).
