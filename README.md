# Enterprise Decision & Action Copilot

**An Azure-based Agentic AI Engineering Portfolio Project**

An evolving enterprise AI application that combines **business intelligence, structured data analytics, document intelligence (RAG), evidence-based reasoning, and human-approved business actions**.

**Current milestone:** `v0.1.0 — Analytics MVP (in development)`

> **Project status:** Active development. The Azure SQL analytics agent works locally, the FastAPI backend has been deployed and health-tested on Azure Container Apps, and automated tests are passing. Full cloud-to-database integration, document RAG, action workflows, and frontend development are planned.

---

## 1. Project Overview

Enterprise organizations rely on multiple information sources to make business decisions:

- Structured data stored in business databases.
- Internal documents containing policies, procedures, and business knowledge.
- Operational systems used to execute business processes.

Accessing and combining this information often requires navigating multiple applications, dashboards, and documents.

**Enterprise Decision & Action Copilot** aims to provide a unified conversational interface that enables business users to ask questions, investigate performance, retrieve relevant knowledge, and make evidence-based decisions.

### What the application aims to do

The full application will support five capabilities:

1. **Ask:** Understand business questions expressed in natural language.
2. **Analyze:** Query structured business data through approved analytics tools.
3. **Investigate:** Combine database analytics and document retrieval to explore business problems.
4. **Recommend:** Generate recommendations supported by traceable evidence.
5. **Act:** Execute authorized business workflows with human approval and audit logging.

The project is being developed incrementally, with each version introducing new capabilities.

---

## 2. Business Use Cases

The copilot is designed to support business scenarios such as:

**Sales Performance Analysis**

"How did our revenue change between Q1 and Q2?"

**Business Investigation**

"Which product categories contributed most to the decline in sales?"

**Customer Experience Analysis**

"Which products have the lowest customer satisfaction ratings?"

**Document Intelligence — Planned**

"What does our refund policy say about delayed deliveries?"

**Cross-Source Investigation — Planned**

"Are our delivery delays consistent with our customer service policies?"

**Decision and Action Workflows — Planned**

"Identify underperforming categories and prepare a corrective action plan for approval."

These scenarios represent the intended evolution of the system. Only the initial quarterly sales analytics capability is currently implemented.

---

## 3. Current System Architecture

The working local analytics workflow is:

```text
                    BUSINESS USER
                          |
                          v
                   FASTAPI BACKEND
                          |
                          v
                    AI ORCHESTRATOR
                          |
                          v
              MICROSOFT FOUNDRY
                 GPT-5.4-mini
                          |
                          v
                   AI TOOL CALLING
                          |
                          v
              APPROVED PYTHON TOOLS
                          |
                          v
                AZURE SQL DATABASE
                 OLIST BUSINESS DATA
                          |
                          v
                STRUCTURED RESULTS
                          |
                          v
                 AI-GENERATED ANSWER
                 + TOOL EXECUTION TRACE
```

### Architecture principles

- **Modularity:** Separate API, AI orchestration, analytics tools, and database access.
- **Controlled tool execution:** The model can invoke only explicitly registered functions.
- **Data grounding:** Numerical claims should come from database queries rather than model-generated estimates.
- **Traceability:** Record tool requests, arguments, results, and model response identifiers.
- **Secure authentication:** Use Microsoft Entra ID rather than hardcoded database credentials.
- **Incremental delivery:** Build, test, document, and release capabilities progressively.

The original SQLite analytics tool remains available for local regression testing.

---

## 4. Technology Stack

| Layer | Technology |
|---|---|
| Programming language | Python |
| Backend framework | FastAPI |
| AI platform | Microsoft Foundry |
| AI model | GPT-5.4-mini |
| AI integration | OpenAI Python SDK |
| Agent orchestration | Function calling / tool calling |
| Structured business database | Azure SQL Database |
| Local prototype database | SQLite |
| SQL connectivity | pyodbc, Microsoft ODBC Driver 18 |
| Authentication | Microsoft Entra ID, Azure Identity |
| Containerization | Docker |
| Container registry | Azure Container Registry |
| Cloud hosting | Azure Container Apps |
| Infrastructure as Code | Azure Bicep |
| Automated testing | pytest, unittest.mock, FastAPI TestClient |
| Version control | Git and GitHub |
| Document storage (planned) | Azure Blob Storage |
| Vector and document search (planned) | Azure AI Search |
| Frontend (planned) | Next.js |
| CI/CD (planned) | GitHub Actions |

