# Import patch to replace the AI agent during testing.
from unittest.mock import patch

# Import FastAPI's test client for simulating HTTP requests.
from fastapi.testclient import TestClient

# Import our existing FastAPI application.
from app.main import app

# Create a client that can test our API without running a server.
client = TestClient(app)


# Import pytest to create a reusable test fixture.
import pytest


# Simulate an authorized Microsoft user for each API test.
@pytest.fixture(autouse=True)
def authenticated_test_user():

    # Find the analytics endpoint registered by FastAPI.
    route = next(
        route for route in app.routes
        if getattr(route, "path", None) == "/api/v1/analytics/ask"
    )

    # Retrieve the exact authentication dependency.
    auth_dependency = route.dependant.dependencies[0].call

    # Simulate verified Microsoft Entra claims.
    def mock_authenticated_user():
        return {
            "tid": "test-tenant-001",
            "oid": "test-user-001",
            "roles": ["Copilot.User"],
            "scp": "Copilot.Access",
        }

    # Override authentication for this test only.
    app.dependency_overrides[auth_dependency] = mock_authenticated_user

    # Execute the test with simulated authentication.
    try:
        yield

    # Restore the original authentication dependency afterward.
    finally:
        app.dependency_overrides.pop(auth_dependency, None)



# Verify that the API returns an AI-generated answer.
@patch("app.main.run_analytics_agent")
def test_analytics_api_success(mock_agent):

    # Simulate a successful response from our AI agent.
    mock_agent.return_value = {
        "answer": "Sales increased by 77.52%.",
        "tool_calls": [],
        "response_id": "test_response_001",
    }

    # Send a valid question to the API.
    response = client.post(
        "/api/v1/analytics/ask",
        json={"question": "How did Olist sales change?"},
    )

    # Verify that the HTTP request succeeded.
    assert response.status_code == 200

    # Verify that the API returned the expected answer.
    assert response.json()["answer"] == "Sales increased by 77.52%."

    # Verify that the API forwarded the question to our agent.
    mock_agent.assert_called_once()
    args, kwargs = mock_agent.call_args
    assert args == ("How did Olist sales change?",)
    assert kwargs["principal"].tenant_id == "test-tenant-001"
    assert kwargs["principal"].user_id == "test-user-001"


# Verify that empty questions are rejected.
@patch("app.main.run_analytics_agent")
def test_analytics_api_rejects_empty_question(mock_agent):

    # Send an empty question to the API.
    response = client.post(
        "/api/v1/analytics/ask",
        json={"question": ""},
    )

    # Verify that FastAPI rejects the invalid request.
    assert response.status_code == 422

    # Verify that the AI agent was never called.
    mock_agent.assert_not_called()


# Verify that our health-check endpoint works.
def test_health_endpoint():

    # Request the API's health status.
    response = client.get("/health")

    # Verify that the endpoint responds successfully.
    assert response.status_code == 200

    # Verify that the response contains the expected status.
    assert response.json() == {"status": "ok"}
