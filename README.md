# Margin Collateral Agent

> AI-Powered OTC Derivatives Collateral Management under ISDA/CSA Agreements

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![Tests](https://img.shields.io/badge/Tests-24%2F24%20Passing-success.svg)](backend/tests/)
[![Status](https://img.shields.io/badge/Status-MVP%20Development-yellow.svg)]()

**Financial AI Hackathon Championship 2025** | **Demo Date**: November 9, 2025

---

## What This Does

Automates margin calculations for OTC derivatives by reading CSA contracts, extracting terms, normalizing collateral data, calculating margin requirements, and explaining results with full audit trails.

**Problem**: Manual CSA processing takes hours per counterparty and is error-prone
**Solution**: Automated extraction → normalization → calculation → explanation with AI

**How it works**:
1. **Extracts** CSA terms from PDFs (LandingAI ADE)
2. **Normalizes** collateral tables with AI (Claude Haiku)
3. **Calculates** margin requirements (deterministic engine)
4. **Explains** results with citations (Claude Sonnet 4.5)
5. **Tracks** complete audit trails for compliance

---

## How to Run

### Quick Start

```bash
# 1. Install dependencies
cd backend
uv sync

# 2. Configure API keys
cp .env.example .env
# Edit .env: Add your LANDINGAI_API_KEY and ANTHROPIC_API_KEY

# 3. Start the backend server
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 4. Access the API
# - API Docs: http://localhost:8000/docs
# - Health Check: http://localhost:8000/health
```

### Complete Workflow

**Upload → Parse → Extract → Normalize → Calculate → Explain**

1. **Upload CSA PDF**: `POST /api/v1/documents/upload`
2. **Parse Document**: `POST /api/v1/documents/parse/{document_id}`
3. **Extract Fields**: `POST /api/v1/documents/extract/{parse_id}`
4. **Normalize Collateral**: `POST /api/v1/documents/normalize/{extraction_id}`
5. **Map to CSATerms**: `POST /api/v1/documents/map/{document_id}`
6. **Calculate Margin**: `POST /api/v1/calculations/calculate`
7. **Generate Explanation**: `POST /api/v1/calculations/{calculation_id}/explain`

See [backend/README.md](backend/README.md) for detailed API usage examples.

### Run Tests

```bash
cd backend
uv run pytest tests/ -v  # 24/24 passing
```

### Prerequisites

- **Python**: 3.11 or 3.12
- **uv**: Fast Python package installer ([install here](https://github.com/astral-sh/uv))
- **API Keys**: [LandingAI](https://landing.ai), [Anthropic](https://anthropic.com)

---



## Project Structure

```
Counterparty Margin Collateral Agent v2/
├── backend/                 # FastAPI + Python 3.11
│   ├── app/
│   │   ├── api/             # 21 REST endpoints
│   │   ├── agents/          # Multi-agent normalization system
│   │   ├── core/            # Margin calculation engine
│   │   ├── models/          # 23+ Pydantic schemas
│   │   ├── services/        # ADE, LLM, normalization
│   │   └── utils/           # File storage & utilities
│   ├── data/                # 7-layer persistence (PDFs → explanations)
│   └── tests/               # 24+ passing tests
├── frontend/                # React (Phase 7 - planned)
└── docs/                    # Architecture & domain knowledge
```

## Features

**Implemented (Phases 1-5)**
- Document upload & ADE integration (parse/extract workflow)
- AI-powered collateral normalization (single & multi-agent modes)
- Deterministic margin calculation engine (5-step process)
- AI explanations with contract citations (Claude Sonnet 4.5)
- Multi-agent reasoning chains with self-correction
- Complete audit trails & provenance tracking
- 21 API endpoints, 24+ passing tests, 23+ Pydantic models

**Planned (Phases 6-7)**
- Enhanced backend APIs & export features
- React frontend for document review & calculations

## API Overview

**21 Total Endpoints** across 5 categories:

| Category | Endpoints | Description |
|----------|-----------|-------------|
| **Document Management** | 7 | Upload, parse, extract, list, delete |
| **Normalization** | 6 | Single-agent & multi-agent with reasoning |
| **CSA Terms** | 2 | Mapping & retrieval |
| **Calculations** | 5 | Margin calc & AI explanations |
| **System** | 3 | Health, docs, root |

**Interactive API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

See [backend/README.md](backend/README.md) for complete endpoint list and usage examples.

## Testing

**24/24 tests passing** with 100% coverage on calculation engine

```bash
cd backend
uv run pytest tests/ -v
```

Tests cover: core calculations, scenarios, edge cases, determinism, and provenance tracking.

---

## Key Differentiators

1. **Deterministic Calculations** - Same input = same output (regulatory compliance)
2. **Full Audit Trail** - Every step logged with formulas & CSA clause references
3. **AI Explainability** - Plain English explanations citing contract clauses
4. **Source Provenance** - Fields linked to PDF pages & coordinates
5. **Multi-Agent Reasoning** - Optional advanced mode with complete reasoning chains

## Technology Stack

**Backend**: FastAPI, Python 3.11+, Pydantic, pytest, uv
**AI/ML**: LandingAI ADE, Anthropic Claude (Haiku + Sonnet 4.5)
**Dev Tools**: ruff, black, mypy, httpx
**Frontend (Planned)**: React

---

## Status

**Phases 1-5 Complete** | 21 API endpoints | 24+ tests passing | Ready for demo

See [STATUS_UPDATE.md](docs/STATUS_UPDATE.md) for detailed progress tracking.

## Development

```bash
# Format & lint
cd backend
uv run black app/ tests/
uv run ruff check app/ tests/

# Type check
uv run mypy app/

# Test with coverage
uv run pytest tests/ --cov=app --cov-report=html
```


---

## License & Acknowledgments

**Proprietary** - Financial AI Hackathon Championship 2025

**Thanks to**: LandingAI (ADE), Anthropic (Claude AI), Financial AI Hackathon organizers

---

**Built for Financial AI Hackathon 2025** | v0.2.0 | Last Updated: November 6, 2025