---

## 5. Real-World Business Dataset

The project uses the **Brazilian E-Commerce Public Dataset by Olist**, containing historical e-commerce transactions, products, customers, sellers, payments, and customer reviews.

The dataset allows the copilot to operate on realistic relational business data instead of relying entirely on synthetic examples.

### Azure SQL data

Eight tables have been imported and verified:

| Table | Number of records |
|---|---:|
| `olist_customers` | 99,441 |
| `olist_products` | 32,951 |
| `olist_sellers` | 3,095 |
| `olist_category_translations` | 71 |
| `olist_orders` | 99,441 |
| `olist_order_items` | 112,650 |
| `olist_order_payments` | 103,886 |
| `olist_order_reviews` | 99,224 |
| **Total** | **550,759** |

### Data engineering components

- `data/olist_schema.sql` — SQL table definitions.
- `data/pipelines/import_olist.py` — Dataset ingestion pipeline.
- `data/azure_sql.py` — Reusable Azure SQL connection module.

The raw CSV datasets are excluded from Git to keep the repository focused on source code and reproducible implementation assets.

### Revenue metric definition

The initial revenue analytics tool calculates:

**Delivered-order item sales value = SUM(order item prices)**

It uses:

- `olist_orders` to identify purchase dates and order status.
- `olist_order_items` to calculate item sales values.
- Delivered orders only.
- Purchase dates to determine quarters.
- Brazilian reais (BRL) as the currency.

Freight charges are excluded.

This definition avoids mixing item prices with payment totals, which represent a different business measure.

---

## 6. Implemented AI Capabilities

### 6.1 Natural-language business analytics

Users can ask questions about quarterly sales performance.

The AI model interprets the question and selects the appropriate registered analytics tool.

### 6.2 Azure SQL analytics

The application connects to Azure SQL using Microsoft Entra authentication.

The initial real-data analytics tool is:

`get_olist_revenue_summary(quarter_a, quarter_b)`

It compares item sales value between two quarters and returns structured results.

### 6.3 Controlled AI tool calling

The orchestrator maintains a registry of permitted tools.

The AI model cannot directly execute arbitrary SQL through the implemented analytics workflow.

Instead, it calls predefined Python functions that execute parameterized SQL queries.

### 6.4 Evidence-based answers

The AI receives structured numerical results from the analytics tool and uses them to formulate its answer.

The orchestrator records:

- Tool name.
- Tool arguments.
- Tool result.
- Model response identifier.

This provides an initial level of execution traceability.

More comprehensive evidence tracing, including document citations and retrieval metadata, is planned.

---

## 7. Example: Real AI Analytics Result

### Business question

"How did delivered-order item sales value change between Q1 2017 and Q2 2017?"

### Verified results

| Metric | Result |
|---|---:|
| Q1 2017 sales | BRL 705,220.61 |
| Q2 2017 sales | BRL 1,251,931.30 |
| Absolute change | +BRL 546,710.69 |
| Percentage change | +77.52% |

### AI-generated interpretation

Delivered-order item sales value increased by 77.52% between Q1 and Q2 2017.

The increase represents approximately BRL 546,711 in additional item sales value, excluding freight.

The available calculation establishes the magnitude of the change but does not independently explain its causes.

### End-to-end validation

A successful local test confirmed that:

1. The AI model understood the business question.
2. The model selected `get_olist_revenue_summary`.
3. The Python tool queried Azure SQL.
4. Azure SQL returned the expected business figures.
5. The model generated an answer consistent with the tool results.

---

## 8. Backend API

The backend is implemented using FastAPI.

### Available endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application health check |
| POST | `/api/v1/analytics/ask` | Submit business questions to the AI agent |
| GET | `/api/v1/model/test` | Development-only model connectivity test |

### Example API request

**Endpoint:** `POST /api/v1/analytics/ask`

```json
{
  "question": "Compare Olist sales between 2017-Q1 and 2017-Q2."
}
```

### Response structure

The API returns:

- The AI-generated answer.
- The executed tool-call trace.
- The model response identifier.

The API is implemented, and its request-handling behavior is covered by automated tests.

Cloud-to-Azure-SQL connectivity remains to be validated separately.

