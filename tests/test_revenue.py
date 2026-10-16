
# Import the analytics tool that we want to verify.
from agents.tools.revenue import get_revenue_summary

# Import the database initialization function.
from data.database import initialize_database


# Define a test for our known synthetic revenue decline.
def test_revenue_decline():
    # Create the development database if necessary.
    initialize_database()

    # Compare revenue between the two known quarters.
    result = get_revenue_summary("2026-Q1", "2026-Q2")

    # Verify that the starting revenue is correct.
    assert result["revenue_a"] == 200000.0

    # Verify that the ending revenue is correct.
    assert result["revenue_b"] == 164000.0

    # Verify that the calculated decline is exactly 18%.
    assert result["percentage_change"] == -18.0
