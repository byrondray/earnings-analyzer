# Stock Earnings Analyzer

A full-stack application that displays weekly earnings calendars and runs AI-powered analysis on individual stock earnings reports. Built with FastAPI and Svelte 5.

## Features

- **Weekly Earnings Calendar** — Browse upcoming and past earnings events by week
- **AI-Powered Analysis** — Get structured financial analysis of earnings reports using Claude
- **Stock Search** — Look up any ticker to view earnings history and details
- **Favorites** — Save stocks to a personal watchlist (Clerk authentication)
- **Stock Charts** — View price charts powered by market data APIs
- **News Feed** — Surface relevant financial news for tracked stocks
- **Redis Caching** — Optional caching layer for calendar data (4h TTL) and market caps (24h TTL)

## Tech Stack

| Layer    | Technology                                         |
| -------- | -------------------------------------------------- |
| Frontend | Svelte 5, Vite 6, Tailwind CSS v4                  |
| Backend  | Python 3.11+, FastAPI, SQLAlchemy (async), asyncpg |
| Database | PostgreSQL (JSONB for analysis storage)            |
| Cache    | Redis                                              |
| Auth     | Clerk                                              |
| AI       | Anthropic Claude API (structured tool-use output)  |
| Search   | Brave Search API                                   |
| Data     | Alpha Vantage, Financial Modeling Prep, Polygon.io |

## API Endpoints

| Method | Path                      | Description                      |
| ------ | ------------------------- | -------------------------------- |
| GET    | `/api/calendar/week`      | Current week's earnings events   |
| GET    | `/api/calendar/week/next` | Next week's earnings events      |
| GET    | `/api/calendar/week/prev` | Previous week's earnings events  |
| GET    | `/api/calendar/search`    | Search earnings by ticker        |
| POST   | `/api/analysis/{ticker}`  | Trigger AI analysis for a ticker |
| GET    | `/api/analysis/{ticker}`  | Retrieve cached analysis         |
| GET    | `/api/favorites`          | List user's favorite stocks      |
| POST   | `/api/favorites/{ticker}` | Add a stock to favorites         |
| DELETE | `/api/favorites/{ticker}` | Remove a stock from favorites    |
| GET    | `/health`                 | Health check                     |

## Data Flow

```
Alpha Vantage ──► Postgres (upsert) ──► API response ──► Frontend

Analysis request:
  Brave Search ──► Claude API (structured output) ──► Postgres ──► Frontend modal
```

## Testing

### Backend

```bash
cd backend
pytest                # run all tests
pytest -v             # verbose output
pytest --cov          # with coverage
```

Tests mock all external services (Alpha Vantage, Brave Search, Anthropic, Redis) using `unittest.mock`.

### Frontend

```bash
cd frontend
npm run test          # run once
npm run test:watch    # watch mode
```

## Docker

Build and run the full stack as a single container:

```bash
docker build --build-arg VITE_CLERK_PUBLISHABLE_KEY=pk_test_... -t stock-earnings .
docker run -p 8000:8000 --env-file .env stock-earnings
```

The Dockerfile uses a multi-stage build — Node builds the frontend, then the Python image serves both the API and the static SPA assets.

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app & lifespan
│   │   ├── config.py            # Pydantic settings
│   │   ├── auth.py              # Clerk JWT verification
│   │   ├── db/
│   │   │   ├── database.py      # Async engine & session
│   │   │   └── models.py        # SQLAlchemy models
│   │   ├── routers/             # API route handlers
│   │   ├── services/            # Business logic & external APIs
│   │   └── mcp_server/tools/    # Brave Search & Claude analysis
│   └── tests/                   # pytest async tests
├── frontend/
│   └── src/
│       ├── App.svelte           # Root component
│       ├── components/          # UI components
│       └── lib/                 # API client & utilities
├── Dockerfile                   # Multi-stage build
└── .env                         # Environment variables (not committed)
```
