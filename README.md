# Fintel — AI Financial Research Agent

A production-grade AI-powered stock research platform built with FastAPI, LangGraph, GPT-4o, and a fully responsive dark UI. Analyze any stock ticker, get deterministic buy/sell/hold decisions backed by a normalized multi-factor scoring engine, real-time technical indicators, fundamental data, news sentiment, and an AI chat assistant — all deployed on AWS EC2.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![GPT-4o](https://img.shields.io/badge/GPT--4o-powered-purple)
![AWS EC2](https://img.shields.io/badge/AWS-EC2-orange)
![Mobile Ready](https://img.shields.io/badge/Mobile-Responsive-brightgreen)

---

## What Makes This Different

Most AI financial tools let the LLM decide whether to buy or sell. This system does not. The investment decision is made entirely by a **deterministic scoring engine** — GPT-4o only explains the decision in plain English. This eliminates hallucination risk from the most critical part of the pipeline.

---

## Features

### Scoring Engine
- **Normalized scoring** — scores are computed as `(actual / max_possible) × 100`, so stocks with missing data are judged fairly on what's available rather than penalized
- **Three-component model** — Technical (0–25), Fundamental (0–40), Sentiment (0–15), minus a Volatility penalty (0–10)
- **Decision thresholds** — BUY ≥ 70%, HOLD 40–69%, SELL < 40%, operating on the normalized score
- **Conflict detection** — when technical and fundamental signals sharply disagree (variance > 0.15) and the score sits in the 35–55 borderline zone, the system overrides to HOLD to avoid a false signal
- **Time horizon adaptation** — weight profiles for `short_term` (amplifies technicals), `long_term` (amplifies fundamentals), and `default` (balanced)
- **Confidence scoring** — 5-factor model: data completeness, missing data penalty, signal agreement, signal consistency bonus, volatility/uncertainty penalty

### Analysis
- **Live market data** — real OHLCV price history via Stooq (no API key required)
- **Technical indicators** — MA50, MA200, RSI, volatility, 1Y price change, golden cross / death cross detection
- **Fundamental data** — revenue growth, profit margin, P/E ratio, debt-to-equity, EPS via Alpha Vantage
- **News sentiment** — real-time news via Tavily API, scored by GPT-4o into positive / neutral / negative

### Portfolio Mode
- **Multi-ticker ranking** — submit a list of tickers and receive a ranked table sorted by normalized score
- **Allocation percentages** — portfolio allocation is distributed proportionally among BUY and HOLD positions; SELL and INSUFFICIENT_DATA positions receive 0%

### Infrastructure
- **Redis caching** — analysis results cached for 15 minutes to minimize API calls
- **Session memory** — chat history persisted per session in Redis
- **Fully mobile responsive** — tab-based layout on mobile with Analysis and Chat panels switchable via bottom tab bar
- **AI chat assistant** — ask follow-up questions about any analyzed stock in natural language

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| AI Orchestration | LangGraph + LangChain |
| LLM | OpenAI GPT-4o |
| Market Data | Stooq via pandas_datareader |
| Fundamental Data | Alpha Vantage API |
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
FastAPI REST API
     │
     ▼
Orchestrator (LangGraph)
     ├── fetch_stock_data()        → Stooq (OHLCV + technicals)
     ├── fetch_fundamental_data()  → Alpha Vantage
     ├── fetch_company_news()      → Tavily API + GPT-4o sentiment
     ├── apply_time_horizon_weights()
     ├── compute_normalized_score()
     ├── detect_conflict()
     ├── compute_confidence()
     └── make_deterministic_decision()  ← no LLM involvement
          │
          ▼
     Decision Agent (GPT-4o)       → natural language explanation only
          │
          ▼
Redis Cache (TTL: 15 min)
     │
     ▼
JSON Response → Frontend
```

### Scoring Engine Detail

```
Technical Score   (0–25)  ← MA cross, RSI, price momentum, volatility
Fundamental Score (0–40)  ← revenue growth, profit margin, P/E, D/E, EPS
Sentiment Score   (0–15)  ← news tone (positive=10, neutral=5, negative=0)
Volatility Penalty(0–10)  ← subtracted from total

normalized_score = (total / max_possible) × 100

BUY  ≥ 70%
HOLD  40–69%  (or conflict override when signals disagree in 35–55 range)
SELL < 40%
```

---

## Project Structure

```
financial-research-agent/
├── app/
│   ├── agents/
│   │   ├── scoring_engine.py      # Deterministic multi-factor scoring
│   │   ├── portfolio_engine.py    # Multi-ticker ranking + allocation
│   │   ├── decision_agent.py      # GPT-4o explanation generator
│   │   └── orchestrator.py        # LangGraph pipeline
│   ├── api/
│   │   ├── middleware.py           # CORS + request logging
│   │   └── routes/
│   │       ├── analysis.py         # /analyze, /chat, /portfolio/rank
│   │       └── health.py           # /health/live and /health/ready
│   ├── models/
│   │   ├── agent_state.py          # LangGraph state (TypedDict)
│   │   ├── requests.py             # Pydantic request models
│   │   └── responses.py            # Pydantic response models
│   ├── services/
│   │   ├── cache_service.py        # Redis async wrapper
│   │   ├── session_service.py      # Chat history in Redis
│   │   └── validation_service.py   # Data quality checks
│   ├── tools/
│   │   ├── yfinance_tool.py        # Market data fetcher (Stooq)
│   │   └── tavily_tool.py          # News fetcher
│   ├── utils/
│   │   ├── config.py               # Pydantic BaseSettings
│   │   └── logger.py               # Structlog setup
│   └── main.py                     # FastAPI app + lifespan
├── frontend/
│   └── index.html                  # Single-page responsive UI
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/analyze` | Full AI analysis for a single stock ticker |
| POST | `/api/v1/chat` | Conversational AI assistant |
| POST | `/api/v1/portfolio/rank` | Rank and allocate across multiple tickers |
| GET | `/health/live` | Liveness check |
| GET | `/health/ready` | Readiness check (Redis connection) |

### Analyze a stock

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "include_news": true, "time_horizon": "long_term"}'
```

**Response fields include:** `recommendation`, `normalized_score`, `confidence_score`, `conflict_detected`, `missing_components`, `time_horizon_used`, `score_breakdown`, `technical_indicators`, `fundamental_data`, `news_summary`, `explanation`

### Rank a portfolio

```bash
curl -X POST http://localhost:8000/api/v1/portfolio/rank \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL", "MSFT", "TSLA", "NVDA"], "time_horizon": "default"}'
```

### Chat

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Why is AAPL rated HOLD?", "session_id": "session-abc123", "ticker": "AAPL"}'
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- OpenAI API key — [platform.openai.com](https://platform.openai.com)
- Tavily API key — [tavily.com](https://tavily.com)
- Alpha Vantage API key — [alphavantage.co](https://www.alphavantage.co) (free tier available)

### 1. Clone the repo

```bash
git clone https://github.com/Rajkumar2002-Rk/financial-research-agent.git
cd financial-research-agent
```

### 2. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key
ALPHA_VANTAGE_API_KEY=your_alphavantage_key
REDIS_URL=redis://redis:6379
OPENAI_MODEL=gpt-4o
```

### 3. Run with Docker

```bash
docker compose up --build
```

Open `http://localhost:8000` in your browser.

---

## Deployment on AWS EC2

1. Launch an EC2 instance (Ubuntu 24.04, t2.micro or larger)
2. Open port `8000` in your security group
3. SSH in and install Docker:

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker ubuntu
```

4. Clone, configure, and run:

```bash
git clone https://github.com/Rajkumar2002-Rk/financial-research-agent.git
cd financial-research-agent
nano .env
docker compose up --build -d
```

5. Access at `http://<your-ec2-public-ip>:8000`

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `TAVILY_API_KEY` | Yes | Tavily Search API key |
| `ALPHA_VANTAGE_API_KEY` | Yes | Alpha Vantage API key (fundamental data) |
| `REDIS_URL` | Yes | Redis connection URL |
| `OPENAI_MODEL` | No | Model name (default: `gpt-4o`) |
| `REDIS_CACHE_TTL` | No | Cache TTL in seconds (default: `900`) |
| `REDIS_SESSION_TTL` | No | Session TTL in seconds (default: `3600`) |

---

## Known Limitations

- **Alpha Vantage free tier** is limited to 25 API calls/day. Fundamental data may be unavailable for less common tickers.
- **INSUFFICIENT_DATA** is returned when confidence falls below threshold (e.g., extreme volatility + negative sentiment with no fundamentals). This is intentional — the system refuses to guess.
- **Not financial advice.** This is a personal portfolio project for demonstrating AI system design. Do not use it to make real investment decisions.

---

## License

MIT
