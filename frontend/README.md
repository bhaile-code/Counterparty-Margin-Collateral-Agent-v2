# Frontend - Margin Collateral Agent

React frontend for AI-powered OTC derivatives collateral management.

## Status

**Phase 7**: Planned (not yet implemented)

This frontend will provide a modern UI for document review, margin calculations, and AI-generated explanations.

---

## Planned Features

### 1. Document Management
- Drag-and-drop PDF upload interface
- Real-time processing status tracker
  - Upload → Parse → Extract → Normalize → Map
- Document list with metadata and timestamps
- Document deletion with confirmation

### 2. CSA Terms Review
- Display extracted fields with confidence scores
- Interactive editor for normalized collateral items
- Flag UNKNOWN types for manual review
- Save and update edited terms
- View source document pages with bounding boxes

### 3. Calculation Dashboard
- Input form for market data
  - Current exposure
  - Posted collateral (with type and amount)
- Execute margin calculations
- View 5-step calculation breakdown
  - Net exposure
  - Collateral haircuts
  - Threshold application
  - MTA check
  - Rounding
- Historical calculations table with filters

### 4. Explanation Viewer
- AI-generated narrative with contract citations
- Highlighted key factors driving the calculation
- Step-by-step calculation details with CSA references
- Interactive audit trail timeline
- Risk assessment panel with recommendations
- Citation links to source document pages

### 5. Multi-Agent Reasoning (Advanced Mode)
- Collateral agent reasoning chain (6 steps)
- Temporal agent reasoning (4 steps)
- Currency agent reasoning (3 steps)
- Validation report with warnings
- Confidence scores and human review flags

---

## Planned Tech Stack

- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **UI Library**: TBD (Material-UI / Tailwind CSS / shadcn/ui)
- **State Management**: TBD (Zustand / Redux Toolkit)
- **API Client**: TanStack Query (React Query) + Axios
- **Forms**: React Hook Form + Zod validation
- **Routing**: React Router v6
- **Charts**: Recharts / Chart.js (for visualization)

---

## Quick Start (When Implemented)

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

---

## API Integration

Will connect to backend at `http://localhost:8000`:

**Document Endpoints**:
- `POST /api/v1/documents/upload`
- `POST /api/v1/documents/parse/{document_id}`
- `POST /api/v1/documents/extract/{parse_id}`
- `POST /api/v1/documents/normalize/{extraction_id}`
- `POST /api/v1/documents/map/{document_id}`
- `GET /api/v1/documents/list`

**Calculation Endpoints**:
- `POST /api/v1/calculations/calculate`
- `POST /api/v1/calculations/{calculation_id}/explain`
- `GET /api/v1/calculations/{calculation_id}`
- `GET /api/v1/calculations/`

See [backend/README.md](../backend/README.md) for complete API documentation.

---

## Development Plan

1. **Phase 7.1**: Project setup
   - Initialize Vite + React + TypeScript
   - Configure routing and state management
   - Setup API client with TanStack Query
   - Create base layout and navigation

2. **Phase 7.2**: Document upload flow
   - File upload component with drag-and-drop
   - Processing status indicator
   - Document list with search and filters

3. **Phase 7.3**: CSA terms review interface
   - Display extracted fields in organized sections
   - Editable collateral table
   - Confidence score indicators
   - UNKNOWN type flagging

4. **Phase 7.4**: Calculation dashboard
   - Market data input form
   - Execute calculation button
   - Results display with breakdown
   - Historical calculations table

5. **Phase 7.5**: Explanation viewer
   - Narrative display with citations
   - Key factors panel
   - Step-by-step calculation details
   - Audit trail timeline

6. **Phase 7.6**: Multi-agent reasoning
   - Reasoning chains viewer
   - Validation report display
   - Confidence scores

7. **Phase 7.7**: Polish and testing
   - Responsive design
   - Error handling
   - Loading states
   - Unit and integration tests

---

## UI/UX Goals

- **Clarity**: Clear information hierarchy for complex financial data
- **Transparency**: Full visibility into AI reasoning and calculations
- **Efficiency**: Streamlined workflow for daily operations
- **Trust**: Prominent display of audit trails and citations
- **Accessibility**: WCAG 2.1 AA compliance

---

Financial AI Hackathon 2025
