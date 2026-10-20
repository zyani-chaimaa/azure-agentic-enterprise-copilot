# Import UUID utilities to generate and validate conversation identifiers.
from uuid import UUID, uuid4

# Import our existing secure Azure SQL connection.
from data.azure_sql import connect_to_azure_sql


# Convert verified Microsoft Entra identity claims into UUID objects.
def get_owner_ids(claims: dict) -> tuple[UUID, UUID]:
    # Read the tenant ID from the validated access token.
    tenant_id = UUID(claims["tid"])

    # Read the user object ID from the validated access token.
    user_id = UUID(claims["oid"])

    # Return both identifiers for ownership-filtered SQL queries.
    return tenant_id, user_id


# Create a conversation belonging to the authenticated user.
def create_conversation(claims: dict, title: str = "New conversation") -> dict:
    # Extract the verified conversation owner.
    tenant_id, user_id = get_owner_ids(claims)

    # Generate the conversation identifier on the backend.
    conversation_id = uuid4()

    # Connect to Azure SQL.
    with connect_to_azure_sql() as connection:
        # Create a cursor for parameterized SQL.
        cursor = connection.cursor()

        # Insert the conversation without accepting an owner from the browser.
        cursor.execute(
            """
            INSERT INTO chat.conversations
                (conversation_id, tenant_id, user_id, title)
            VALUES (?, ?, ?, ?)
            """,
            str(conversation_id),
            str(tenant_id),
            str(user_id),
            title,
        )

    # Return the new conversation's identifier and title.
    return {"conversation_id": str(conversation_id), "title": title}


# List conversations belonging only to the authenticated user.
def list_conversations(claims: dict) -> list[dict]:
    # Extract the verified conversation owner.
    tenant_id, user_id = get_owner_ids(claims)

    # Open an authenticated Azure SQL connection.
    with connect_to_azure_sql() as connection:
        # Create a cursor for the read-only query.
        cursor = connection.cursor()

        # Filter by both tenant and user to enforce ownership.
        cursor.execute(
            """
            SELECT conversation_id, title, created_at, updated_at
            FROM chat.conversations
            WHERE tenant_id = ? AND user_id = ?
            ORDER BY updated_at DESC, created_at DESC
            """,
            str(tenant_id),
            str(user_id),
        )

        # Convert the database records into JSON-compatible dictionaries.
        return [
            {
                "conversation_id": str(row.conversation_id).lower(),
                "title": row.title,
                "created_at": row.created_at.isoformat(),
                "updated_at": row.updated_at.isoformat(),
            }
            for row in cursor.fetchall()
        ]


# Import JSON utilities to restore saved agent tool results.
import json


