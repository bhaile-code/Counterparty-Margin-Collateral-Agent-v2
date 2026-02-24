# Backend - Margin Collateral Agent

FastAPI backend for AI-powered OTC derivatives collateral management.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env: Add LANDINGAI_API_KEY and ANTHROPIC_API_KEY

# 3. Run server
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 4. Run tests
uv run pytest tests/ -v  # 24/24 passing
```

**API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
**Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Complete Workflow Example

```bash
# Upload CSA PDF
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@sample_csa.pdf"
# Returns: {"document_id": "abc-123"}

# Parse document (ADE Step 1)
curl -X POST http://localhost:8000/api/v1/documents/parse/abc-123
# Returns: {"parse_id": "parse_abc-123_timestamp"}

# Extract fields (ADE Step 2)
curl -X POST http://localhost:8000/api/v1/documents/extract/parse_abc-123_timestamp
# Returns: {"extraction_id": "extract_abc-123_timestamp", ...}

# Normalize collateral (AI-powered)
curl -X POST http://localhost:8000/api/v1/documents/normalize/extract_abc-123_timestamp
# Returns: {"collateral_items_count": 10, ...}

# Map to CSATerms
curl -X POST http://localhost:8000/api/v1/documents/map/abc-123
# Returns: {"status": "mapped", ...}

# Calculate margin
curl -X POST http://localhost:8000/api/v1/calculations/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "csa_terms": {...},
    "market_data": {
      "current_exposure": 5500000,
      "posted_collateral": [{"type": "CASH", "amount": 3000000, "currency": "USD"}]
    }
  }'
# Returns: {"calculation_id": "calc-xyz", "margin_call_amount": 2500000, ...}

# Generate AI explanation
curl -X POST http://localhost:8000/api/v1/calculations/calc-xyz/explain
# Returns: {"explanation_id": "exp-123", "narrative": "...", ...}
```

---

## API Endpoints (21 Total)

### Document Management (7 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload CSA PDF document |
| POST | `/api/v1/documents/parse/{document_id}` | Parse document (ADE Step 1) |
| POST | `/api/v1/documents/extract/{parse_id}` | Extract fields (ADE Step 2) |
| GET | `/api/v1/documents/extractions/{extraction_id}` | Retrieve extraction results |
| GET | `/api/v1/documents/parses/{parse_id}` | Retrieve parse results |
| GET | `/api/v1/documents/list` | List all uploaded documents |
| DELETE | `/api/v1/documents/{document_id}` | Delete a document |

### Normalization - Single Agent (2 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/normalize/{extraction_id}` | AI-powered collateral normalization (Claude Haiku) |
| GET | `/api/v1/documents/normalized/{document_id}` | Retrieve normalized collateral table |

### Normalization - Multi-Agent (4 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/normalize-multiagent/{extraction_id}` | Advanced multi-agent normalization with reasoning chains |
| GET | `/api/v1/documents/normalized-multiagent/{normalized_id}/reasoning` | Get all agent reasoning chains |
| GET | `/api/v1/documents/normalized-multiagent/{normalized_id}/reasoning/{agent}` | Get specific agent reasoning (collateral, temporal, currency) |
| GET | `/api/v1/documents/normalized-multiagent/{normalized_id}/validation` | Get validation report with warnings |

### CSA Terms (2 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/map/{document_id}` | Map extraction + normalized data → CSATerms |
| GET | `/api/v1/documents/csa-terms/{document_id}` | Retrieve saved CSATerms |

### Calculations (5 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/calculations/calculate` | Calculate margin requirement |
| POST | `/api/v1/calculations/{calculation_id}/explain` | Generate AI explanation with citations |
| GET | `/api/v1/calculations/{calculation_id}` | Retrieve calculation result |
| GET | `/api/v1/calculations/{calculation_id}/explanation` | Retrieve explanation |
| GET | `/api/v1/calculations/` | List all calculations |

### System (3 endpoints)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Root endpoint |
| GET | `/health` | Health check with API status |
| GET | `/docs` | Interactive API documentation (Swagger UI) |

---

