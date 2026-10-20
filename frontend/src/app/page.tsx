// Run this page in the browser so it can use authentication hooks.
"use client";

// Import MSAL's React authentication hook.
import { useMsal } from "@azure/msal-react";

// Import the configuration for requesting our API permission.
import { apiTokenRequest } from "@/lib/authConfig";

// Define our application's homepage.
export default function Home() {
  // Access the MSAL instance and currently signed-in accounts.
  const { instance, accounts } = useMsal();

  // Determine whether a user is signed in.
  const isSignedIn = accounts.length > 0;

  // Start Microsoft Entra ID authentication.
  async function signIn() {
    try {
      // Redirect to Microsoft and request our API permission.
      await instance.loginRedirect(apiTokenRequest);
    } catch (error) {
      // Log authentication errors without exposing tokens.
      console.error("Sign-in failed:", error);
    }
  }

  // Sign the current user out of Microsoft Entra ID.
  async function signOut() {
    try {
      // Redirect to Microsoft to complete sign-out.
      await instance.logoutRedirect();
    } catch (error) {
      // Log sign-out errors.
      console.error("Sign-out failed:", error);
    }
  }

  // Render the sign-in interface.
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-950 p-6 text-white">
      {/* Display the main application panel. */}
      <section className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-10 shadow-xl">
        {/* Display our application name. */}
        <h1 className="mb-3 text-3xl font-bold">
          Enterprise Decision & Action Copilot
        </h1>

        {/* Explain what our application does. */}
        <p className="mb-8 text-slate-300">
          Your AI-powered assistant for enterprise analytics,
          document intelligence, and governed business actions.
        </p>

        {/* Show different content depending on authentication state. */}
        {isSignedIn ? (
          <>
            {/* Display the signed-in user's name. */}
            <p className="mb-5 text-green-400">
              Signed in as {accounts[0].username}
            </p>

            {/* Allow the user to sign out. */}
            <button
              onClick={signOut}
              className="rounded-lg bg-slate-700 px-5 py-3 font-semibold hover:bg-slate-600"
            >
              Sign out
            </button>
          </>
        ) : (
          /* Allow unauthenticated users to sign in. */
          <button
            onClick={signIn}
            className="rounded-lg bg-blue-600 px-6 py-3 font-semibold hover:bg-blue-500"
          >
            Sign in with Microsoft
          </button>
        )}
      </section>
    </main>
  );
}