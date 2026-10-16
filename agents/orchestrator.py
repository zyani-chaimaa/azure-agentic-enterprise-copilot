
# Import JSON for decoding tool arguments and encoding tool results.
import json

# Import our Azure model client factory.
from app.model_client import create_model_client

# Import the configured model deployment name.
from app.config import settings

# Import the business analytics tool.
from agents.tools.revenue import get_revenue_summary
from agents.tools.olist_revenue import get_olist_revenue_summary


# Define the tools that the model is allowed to request.
TOOLS = [
    {
        "type": "function",
        "name": "get_olist_revenue_summary",
        "description": (
            "Compare historical Olist delivered-order item sales value "
            "between two quarters. Uses real Azure SQL data, excludes freight, "
            "and returns amounts in Brazilian reais (BRL)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "quarter_a": {
                    "type": "string",
                    "description": "Starting quarter, for example 2017-Q1.",
                },
                "quarter_b": {
                    "type": "string",
                    "description": "Ending quarter, for example 2017-Q2.",
                },
            },
            "required": ["quarter_a", "quarter_b"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_revenue_summary",
        "description": "Compare total revenue between two business quarters.",
        "parameters": {
            "type": "object",
            "properties": {
                "quarter_a": {
                    "type": "string",
                    "description": "Starting quarter, for example 2026-Q1.",
                },
                "quarter_b": {
                    "type": "string",
                    "description": "Ending quarter, for example 2026-Q2.",
                },
            },
            "required": ["quarter_a", "quarter_b"],
            "additionalProperties": False,
        },
        "strict": True,
    }
]


# Define the main entry point for our analytics agent.
def run_analytics_agent(question: str) -> dict:
    # Create an authenticated client for the Azure model.
    client = create_model_client()

    # Ask the model to reason about the question and available tools.
    response = client.responses.create(
        model=settings.azure_openai_deployment,
        instructions=(
            "You are an enterprise analytics assistant. "
            "Use tools for numerical business claims. "
            "Never invent business figures or unsupported causes. "
            "Explain the evidence and acknowledge missing information."
        ),
        input=question,
        tools=TOOLS,
        max_output_tokens=1500,
    )

    # Keep a record of which tools the model requested.
    tool_calls = []

    # Allow at most three rounds of tool execution.
    for _ in range(3):
        # Extract function calls from the model's response.
        requested_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        # Stop when the model no longer requests tools.
        if not requested_calls:
            break

        # Collect the results of the requested tool calls.
        tool_outputs = []

        # Process each function call returned by the model.
        for call in requested_calls:
            # Decode the model-generated function arguments.
            arguments = json.loads(call.arguments)

            # Execute only the explicitly permitted analytics tool.
            if call.name == "get_revenue_summary":
                result = get_revenue_summary(
                    quarter_a=arguments["quarter_a"],
                    quarter_b=arguments["quarter_b"],
                )

            # Execute the real Olist analytics tool when requested.
            elif call.name == "get_olist_revenue_summary":
                result = get_olist_revenue_summary(
                    quarter_a=arguments["quarter_a"],
                    quarter_b=arguments["quarter_b"],
                )

            # Reject any unexpected tool name.
            else:
                result = {"error": "Tool is not permitted."}

            # Record the tool request for observability.
            tool_calls.append(
                {"name": call.name, "arguments": arguments, "result": result}
            )

            # Return the tool result using the original call identifier.
            tool_outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                }
            )

        # Give the tool results back to the model for its next decision.
        response = client.responses.create(
            model=settings.azure_openai_deployment,
            previous_response_id=response.id,
            input=tool_outputs,
            tools=TOOLS,
            max_output_tokens=1500,
        )

    # Return the final answer and the executed tool-call trace.
    return {
        "answer": response.output_text,
        "tool_calls": tool_calls,
        "response_id": response.id,
    }