The model connectivity test endpoint must be protected or removed before public exposure.

---

## 9. Automated Testing

The project uses **pytest** to validate its components.

### Current results

**8 tests passed — 0 failures**

| Test | Purpose |
|---|---|
| `test_revenue_decline` | Validate the original SQLite revenue calculation |
| `test_olist_revenue_growth` | Validate Azure SQL revenue calculations using mocked results |
| `test_olist_revenue_invalid_quarter` | Reject invalid quarter formats |
| `test_olist_revenue_missing_quarter` | Handle missing sales data |
| `test_agent_calls_olist_revenue_tool` | Verify AI tool orchestration |
| `test_analytics_api_success` | Validate successful API requests |
| `test_analytics_api_rejects_empty_question` | Validate API input protection |
| `test_health_endpoint` | Verify the health endpoint |

### Testing approach

The project distinguishes between:

**Unit tests**

Validate individual functions without external dependencies.

**Mocked integration tests**

Validate interactions between components using simulated model and database responses.

**Live integration tests**

Verify real connections to Azure SQL and Microsoft Foundry.

**End-to-end tests**

Validate the complete workflow from a business question to a grounded AI answer.

The current eight automated tests do not require live Azure resources.

A separate successful local end-to-end test has been performed using the real Azure AI model and Azure SQL database.

---

## 10. Development Setup

### Requirements

- Python and pip.
- A Python virtual environment.
- Microsoft ODBC Driver 18 for SQL Server.
- Appropriate Microsoft Entra credentials and Azure SQL access for live integration.
- Access to the configured Microsoft Foundry model deployment.

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run automated tests

```bash
python -m pytest -v
```

### Start the FastAPI backend

```bash
uvicorn app.main:app --reload
```

### API documentation

When the local server is running, FastAPI's interactive API documentation is available at:

`http://127.0.0.1:8000/docs`

Live Azure SQL functionality requires the necessary network access, permissions, and local ODBC dependencies.

---

## 11. Cloud Infrastructure

The project uses Azure infrastructure defined through Bicep.

### Implemented infrastructure components

- Azure Container Registry.
- Azure Container Apps.
- Azure SQL Database.
- Microsoft Foundry model deployment.
- Microsoft Entra authentication.
- Azure Managed Identity and RBAC configuration.

### Deployment status

The FastAPI backend has been deployed to Azure Container Apps and successfully health-tested.

The Azure SQL analytics workflow has been verified locally.

Secure cloud-to-SQL connectivity and database authorization for the deployed application remain to be completed.

Infrastructure definitions are maintained in:

`infrastructure/main.bicep`

---

## 12. Security Architecture

Security is an essential design consideration.

### Implemented practices

- Microsoft Entra authentication for Azure SQL access.
- No hardcoded SQL passwords in application code.
- Azure Managed Identity configured for cloud resources.
- Parameterized SQL queries.
- Explicitly registered AI tools.
- Separation of application configuration and implementation.
- Exclusion of `.env` files, raw datasets, and local databases from Git.

### Security work remaining

- Dedicated least-privilege Azure SQL identities.
- Secure connectivity between Azure Container Apps and Azure SQL.
- Removal of temporary development firewall rules.
- API authentication and authorization.
- Protection or removal of development-only endpoints.
- Secrets scanning and dependency security checks.
- Monitoring and audit logging.
- Authorization and approval policies for business actions.

The project is not yet production-ready.

---

## 13. Evidence Tracing and Explainability

An enterprise AI system should be able to explain **where its information came from and how its conclusions were reached**.

### Current implementation

The AI orchestrator captures the executed tool, its arguments, returned result, and model response identifier.

### Planned enhancements

Future versions will add:

- Database source identifiers.
- Document references and citations.
- Retrieved passages and retrieval scores.
- Query execution metadata.
- Model and tool execution details.
- Evaluation results.
- Human approval records.
- Action execution history.

The objective is to make AI-assisted decisions traceable and auditable.

---

## 14. Versioned Development Roadmap

The project follows an incremental release strategy.

### v0.1.0 — Analytics MVP

**Goal:** Establish a working AI analytics foundation.

