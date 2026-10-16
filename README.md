# Enterprise Decision & Action Copilot

An Azure-based AI engineering portfolio project for building an enterprise copilot that answers business questions, analyzes structured data, retrieves organizational knowledge, and supports controlled business actions.

> **Project status:** Active development. The initial SQL analytics agent works locally, and the FastAPI backend has been deployed and health-tested on Azure Container Apps. Full cloud AI integration, RAG, action workflows, and frontend development are in progress.

## Business Problem

Enterprise teams often need to combine information from business databases and internal documents to understand performance, investigate problems, and decide what to do next.

This project explores how an AI copilot can bring these capabilities together through a secure, extensible architecture.

## Current Architecture

- **Backend:** Python, FastAPI
- **AI model:** GPT-5.4-mini deployed through Microsoft Foundry
- **AI integration:** OpenAI Python SDK and model tool calling
- **Structured data:** SQLite for local development
- **Containerization:** Docker
- **Container registry:** Azure Container Registry
- **Cloud hosting:** Azure Container Apps
- **Infrastructure as Code:** Azure Bicep
- **Cloud identity:** Microsoft Entra ID, Managed Identity, Azure RBAC

## Implemented Capabilities

- FastAPI backend with a health-check endpoint
- Business analytics endpoint using an LLM and SQL-backed tool
- Revenue summary tool for structured business analysis
- Local model orchestration and tool-calling test
- Dockerized backend running as a non-root user
- Azure infrastructure deployment using Bicep
- Container image published to Azure Container Registry
- Private Azure Container Apps deployment
- Successful cloud health-check verification
- Managed Identity and RBAC configuration

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Application health check |
| POST | `/api/v1/analytics/ask` | Business analytics questions |
| GET | `/api/v1/model/test` | Temporary development-only model connectivity test |

The model-testing endpoint is intended for development and must be removed or protected before public exposure.

## Development Roadmap

- [x] Initial architecture and technology selection
- [x] Local FastAPI and SQL analytics prototype
- [x] Docker containerization
- [x] Azure Container Registry deployment
- [x] Azure Container Apps deployment and health verification
- [ ] Verify cloud-to-model authentication and inference
- [ ] Integrate Azure SQL
- [ ] Implement document ingestion and RAG with Azure AI Search
- [ ] Build agent orchestration across data and knowledge tools
- [ ] Add human-approved business actions and audit logging
- [ ] Build a Next.js frontend
- [ ] Implement authentication, authorization, and security controls
- [ ] Add automated testing, AI evaluations, and observability
- [ ] Implement GitHub Actions CI/CD
- [ ] Prepare a complete demonstration and technical case study

## Security Approach

The project uses Azure Managed Identity and RBAC for cloud resource access, avoiding hardcoded Azure API credentials. The deployed API currently uses private ingress.

Production readiness will require additional controls, including API authentication, authorization, secure tool execution, auditing, and evaluation.

## Infrastructure

Azure resources are defined in `infrastructure/main.bicep`.

The compiled ARM template is generated from Bicep and is not maintained separately in source control.

## Repository Structure

- `app/` — FastAPI application and model client
- `agents/` — AI orchestration and tools
- `data/` — Database access and local development data support
- `infrastructure/` — Azure infrastructure definitions
- `tests/` — Application tests
- `docs/` — Technical documentation
- `evaluations/` — Planned AI evaluation assets

## Project Goals

This project is being developed as a hands-on demonstration of Azure AI engineering, agentic AI, enterprise RAG, cloud infrastructure, security, and production-oriented software development.

It is an educational and portfolio project, not yet a production-ready enterprise application.
