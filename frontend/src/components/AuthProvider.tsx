// This component runs in the browser because authentication uses browser APIs.
"use client";

// Import the type for nested React components.
import type { ReactNode } from "react";

// Import the React hook used to initialize MSAL.
import { useEffect, useState } from "react";

// Import the MSAL browser client.
import { PublicClientApplication } from "@azure/msal-browser";

// Import the provider that shares authentication state with React.
import { MsalProvider } from "@azure/msal-react";

// Import our Microsoft Entra ID configuration.
import { msalConfig } from "@/lib/authConfig";

// Create one MSAL instance for the entire frontend.
const msalInstance = new PublicClientApplication(msalConfig);

// Define the component that wraps our application.
export default function AuthProvider({ children }: { children: ReactNode }) {
  // Track whether MSAL has finished initializing.
  const [ready, setReady] = useState(false);

  // Initialize MSAL when this component mounts in the browser.
  useEffect(() => {
    // Initialize MSAL and process any authentication redirect response.
    async function initializeAuth() {
      await msalInstance.initialize();
      await msalInstance.handleRedirectPromise();
      setReady(true);
    }

    // Start initialization.
    void initializeAuth().catch((error) => {
      console.error("Authentication initialization failed:", error);
    });
  }, []);

  // Avoid rendering authenticated components before initialization finishes.
  if (!ready) {
    return <p>Initializing authentication...</p>;
  }

  // Share the initialized MSAL instance with all nested components.
  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}
