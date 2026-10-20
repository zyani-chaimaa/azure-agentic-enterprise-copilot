// Import the TypeScript interface for our Microsoft authentication client.
import type { IPublicClientApplication } from "@azure/msal-browser";

// Import the API permission scope configured in Microsoft Entra ID.
import { apiTokenRequest } from "@/lib/authConfig";

// Describe the response returned by our protected FastAPI endpoint.
export type AuthenticatedUser = {
  authenticated: boolean; // Indicates whether FastAPI accepted the authentication.
  user_id: string; // The user's Microsoft Entra ID object identifier.
  roles: string[]; // The application roles assigned to the user.
};

// Create a reusable function for verifying a signed-in user's API access.
export async function getAuthenticatedUser(
  msalInstance: IPublicClientApplication, // The existing Microsoft authentication client.
): Promise<AuthenticatedUser> {
  // Find the active account, or use the first signed-in account.
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];

  // Stop if no Microsoft account is signed in.
  if (!account) {
    throw new Error("No Microsoft account is signed in.");
  }

  // Request an access token for our backend API using the signed-in account.
  const tokenResponse = await msalInstance.acquireTokenSilent({
    ...apiTokenRequest, // Request the Copilot.Access permission.
    account, // Specify which signed-in user needs the token.
  });

  // Send the access token to the protected FastAPI endpoint.
  const response = await fetch("http://localhost:8000/api/v1/auth/me", {
    method: "GET", // Retrieve the current user's authentication details.
    headers: {
      // Present the Microsoft-issued access token to FastAPI.
      Authorization: `Bearer ${tokenResponse.accessToken}`,
    },
  });

  // Report an error if FastAPI rejects the request.
  if (!response.ok) {
    throw new Error(`FastAPI rejected the request: HTTP ${response.status}`);
  }

  // Convert the successful JSON response into our TypeScript data structure.
  return (await response.json()) as AuthenticatedUser;
}

// Describe a function executed by the AI orchestrator.
export type CopilotToolCall = {
  name: string; // The backend function selected by the model.
  arguments: Record<string, unknown>; // The arguments supplied to that function.
  result: unknown; // The function's returned data.
};

// Describe the unified copilot API response.
export type CopilotResponse = {
  answer: string; // The model's final answer.
  tool_calls: CopilotToolCall[]; // The executed function calls.
  response_id: string; // The Azure model response identifier.
};

// Send a question to our unified, protected copilot endpoint.
export async function askCopilot(
  msalInstance: IPublicClientApplication, // The existing Microsoft authentication client.
  question: string, // The user's question.
  conversationId?: string, // The selected Azure SQL conversation.
): Promise<CopilotResponse> {
  // Identify the active signed-in Microsoft account.
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];

  // Require authentication before sending any business question.
  if (!account) {
    throw new Error("Please sign in before asking a question.");
  }

  // Obtain a delegated access token for the FastAPI backend.
  const tokenResponse = await msalInstance.acquireTokenSilent({
    ...apiTokenRequest, // Reuse the configured Copilot.Access scope.
    account, // Request the token for the current user.
  });

  // Read the API address from configuration, falling back to local development.
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  // Send the question and Microsoft access token to FastAPI.
  const response = await fetch(`${apiBaseUrl}/api/v1/copilot/ask`, {
    method: "POST", // Submit a question to the copilot.
    headers: {
      "Content-Type": "application/json", // Tell FastAPI we're sending JSON.
      Authorization: `Bearer ${tokenResponse.accessToken}`, // Authenticate the request.
    },
    body: JSON.stringify({
      question, // The user's question.
      ...(conversationId ? { conversation_id: conversationId } : {}), // Optional saved conversation.
    }), // Match FastAPI's CopilotQuestionRequest model.
  });

  // Report a readable error if the backend rejects the request.
  if (!response.ok) {
    throw new Error(`Copilot request failed: HTTP ${response.status}`);
  }

  // Decode and return the structured copilot response.
  return (await response.json()) as CopilotResponse;
}

// Describe a conversation created by our FastAPI backend.
export type Conversation = {
  conversation_id: string; // The unique conversation identifier.
  title: string; // The conversation's display title.
};

