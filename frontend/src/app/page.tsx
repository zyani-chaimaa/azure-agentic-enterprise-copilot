"use client";

// Import the Microsoft authentication hook.
import { useMsal } from "@azure/msal-react";

// Import the permission required to access our backend API.
import { apiTokenRequest } from "@/lib/authConfig";

// Import our new enterprise workspace.
import Workspace from "@/components/Workspace";

// Define the application's homepage.
export default function Home() {
  // Get the authentication client and signed-in accounts.
  const { instance, accounts } = useMsal();

  // Determine whether the user has signed in.
  const isSignedIn = accounts.length > 0;

  // Start the Microsoft Entra ID sign-in process.
  async function signIn() {
    try {
      // Request access to our protected backend API.
      await instance.loginRedirect(apiTokenRequest);
    } catch (error) {
      // Log authentication failures for debugging.
      console.error("Microsoft sign-in failed:", error);
    }
  }

  // Show the enterprise workspace after sign-in.
  if (isSignedIn) {
    return <Workspace />;
  }

  // Display a professional sign-in screen for unauthenticated users.
  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F5F7FB] px-6">
      <section className="w-full max-w-md rounded-2xl border border-[#E2E8F0] bg-white p-10 shadow-sm">
        {/* Display our product identity. */}
        <div className="mb-8 flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#2563EB] text-xl font-bold text-white">
            E
          </div>
          <div>
            <p className="font-semibold text-[#17243A]">Enterprise Copilot</p>
            <p className="text-xs text-[#64748B]">Decision intelligence</p>
          </div>
        </div>

        {/* Introduce the application. */}
        <h1 className="text-2xl font-semibold tracking-tight text-[#17243A]">
          Welcome back
        </h1>

        <p className="mt-3 text-sm leading-6 text-[#64748B]">
          Sign in to access your enterprise analytics and document
          intelligence workspace.
        </p>

        {/* Start Microsoft authentication. */}
        <button
          onClick={signIn}
          className="mt-8 w-full rounded-lg bg-[#2563EB] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#1D4ED8]"
        >
          Continue with Microsoft
        </button>

        {/* Explain how access is managed. */}
        <p className="mt-6 text-center text-xs text-[#94A3B8]">
          Secure access managed through Microsoft Entra ID
        </p>
      </section>
    </main>
  );
}
