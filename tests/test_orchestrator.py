# Import SimpleNamespace to construct simulated AI responses.
from types import SimpleNamespace

# Import patch to replace external dependencies during testing.
from unittest.mock import patch

# Import our analytics agent.
from agents.orchestrator import run_analytics_agent


# Verify that the agent executes the correct Azure SQL tool.
@patch("agents.orchestrator.get_olist_revenue_summary")
@patch("agents.orchestrator.create_model_client")
def test_agent_calls_olist_revenue_tool(mock_client_factory, mock_revenue):

    # Simulate the business data returned by our analytics tool.
    mock_revenue.return_value = {
        "quarter_a": "2017-Q1",
        "quarter_b": "2017-Q2",
        "sales_a": 705220.61,
        "sales_b": 1251931.30,
        "percentage_change": 77.52,
        "currency": "BRL",
    }

    # Simulate the AI model requesting our Azure SQL tool.
    tool_call = SimpleNamespace(
        type="function_call",
        name="get_olist_revenue_summary",
        arguments='{"quarter_a":"2017-Q1","quarter_b":"2017-Q2"}',
        call_id="call_test_001",
    )

    # Simulate the model's initial response.
    first_response = SimpleNamespace(
        id="response_001",
        output=[tool_call],
        output_text="",
    )

    # Simulate the model's final response after receiving tool results.
    final_response = SimpleNamespace(
        id="response_002",
        output=[],
        output_text="Sales increased by 77.52%.",
    )

    # Configure the simulated model to return these responses in order.
    mock_client_factory.return_value.responses.create.side_effect = [
        first_response,
        final_response,
    ]

    # Execute our actual orchestrator logic.
    result = run_analytics_agent(
        "Compare Olist sales between 2017-Q1 and 2017-Q2."
    )

    # Verify that the approved Azure SQL tool was executed.
    mock_revenue.assert_called_once_with(
        quarter_a="2017-Q1",
        quarter_b="2017-Q2",
    )

    # Verify that the tool call was recorded for traceability.
    assert result["tool_calls"][0]["name"] == "get_olist_revenue_summary"

    # Verify that the agent returned the model's final answer.
    assert result["answer"] == "Sales increased by 77.52%."

    # Verify that the model was called twice.
    assert mock_client_factory.return_value.responses.create.call_count == 2