## Project Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration & environment
│   ├── api/                 # 21 REST endpoints
│   │   ├── documents.py     # Document management (16 endpoints)
│   │   └── calculations.py  # Margin calc & explanations (5 endpoints)
│   ├── agents/              # Multi-agent normalization system
│   │   ├── orchestrator.py
│   │   ├── collateral_agent.py
│   │   ├── temporal_agent.py
│   │   ├── currency_agent.py
│   │   └── validation_agent.py
│   ├── core/
│   │   └── calculator.py    # Deterministic margin calculation engine
│   ├── models/              # 23+ Pydantic schemas
│   ├── services/            # ADE, LLM, normalization
│   └── utils/               # File storage & utilities
├── data/                    # 7-layer persistence
│   ├── pdfs/                # Uploaded CSA PDFs
│   ├── parsed/              # ADE parse results
│   ├── extractions/         # ADE extracted fields
│   ├── normalized_collateral/
│   ├── csa_terms/
│   ├── calculations/
│   └── explanations/
├── tests/                   # 24+ passing tests
│   ├── test_calculator.py
│   ├── test_agents.py
│   ├── test_normalization.py
│   └── integration/
├── .env                     # Environment config (git-ignored)
├── pyproject.toml           # Dependencies & project config
└── uv.lock                  # Locked dependencies
```

---

## Environment Variables

Required in `.env` file:

```bash
# API Keys (Required)
LANDINGAI_API_KEY=your_landingai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
DEBUG=false
LOG_LEVEL=INFO
```

---

## Key Components

### Core Services
| Component | Purpose |
|-----------|---------|
| [calculator.py](app/core/calculator.py) | Deterministic 5-step margin calculation engine |
| [ade_service.py](app/services/ade_service.py) | LandingAI document extraction integration |
| [collateral_normalizer.py](app/services/collateral_normalizer.py) | AI-powered collateral normalization (single-agent) |
| [llm_service.py](app/services/llm_service.py) | Claude AI for explanations with citations |
| [documents.py](app/api/documents.py) | Document management API (16 endpoints) |
| [calculations.py](app/api/calculations.py) | Margin calculations & explanations (5 endpoints) |

### Multi-Agent Normalization System

For high-stakes CSAs requiring maximum transparency and complete audit trails.

| Agent | Steps | Purpose |
|-------|-------|---------|
| **CollateralNormalizerAgent** | 6 | Standardize collateral types & extract maturity buckets |
| **TemporalNormalizerAgent** | 4 | Infer timezones from valuation times |
| **CurrencyNormalizerAgent** | 3 | Standardize to ISO 4217 |
| **ValidationAgent** | N/A | Cross-field consistency checks & business rules |

**Features**:
- Complete reasoning chains for full audit trails
- Self-correction capabilities (auto-fix taxonomy errors)
- Context-aware timezone inference
- Confidence scoring & human review flagging
- 4 dedicated API endpoints for reasoning retrieval

**When to use**:
- High-stakes CSAs requiring regulatory review
- Complex collateral schedules with ambiguities
- Need for complete transparency in AI decisions
- Audit requirements for AI reasoning

See [MULTI_AGENT_NORMALIZATION.md](../docs/MULTI_AGENT_NORMALIZATION.md) for details.

---

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Format & lint
uv run black app/ tests/
uv run ruff check app/ tests/

# Type check
uv run mypy app/

# Test with coverage
uv run pytest tests/ --cov=app --cov-report=html
```

---

## Testing

**24+ tests passing** with 100% coverage on calculation engine.

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test categories
uv run pytest tests/test_calculator.py -v        # Core calculations
uv run pytest tests/test_agents.py -v            # Agent logic
uv run pytest tests/test_normalization.py -v     # Integration

# Run with coverage
uv run pytest tests/ --cov=app --cov-report=html

# Run multi-agent integration tests
uv run python tests/integration/test_multiagent_normalization.py
```

**Test Coverage**:
- Core calculations (8 tests): Margin calc, haircuts, rounding
- Scenarios (4 tests): Thresholds, MTA, multiple collateral
- Edge cases (6 tests): Negative exposure, large numbers, invalid inputs
- Determinism (2 tests): Reproducibility, order independence
- Provenance (4 tests): Audit trails, formulas, CSA references
- Agent logic: Ambiguity detection, self-correction, validation
- Integration: Multi-agent pipeline, reasoning chains

---

