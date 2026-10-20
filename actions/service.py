# Import UUID generation for unique action identifiers.
from uuid import uuid4

# Import our existing authenticated Azure SQL connection.
from data.azure_sql import connect_to_azure_sql


# Create a new business action proposal without executing it.
def propose_order_review(
    order_id: str,
    reason: str,
    proposed_by: str,
) -> dict:

    # Validate the target order identifier.
    if not order_id or not order_id.strip():
        raise ValueError("Order ID is required.")

    # Validate the explanation for the proposed action.
    if not reason or not reason.strip():
        raise ValueError("A reason is required.")

    # Validate the identity associated with the proposal.
    if not proposed_by or not proposed_by.strip():
        raise ValueError("Proposer identity is required.")

    # Generate a unique identifier for this proposal.
    action_id = str(uuid4())

    # Connect to our Azure SQL database.
    connection = connect_to_azure_sql()

    # Use a transaction so the proposal and audit event succeed together.
    connection.autocommit = False

    try:
        # Create a database cursor for SQL operations.
        cursor = connection.cursor()

        # Insert the action request with pending status.
        cursor.execute(
            """
            INSERT INTO dbo.copilot_action_requests
                (action_id, action_type, target_id, reason, status, proposed_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            action_id,
            "flag_order_for_review",
            order_id,
            reason,
            "pending",
            proposed_by,
        )

        # Record the proposal in our audit history.
        cursor.execute(
            """
            INSERT INTO dbo.copilot_action_audit
                (action_id, event_type, actor, details)
            VALUES (?, ?, ?, ?)
            """,
            action_id,
            "proposed",
            proposed_by,
            reason,
        )

        # Commit both records atomically.
        connection.commit()

    # Roll back both records if anything fails.
    except Exception:
        connection.rollback()
        raise

    # Always close the database connection.
    finally:
        connection.close()

    # Return the new proposal without performing the business action.
    return {
        "action_id": action_id,
        "action_type": "flag_order_for_review",
        "target_id": order_id,
        "reason": reason,
        "status": "pending",
        "proposed_by": proposed_by,
        "executed": False,
    }


# Record a human approval or rejection without executing the action.
def review_action(
    action_id: str,
    decision: str,
    reviewer: str,
) -> dict:

    # Accept only the two supported human decisions.
    if decision not in ("approved", "rejected"):
        raise ValueError("Decision must be approved or rejected.")

    # Require an action identifier.
    if not action_id or not action_id.strip():
        raise ValueError("Action ID is required.")

    # Require a reviewer identity.
    if not reviewer or not reviewer.strip():
        raise ValueError("Reviewer identity is required.")

    # Open our authenticated Azure SQL connection.
    connection = connect_to_azure_sql()

    # Make the decision and audit event one transaction.
    connection.autocommit = False

    try:
        # Create a cursor for database operations.
        cursor = connection.cursor()

        # Change the status only if the action is still pending.
        cursor.execute(
            """
            UPDATE dbo.copilot_action_requests
            SET status = ?,
                reviewed_by = ?,
                reviewed_at = SYSUTCDATETIME()
            WHERE action_id = ?
              AND status = 'pending'
            """,
            decision,
            reviewer,
            action_id,
        )

        # Reject missing actions and repeated approval attempts.
        if cursor.rowcount != 1:
            raise ValueError(
                "Action not found or no longer pending."
            )

        # Record the decision in the audit history.
        cursor.execute(
            """
            INSERT INTO dbo.copilot_action_audit
                (action_id, event_type, actor, details)
            VALUES (?, ?, ?, ?)
            """,
            action_id,
            decision,
            reviewer,
            f"Human review decision: {decision}",
        )

        # Save the status change and audit event together.
        connection.commit()

    # Undo all database changes if any step fails.
    except Exception:
        connection.rollback()
        raise

    # Always close the database connection.
    finally:
        connection.close()

    # Return the decision without executing the business action.
    return {
        "action_id": action_id,
        "status": decision,
        "reviewed_by": reviewer,
        "executed": False,
    }

# Execute an approved order-review action exactly once.
def execute_order_review(action_id: str) -> dict:

    # Require a valid action identifier.
    if not action_id or not action_id.strip():
        raise ValueError("Action ID is required.")

    # Connect to Azure SQL using Microsoft Entra authentication.
    connection = connect_to_azure_sql()

    # Begin a transaction covering execution and auditing.
    connection.autocommit = False

    try:
        # Create a cursor for our database operations.
        cursor = connection.cursor()

        # Lock the action row while checking its approval status.
        cursor.execute(
            """
            SELECT action_type, target_id, reason, status
            FROM dbo.copilot_action_requests
                WITH (UPDLOCK, HOLDLOCK)
            WHERE action_id = ?
            """,
            action_id,
        )

        # Retrieve the action information.
        action = cursor.fetchone()

        # Reject unknown action identifiers.
        if action is None:
            raise ValueError("Action not found.")

        # Only explicitly approved actions can be executed.
        if action.status != "approved":
            raise ValueError("Action must be approved before execution.")

        # Permit only the supported business action.
        if action.action_type != "flag_order_for_review":
            raise ValueError("Unsupported action type.")

        # Create the internal order-review record.
        cursor.execute(
            """
            INSERT INTO dbo.copilot_order_reviews
                (action_id, order_id, reason)
            VALUES (?, ?, ?)
            """,
            action_id,
            action.target_id,
            action.reason,
        )

        # Mark the action as executed.
        cursor.execute(
            """
            UPDATE dbo.copilot_action_requests
            SET status = 'executed'
            WHERE action_id = ?
              AND status = 'approved'
            """,
            action_id,
        )

        # Verify that exactly one approved action was updated.
        if cursor.rowcount != 1:
            raise RuntimeError("Action execution state changed unexpectedly.")

        # Record the execution in the audit trail.
        cursor.execute(
            """
            INSERT INTO dbo.copilot_action_audit
                (action_id, event_type, actor, details)
            VALUES (?, ?, ?, ?)
            """,
            action_id,
            "executed",
            "copilot-action-service",
            "Order flagged for manual review.",
        )

        # Commit the business effect, status, and audit event together.
        connection.commit()

    # Undo every change if execution fails.
    except Exception:
        connection.rollback()
        raise

    # Always release the database connection.
    finally:
        connection.close()

    # Report the completed action.
    return {
        "action_id": action_id,
        "action_type": "flag_order_for_review",
        "status": "executed",
        "executed": True,
    }