- [x] Create the FastAPI backend.
- [x] Implement initial AI tool calling.
- [x] Deploy initial backend infrastructure.
- [x] Import real Olist data into Azure SQL.
- [x] Implement quarterly sales analytics.
- [x] Validate local end-to-end AI analytics.
- [x] Implement eight automated tests.
- [ ] Finalize technical and release documentation.
- [ ] Validate secure cloud-to-SQL integration.
- [ ] Review deployment security and permissions.
- [ ] Create the official GitHub release.

### v0.2.0 — Business Intelligence Agent

**Goal:** Expand the copilot's analytical capabilities.

Planned features:

- Product and category performance analysis.
- Regional sales analysis.
- Customer satisfaction analysis.
- Sales trends and comparisons.
- Multi-step business investigations.
- Improved analytical tool selection.

### v0.3.0 — Document Intelligence and RAG

**Goal:** Enable the copilot to understand organizational documents.

Planned features:

- Document ingestion.
- Azure Blob Storage integration.
- Azure AI Search indexing and retrieval.
- Retrieval-augmented generation.
- Document citations and evidence tracing.
- Combined database and document analysis.

### v0.4.0 — Decision and Action Workflows

**Goal:** Move from answering questions to supporting controlled actions.

Planned features:

- Business recommendations.
- Action planning.
- Human approval workflows.
- Authorized action execution.
- Audit logging and action history.

### v1.0.0 — Portfolio-Ready Enterprise Copilot

**Goal:** Deliver a complete, demonstrable application.

Planned features:

- Next.js frontend.
- Secure cloud deployment.
- Authentication and authorization.
- GitHub Actions CI/CD.
- AI evaluations.
- Monitoring and observability.
- Architecture documentation.
- Complete technical case study.
- End-to-end demonstration.

Version targets may evolve as implementation progresses.

---

## 15. Repository Structure

```text
azure-agentic-enterprise-copilot/
|
|-- app/
|   |-- main.py
|   |-- config.py
|   |-- model_client.py
|
|-- agents/
|   |-- orchestrator.py
|   |-- tools/
|       |-- revenue.py
|       |-- olist_revenue.py
|
|-- data/
|   |-- azure_sql.py
|   |-- database.py
|   |-- olist_schema.sql
|   |-- pipelines/
|       |-- import_olist.py
|
|-- infrastructure/
|   |-- main.bicep
|
|-- tests/
|   |-- test_revenue.py
|   |-- test_olist_revenue.py
|   |-- test_orchestrator.py
|   |-- test_api.py
|
|-- Dockerfile
|-- requirements.txt
|-- .gitignore
|-- README.md
```

Additional documentation, evaluation assets, and frontend components will be introduced as the project evolves.

---

## 16. Engineering and GitHub Workflow

Development follows an iterative engineering process:

**Design → Implement → Test → Document → Commit → Release → Improve**

### Development principles

- Implement one capability at a time.
- Keep application components modular.
- Add automated tests for new functionality.
- Document architectural decisions.
- Use descriptive Git commits.
- Track progress through versioned milestones.
- Create GitHub release tags only after release requirements are satisfied.
- Preserve reproducibility and security throughout development.

### Versioning

The project uses version identifiers such as:

- `v0.1.0` — Initial analytics MVP.
- `v0.2.0` — Expanded business intelligence.
- `v0.3.0` — Document intelligence and RAG.
- `v0.4.0` — Controlled decision and action workflows.
- `v1.0.0` — Portfolio-ready release.

These are planned milestones, not claims that the releases have already been published.

---

## 17. Long-Term Vision

The final objective is to build an enterprise AI copilot that can:

- Understand business questions.
- Analyze real operational data.
- Retrieve and interpret organizational documents.
- Investigate business problems using multiple tools.
- Generate evidence-based insights.
- Explain conclusions using traceable sources.
- Recommend business actions.
- Execute authorized workflows with human oversight.

The project is designed to demonstrate practical skills in:

**Azure AI Engineering · Agentic AI · RAG · Business Intelligence · Data Engineering · Cloud Architecture · Software Engineering · AI Security · MLOps/LLMOps**

---

## 18. Project Status

**Active development — v0.1.0 Analytics MVP**

The current implementation demonstrates a working local Azure SQL analytics agent, tested AI tool orchestration, and a FastAPI backend with automated tests.

Document intelligence, multi-agent workflows, advanced business investigations, and human-approved actions are planned for subsequent releases.

The project is continuously evolving toward a secure, observable, and portfolio-ready enterprise AI application.