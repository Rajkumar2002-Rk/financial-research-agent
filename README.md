# Fintel — AI Financial Research Agent

A production-grade AI-powered financial research platform built with FastAPI, LangGraph, GPT-4o, and a premium dark UI. Analyze any stock, get real-time technical indicators, news sentiment, and AI investment recommendations — all in one place.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![GPT-4o](https://img.shields.io/badge/GPT--4o-powered-purple)

---

## Features

- **AI Analysis** — GPT-4o generates buy/sell/hold recommendations with reasoning
- **Live Market Data** — Real OHLCV data via Stooq (no API key required)
- **Technical Indicators** — MA50, MA200, RSI, volatility, 1Y price change, golden/death cross
- **News Sentiment** — Real-time news via Tavily API, summarized by GPT-4o
- **Smart Chat** — Ask about any stock by name or ticker. Fetches live prices on the fly
- **Redis Caching** — Analysis results cached for 15 minutes to reduce API calls
- **Session Memory** — Chat history persisted per session in Redis
- **Guardrails** — Confidence thresholds and consistency checks on LLM output
- **Premium UI** — Side-by-side layout: analysis panel on the left, AI chat on the right

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI Orchestration | LangGraph + LangChain |
| LLM | OpenAI GPT-4o |
| Market Data | Stooq via pandas_datareader |
| News | Tavily Search API |
| Caching & Sessions | Redis |
| Data Validation | Pydantic v2 |
| Logging | Structlog (structured JSON) |
| Frontend | Vanilla JS + Chart.js |
| Containerization | Docker + Docker Compose |
| Cloud | AWS EC2 (Ubuntu 24.04) |

---

## Architecture

```
User Request
     │
     ▼
FastAPI (REST API)
     │
     ▼
Orchestrator (LangGraph)
     ├── fetch_stock_data()   → Stooq (OHLCV)
     ├── fetch_company_news() → Tavily API
     ├── calculate_indicators() → MA, RSI, Volatility
     ├── make_decision()      → GPT-4o
     └── apply_guardrails()   → Confidence + Consistency checks
     │
     ▼
Redis Cache (TTL: 15 min)
     │
     ▼
JSON Response → Frontend
```

---

## Project Structure

```
financial-research-agent/
├── app/
│   ├── agents/
│   │   ├── analysis_agent.py     # Technical indicator calculations
│   │   ├── decision_agent.py     # GPT-4o investment decision
│   │   └── orchestrator.py       # LangGraph pipeline
│   ├── api/
│   │   ├── middleware.py          # CORS + request logging
│   │   └── routes/
│   │       ├── analysis.py        # /analyze and /chat endpoints
│   │       └── health.py          # /health/live and /health/ready
│   ├── guardrails/
│   │   └── financial_guardrails.py
│   ├── models/
│   │   ├── agent_state.py         # LangGraph state (TypedDict)
│   │   ├── requests.py            # Pydantic request models
│   │   └── responses.py           # Pydantic response models
│   ├── services/
│   │   ├── cache_service.py       # Redis async wrapper
│   │   ├── session_service.py     # Chat history in Redis
│   │   └── validation_service.py  # Data quality checks
│   ├── tools/
│   │   ├── yfinance_tool.py       # Market data fetcher (Stooq)
│   │   └── tavily_tool.py         # News fetcher
│   ├── utils/
│   │   ├── config.py              # Pydantic BaseSettings
│   │   └── logger.py              # Structlog setup
│   └── main.py                    # FastAPI app + lifespan
├── frontend/
│   └── index.html                 # Single-page UI
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- OpenAI API key — [platform.openai.com](https://platform.openai.com)
- Tavily API key — [tavily.com](https://tavily.com)

### 1. Clone the repo

```bash
git clone https://github.com/Rajkumar2002-Rk/financial-research-agent.git
cd financial-research-agent
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
OPENAI_API_KEY=your_openai_key_here
TAVILY_API_KEY=your_tavily_key_here
REDIS_URL=redis://localhost:6379
OPENAI_MODEL=gpt-4o
```

### 3. Run with Docker

```bash
docker compose up --build
```

Open `http://localhost:8000` in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/analyze` | Full AI analysis for a stock ticker |
| POST | `/api/v1/chat` | Chat with the AI assistant |
| GET | `/health/live` | Liveness check |
| GET | `/health/ready` | Readiness check (Redis connection) |

### Example — Analyze a stock

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "include_news": true}'
```

### Example — Chat

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the price of TSLA?", "session_id": "session-abc123"}'
```

---

## Deployment on AWS EC2

1. Launch an EC2 instance (Ubuntu 24.04, t2.micro or larger)
2. Open port `8000` in your security group
3. SSH into the instance and install Docker:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker ubuntu
```

4. Clone the repo, create `.env`, and run:

```bash
git clone https://github.com/Rajkumar2002-Rk/financial-research-agent.git
cd financial-research-agent
nano .env   # add your API keys
docker compose up --build -d
```

5. Access at `http://<your-ec2-public-ip>:8000`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | required | OpenAI API key |
| `TAVILY_API_KEY` | required | Tavily Search API key |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `OPENAI_MODEL` | `gpt-4o` | OpenAI model to use |
| `REDIS_CACHE_TTL` | `900` | Cache TTL in seconds (15 min) |
| `REDIS_SESSION_TTL` | `3600` | Session TTL in seconds (1 hour) |
| `MIN_CONFIDENCE_THRESHOLD` | `0.4` | Minimum confidence for a recommendation |

---

## License

MIT
