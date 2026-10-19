# Import patch to replace the AI agent during testing.
from unittest.mock import patch

# Import FastAPI's test client for simulating HTTP requests.
from fastapi.testclient import TestClient

# Import our existing FastAPI application.
from app.main import app

# Create a client that can test our API without running a server.
client = TestClient(app)


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
    mock_agent.assert_called_once_with("How did Olist sales change?")


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
