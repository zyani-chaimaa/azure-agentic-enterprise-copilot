"use client";

// Import React state to control the mobile navigation.
import { useState } from "react";
import ChatPanel from "@/components/ChatPanel";

// Import the Microsoft authentication hook.
import { useMsal } from "@azure/msal-react";

// Define our enterprise workspace component.
export default function Workspace() {
  // Access the signed-in Microsoft account and authentication client.
  const { instance, accounts } = useMsal();

  // Track whether the mobile sidebar is visible.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Get the current user's display name.
  const displayName = accounts[0]?.name || accounts[0]?.username || "User";

  // Generate initials for the account avatar.
  const initials = displayName
    .split(/[ .@_-]+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  // Start a fresh chat without saving anything to Azure SQL.
  function startNewChat() {
    // Ask ChatPanel to clear its current messages.
    window.dispatchEvent(new Event("nexora:new-conversation"));

    // Close the navigation on smaller screens.
    setSidebarOpen(false);
  }

  // Sign the user out of Microsoft Entra ID.
  async function signOut() {
    await instance.logoutRedirect();
  }

  // Display the enterprise workspace.
  return (
    <div className="flex h-dvh overflow-hidden bg-[#F5F7FB] text-[#17243A]">
      {/* Mobile overlay closes the sidebar when selected. */}
      {sidebarOpen && (
        <button
          aria-label="Close navigation"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-30 bg-slate-950/30 lg:hidden"
        />
      )}

      {/* Main application navigation. */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-68 flex-col border-r border-[#E2E8F0] bg-white transition-transform lg:static lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand identity. */}
        <div className="flex h-20 items-center gap-3 border-b border-[#E2E8F0] px-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#722F43] text-lg font-bold text-white">
            N
          </div>
          <div>
            <p className="text-lg font-bold tracking-[0.12em] text-[#251F23]">
              NEXORA
            </p>
          </div>
        </div>

        {/* Keep navigation minimal and focused on conversations. */}
        <nav aria-label="Workspace navigation" className="flex-1 px-4 py-6">
          <button
            type="button"
            onClick={startNewChat}
            className="flex w-full items-center gap-3 rounded-xl bg-[#722F43] px-4 py-3 text-left text-sm font-semibold text-white transition hover:bg-[#512132]"
          >
            <span className="text-xl leading-none">+</span>
            New chat
          </button>

        </nav>

        {/* Authenticated account area. */}
        <div className="border-t border-[#E2E8F0] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#EDE9FE] text-xs font-bold text-[#6D28D9]">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{displayName}</p>
              <p className="text-xs text-[#64748B]">Microsoft account</p>
            </div>
          </div>
          <button
            onClick={signOut}
            className="mt-4 w-full rounded-lg border border-[#E2E8F0] px-4 py-2 text-left text-xs font-medium text-[#475569] transition hover:bg-[#F8FAFC] focus-visible:outline"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main application content. */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        {/* Main conversational experience. */}
        <main className="flex min-h-0 flex-1 flex-col items-center px-5 py-6 md:px-9">
          {/* Render the authenticated, interactive AI conversation. */}
          <ChatPanel />
        </main>
      </div>
    </div>
  );
}
