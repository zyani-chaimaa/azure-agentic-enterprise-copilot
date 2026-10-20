// Import TypeScript's configuration type from MSAL.
import type { Configuration } from "@azure/msal-browser";

// Identify the Microsoft Entra tenant that manages our users.
const tenantId = "a50c7ddf-24ae-403c-b55b-5f14bd5ad88a";

// Identify our frontend application registration.
const frontendClientId = "d631c066-7845-416f-a088-0f6d0f2fbe49";

// Configure how MSAL authenticates users.
export const msalConfig: Configuration = {
  auth: {
    // The frontend's public application ID, not a secret.
    clientId: frontendClientId,

    // Restrict authentication to our Microsoft Entra tenant.
    authority: `https://login.microsoftonline.com/${tenantId}`,

    // Return users to our local frontend after authentication.
    redirectUri: "http://localhost:3000",
  },

  cache: {
    // Keep authentication information in browser session storage.
    cacheLocation: "sessionStorage",
  },
};

// Define the permission required to call our FastAPI backend.
export const apiTokenRequest = {
  scopes: [
    "api://d55c18fc-68a8-4bbb-a700-248cbc9e732c/Copilot.Access",
  ],
};
