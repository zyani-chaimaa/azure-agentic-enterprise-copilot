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
    }), // Match FastAPI's CopilotQuestionRequest model.
  });

  // Report a readable error if the backend rejects the request.
  if (!response.ok) {
    throw new Error(`Copilot request failed: HTTP ${response.status}`);
  }

  // Decode and return the structured copilot response.
  return (await response.json()) as CopilotResponse;
}