// Create a new conversation for the signed-in Microsoft user.
export async function createConversation(
  msalInstance: IPublicClientApplication, // Our existing Microsoft authentication client.
): Promise<Conversation> {
  // Find the active account or the first signed-in account.
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];

  // Require a signed-in user.
  if (!account) {
    throw new Error("Please sign in before creating a conversation.");
  }

  // Obtain a Microsoft access token for our protected backend.
  const tokenResponse = await msalInstance.acquireTokenSilent({
    ...apiTokenRequest, // Request the configured Copilot.Access permission.
    account, // Use the currently signed-in Microsoft account.
  });

  // Read the backend address from our frontend configuration.
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  // Ask FastAPI to create a conversation owned by this user.
  const response = await fetch(`${apiBaseUrl}/api/v1/conversations`, {
    method: "POST", // Create a new conversation.
    headers: {
      Authorization: `Bearer ${tokenResponse.accessToken}`, // Authenticate the request.
    },
  });

  // Report an error if the backend rejects the request.
  if (!response.ok) {
    throw new Error(`Conversation creation failed: HTTP ${response.status}`);
  }

  // Return the new conversation identifier and title.
  return (await response.json()) as Conversation;
}

// Describe a conversation returned by the history endpoint.
export type ConversationHistoryItem = {
  conversation_id: string; // Unique identifier for reopening the conversation.
  title: string; // Title displayed in the NEXORA sidebar.
  created_at: string; // Timestamp when the conversation was created.
  updated_at: string; // Timestamp of the conversation's latest activity.
};

// Retrieve conversations belonging to the signed-in Microsoft user.
export async function listConversations(
  msalInstance: IPublicClientApplication, // Existing Microsoft authentication client.
): Promise<ConversationHistoryItem[]> {
  // Find the active account or the first signed-in account.
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];

  // Require Microsoft authentication.
  if (!account) {
    throw new Error("Please sign in to view conversation history.");
  }

  // Obtain an access token for our protected FastAPI backend.
  const tokenResponse = await msalInstance.acquireTokenSilent({
    ...apiTokenRequest, // Request the Copilot.Access permission.
    account, // Use the currently signed-in Microsoft account.
  });

  // Resolve the configured backend API address.
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  // Request the authenticated user's conversation history.
  const response = await fetch(`${apiBaseUrl}/api/v1/conversations`, {
    method: "GET", // Retrieve existing conversations.
    headers: {
      Authorization: `Bearer ${tokenResponse.accessToken}`, // Authenticate with Microsoft Entra.
    },
  });

  // Handle unsuccessful API responses.
  if (!response.ok) {
    throw new Error(`Conversation history failed: HTTP ${response.status}`);
  }

  // Decode the response from FastAPI.
  const conversations = (await response.json()) as ConversationHistoryItem[];

  // Return the conversation list to the frontend.
  return conversations;
}

// Describe a message stored in Azure SQL.
export type SavedConversationMessage = {
  message_id: string; // Unique identifier of the saved message.
  role: "user" | "assistant"; // Identifies who sent the message.
  content: string; // The original question or AI answer.
  tool_results: CopilotToolCall[] | null; // Saved AI tool calls, when available.
  created_at: string; // Timestamp when the message was saved.
};

// Retrieve saved messages from a conversation owned by the signed-in user.
export async function listConversationMessages(
  msalInstance: IPublicClientApplication, // Existing Microsoft authentication client.
  conversationId: string, // Identifier of the conversation to reopen.
): Promise<SavedConversationMessage[]> {
  // Identify the currently signed-in Microsoft account.
  const account =
    msalInstance.getActiveAccount() ?? msalInstance.getAllAccounts()[0];

  // Require authentication before accessing conversation messages.
  if (!account) {
    throw new Error("Please sign in to view conversation messages.");
  }

  // Request an access token for our protected FastAPI backend.
  const tokenResponse = await msalInstance.acquireTokenSilent({
    ...apiTokenRequest, // Use the configured Copilot.Access permission.
    account, // Request the token for the signed-in user.
  });

  // Resolve the backend API address.
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

  // Encode the conversation identifier for safe use in the URL.
  const safeConversationId = encodeURIComponent(conversationId);

  // Request the conversation's saved messages.
  const response = await fetch(
    `${apiBaseUrl}/api/v1/conversations/${safeConversationId}/messages`,
    {
      method: "GET", // Retrieve saved conversation messages.
      headers: {
        Authorization: `Bearer ${tokenResponse.accessToken}`, // Authenticate the request.
      },
    },
  );

  // Report any unsuccessful response from FastAPI.
  if (!response.ok) {
    throw new Error(`Loading conversation failed: HTTP ${response.status}`);
  }

  // Decode the saved messages returned by Azure SQL.
  return (await response.json()) as SavedConversationMessage[];
}
