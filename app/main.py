
# Import FastAPI to build our backend HTTP service.
from fastapi import FastAPI, HTTPException

# Import Pydantic for request validation.
from pydantic import BaseModel, Field

# Import our analytics agent.
from agents.orchestrator import run_analytics_agent

# Import the factory for creating our authenticated model client.
from app.model_client import create_model_client

# Import the configured Azure model deployment.
from app.config import settings

# Import our Azure AI Search RAG answer generator.
from rag.answer_generator import answer_document_question

# Import FastAPI's dependency injection mechanism.
from fastapi import Depends

# Import our human-user authorization dependency.
from app.auth import require_human_role

# Import FastAPI middleware for controlling browser cross-origin requests.
from fastapi.middleware.cors import CORSMiddleware

# Create the FastAPI application.
app = FastAPI(title="Enterprise Decision & Action Copilot")

# Allow our local Next.js frontend to communicate with FastAPI.
app.add_middleware(
    # Use FastAPI's built-in CORS middleware.
    CORSMiddleware,

    # Allow requests only from our local frontend during development.
    allow_origins=["http://localhost:3000"],

    # Do not enable cookie-based cross-origin credentials.
    allow_credentials=False,

    # Allow the HTTP methods our frontend will use.
    allow_methods=["GET", "POST", "OPTIONS"],

    # Allow the Authorization header used for Microsoft access tokens.
    allow_headers=["Authorization", "Content-Type"],
)

# Define the expected structure of an incoming question.
class QuestionRequest(BaseModel):
    # Require a non-empty question and limit its length.
    question: str = Field(min_length=1, max_length=2000)


# Define a basic health-check endpoint.
@app.get("/health")
def health_check():
    # Return a simple indication that the API is running.
    return {"status": "ok"}


# Define the endpoint that executes the analytics agent.
@app.post("/api/v1/analytics/ask")
def ask_analytics_agent(
    request: QuestionRequest,
    # Reject requests without a valid token, scope, and Copilot.User role.
    claims: dict = Depends(require_human_role("Copilot.User")),
):
    # Execute the agent and return its structured result.
    try:
        # Forward the validated question to the agent.
        return run_analytics_agent(request.question)

    # Handle unexpected failures without exposing internal details.
    except Exception as exc:
        # Log the failure locally for debugging.
        print(f"Analytics agent error: {type(exc).__name__}: {exc}")

        # Return a generic server error to the API caller.
        raise HTTPException(
            status_code=500,
            detail="Analytics agent request failed.",
        ) from exc

# Create an endpoint for verifying cloud-to-model connectivity.
@app.get("/api/v1/model/test")
def test_model_connection(
    # Require a valid Microsoft token, API scope, and Copilot.User role.
    claims: dict = Depends(require_human_role("Copilot.User")),
):
    # Create a client using the current environment's Azure identity.
    client = create_model_client()

    # Send a small request to our deployed GPT model.
    response = client.responses.create(
        model=settings.azure_openai_deployment,
        input="Reply with exactly: Azure model connection successful.",
        max_output_tokens=150,
    )

    # Return a small response without exposing credentials.
    return {
        "status": response.status,
        "answer": response.output_text,
        "model": settings.azure_openai_deployment,
    }

# Define an endpoint for answering questions from enterprise documents.
@app.post("/api/v1/documents/ask")
def ask_documents(
    request: QuestionRequest,
    # Require a valid token with Copilot.Access and Copilot.User.
    claims: dict = Depends(require_human_role("Copilot.User")),
):

    # Handle failures without exposing internal Azure details to clients.
    try:

        # Retrieve relevant PDF passages and generate a grounded answer.
        result = answer_document_question(request.question)

        # Return the answer together with its source citations.
        return result

    # Catch errors from Azure AI Search or Microsoft Foundry.
    except Exception as exc:

        # Log the exception locally to help diagnose failures.
        print(f"Document RAG error: {type(exc).__name__}: {exc}")

        # Return a generic HTTP 500 error to the caller.
        raise HTTPException(
            status_code=500,
            detail="Document question request failed.",
        ) from exc


# Return the identity of an authenticated Copilot user.
@app.get("/api/v1/auth/me")
def get_current_user(
    # Require the Copilot.User role and Copilot.Access scope.
    claims: dict = Depends(require_human_role("Copilot.User")),
):
    # Return safe identity information from the verified token.
    return {
        "authenticated": True,
        "user_id": claims["oid"],
        "roles": claims.get("roles", []),
    }

# Provide a unified entry point for analytics and document intelligence.
@app.post("/api/v1/copilot/ask")
def ask_copilot(
    request: QuestionRequest,
    # Require Microsoft authentication and the Copilot.User role.
    claims: dict = Depends(require_human_role("Copilot.User")),
):
    # Handle model, SQL, and search failures without exposing internals.
    try:
        # Let the existing orchestrator select and execute permitted tools.
        # Execute the existing AI orchestrator.
        result = run_analytics_agent(request.question)

        # Preserve the existing response format for the frontend.
        return result

    # Convert unexpected backend errors into a safe HTTP response.
    except Exception as exc:
        # Record the error type for local troubleshooting.
        print(f"Copilot error: {type(exc).__name__}: {exc}")

        # Avoid leaking credentials or internal Azure details.
        raise HTTPException(
            status_code=500,
            detail="Copilot request failed.",
        ) from exc