# Retrieve messages only from a conversation owned by the signed-in user.
def list_messages(claims: dict, conversation_id: str) -> list[dict]:
    # Extract the tenant and user IDs from the validated access token.
    tenant_id, user_id = get_owner_ids(claims)

    # Validate and normalize the requested conversation identifier.
    valid_conversation_id = str(UUID(conversation_id))

    # Connect to Azure SQL using the application's Azure identity.
    with connect_to_azure_sql() as connection:
        # Create a cursor for the parameterized database query.
        cursor = connection.cursor()

        # Retrieve messages only when the conversation belongs to this user.
        cursor.execute(
            """
            SELECT
                m.message_id,
                m.role,
                m.content,
                m.tool_results_json,
                m.created_at
            FROM chat.messages AS m
            INNER JOIN chat.conversations AS c
                ON c.conversation_id = m.conversation_id
            WHERE c.conversation_id = ?
              AND c.tenant_id = ?
              AND c.user_id = ?
            ORDER BY m.created_at ASC, m.message_id ASC
            """,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Convert each database message into a frontend-friendly dictionary.
        return [
            {
                # Normalize the message identifier to lowercase.
                "message_id": str(row.message_id).lower(),

                # Identify whether the message came from the user or assistant.
                "role": row.role,

                # Restore the original message text.
                "content": row.content,

                # Restore structured tool results when they were saved.
                "tool_results": (
                    json.loads(row.tool_results_json)
                    if row.tool_results_json is not None
                    else None
                ),

                # Return the original message creation timestamp.
                "created_at": row.created_at.isoformat(),
            }
            for row in cursor.fetchall()
        ]


# Import an exception for invalid conversation ownership.
from fastapi import HTTPException


# Save a message to a conversation owned by the authenticated user.
def save_message(
    claims: dict,
    conversation_id: str,
    role: str,
    content: str,
    tool_results: list | None = None,
) -> dict:
    # Extract the verified Microsoft Entra tenant and user IDs.
    tenant_id, user_id = get_owner_ids(claims)

    # Validate and normalize the conversation identifier.
    valid_conversation_id = str(UUID(conversation_id))

    # Allow only the two supported conversation roles.
    if role not in ("user", "assistant"):
        raise ValueError("Invalid message role.")

    # Convert structured agent tool results into JSON for Azure SQL.
    tool_results_json = (
        json.dumps(tool_results, ensure_ascii=False, default=str)
        if tool_results is not None
        else None
    )

    # Generate a unique identifier for the new message.
    message_id = str(uuid4())

    # Open an authenticated Azure SQL connection.
    with connect_to_azure_sql() as connection:
        # Disable autocommit so both writes share one transaction.
        connection.autocommit = False

        # Create a cursor for the database operation.
        cursor = connection.cursor()

        # Insert only when the conversation belongs to this user.
        cursor.execute(
            """
            INSERT INTO chat.messages
                (message_id, conversation_id, role, content, tool_results_json)
            SELECT ?, c.conversation_id, ?, ?, ?
            FROM chat.conversations AS c
            WHERE c.conversation_id = ?
              AND c.tenant_id = ?
              AND c.user_id = ?
            """,
            message_id,
            role,
            content,
            tool_results_json,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Determine whether the ownership-filtered insert succeeded.
        inserted = cursor.rowcount

        # Reject missing conversations and conversations owned by other users.
        if inserted != 1:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        # Update the conversation's last-activity timestamp.
        cursor.execute(
            """
            UPDATE chat.conversations
            SET updated_at = SYSUTCDATETIME()
            WHERE conversation_id = ?
              AND tenant_id = ?
              AND user_id = ?
            """,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Commit the message and timestamp update together.
        connection.commit()

    # Return the identifier of the successfully saved message.
    return {"message_id": message_id}


# Rename a conversation belonging to the authenticated Microsoft user.
def rename_conversation(
    claims: dict,
    conversation_id: str,
    title: str,
) -> dict:
    # Extract the verified tenant and user identifiers.
    tenant_id, user_id = get_owner_ids(claims)

    # Validate and normalize the conversation identifier.
    valid_conversation_id = str(UUID(conversation_id))

    # Remove unnecessary whitespace from the requested title.
    clean_title = title.strip()

    # Reject empty titles or titles exceeding the database limit.
    if not clean_title or len(clean_title) > 200:
        raise ValueError("Conversation title must contain 1 to 200 characters.")

    # Open an authenticated Azure SQL connection.
    with connect_to_azure_sql() as connection:
        # Create a cursor for the parameterized update.
        cursor = connection.cursor()

        # Update only conversations belonging to this tenant and user.
        cursor.execute(
            """
            UPDATE chat.conversations
            SET title = ?,
                updated_at = SYSUTCDATETIME()
            WHERE conversation_id = ?
              AND tenant_id = ?
              AND user_id = ?
            """,
            clean_title,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Determine whether an owned conversation was updated.
        updated = cursor.rowcount

        # Return 404 for missing or unauthorized conversations.
        if updated != 1:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

    # Return the updated conversation information.
    return {
        "conversation_id": valid_conversation_id,
        "title": clean_title,
    }


# Check whether a conversation belongs to the authenticated Microsoft user.
def require_owned_conversation(claims: dict, conversation_id: str) -> None:
    # Extract the verified Microsoft Entra tenant and user identifiers.
    tenant_id, user_id = get_owner_ids(claims)

    # Validate and normalize the conversation identifier.
    valid_conversation_id = str(UUID(conversation_id))

    # Open an authenticated connection to Azure SQL.
    with connect_to_azure_sql() as connection:
        # Create a cursor for the ownership query.
        cursor = connection.cursor()

        # Check for a conversation matching all three identifiers.
        cursor.execute(
            """
            SELECT TOP (1) 1
            FROM chat.conversations
            WHERE conversation_id = ?
              AND tenant_id = ?
              AND user_id = ?
            """,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Read whether an owned conversation exists.
        owned_conversation = cursor.fetchone()

    # Return the same response for missing and unauthorized conversations.
    if owned_conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )


# Save a complete user-and-assistant exchange in one transaction.
def save_exchange(
    claims: dict,
    conversation_id: str,
    question: str,
    answer: str,
    tool_results: list | None = None,
) -> None:
    # Read the tenant and user IDs from the verified Microsoft token.
    tenant_id, user_id = get_owner_ids(claims)

    # Validate and normalize the conversation identifier.
    valid_conversation_id = str(UUID(conversation_id))

    # Serialize the assistant's structured tool results.
    tools_json = (
        json.dumps(tool_results, ensure_ascii=False, default=str)
        if tool_results is not None
        else None
    )

    # Generate unique identifiers for both messages.
    user_message_id = str(uuid4())
    assistant_message_id = str(uuid4())

    # Open our authenticated Azure SQL connection.
    with connect_to_azure_sql() as connection:
        # Use a single transaction for the entire exchange.
        connection.autocommit = False

        # Create a cursor for parameterized SQL statements.
        cursor = connection.cursor()

        # Verify ownership within the same database transaction.
        cursor.execute(
            """
            SELECT conversation_id
            FROM chat.conversations WITH (UPDLOCK, HOLDLOCK)
            WHERE conversation_id = ?
              AND tenant_id = ?
              AND user_id = ?
            """,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Reject missing or unauthorized conversations.
        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        # Save the user's question first.
        cursor.execute(
            """
            INSERT INTO chat.messages
                (message_id, conversation_id, role, content)
            VALUES (?, ?, ?, ?)
            """,
            user_message_id,
            valid_conversation_id,
            "user",
            question,
        )

        # Save the assistant's answer and tool results.
        cursor.execute(
            """
            INSERT INTO chat.messages
                (message_id, conversation_id, role, content, tool_results_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            assistant_message_id,
            valid_conversation_id,
            "assistant",
            answer,
            tools_json,
        )

        # Update the conversation's last-activity timestamp.
        cursor.execute(
            """
            UPDATE chat.conversations
            SET updated_at = SYSUTCDATETIME()
            WHERE conversation_id = ?
              AND tenant_id = ?
              AND user_id = ?
            """,
            valid_conversation_id,
            str(tenant_id),
            str(user_id),
        )

        # Commit all three changes together.
        connection.commit()
