
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

# Create the FastAPI application.
app = FastAPI(title="Enterprise Decision & Action Copilot")


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
def ask_analytics_agent(request: QuestionRequest):
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
def test_model_connection():
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
