"use client";

// Import React state to control the mobile navigation.
import { useEffect, useState } from "react";
import ChatPanel from "@/components/ChatPanel";

// Import the authenticated conversation history API and its TypeScript type.
import {
  createConversation,
  listConversations,
  type ConversationHistoryItem,
} from "@/lib/api";


// Import the Microsoft authentication hook.
import { useMsal } from "@azure/msal-react";

// Define our enterprise workspace component.
export default function Workspace() {
  // Access the signed-in Microsoft account and authentication client.
  const { instance, accounts } = useMsal();

  // Track whether the mobile sidebar is visible.
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Track the conversation currently displayed in the chat panel.
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  // Store conversations belonging to the authenticated Microsoft user.
  const [conversations, setConversations] = useState<ConversationHistoryItem[]>([]);

  // Track whether conversation history is being loaded.
  const [historyLoading, setHistoryLoading] = useState(true);

  // Store a readable error if conversation history cannot be loaded.
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Load the signed-in user's conversations when the workspace opens.
  useEffect(() => {
    // Prevent state updates after the component unmounts.
    let cancelled = false;

    // Fetch the authenticated user's conversation history.
    async function loadHistory() {
      try {
        // Retrieve conversations from the protected FastAPI endpoint.
        const savedConversations = await listConversations(instance);

        // Update state only while the component is mounted.
        if (!cancelled) {
          setConversations(savedConversations);
          setHistoryError(null);
        }
      } catch (error) {
        // Display a safe, readable error without exposing tokens.
        if (!cancelled) {
          setHistoryError(
            error instanceof Error ? error.message : "Unable to load conversations.",
          );
        }
      } finally {
        // Finish loading if this effect is still active.
        if (!cancelled) {
          setHistoryLoading(false);
        }
      }
    }

    // Start loading conversation history.
    void loadHistory();

    // Ignore responses that arrive after unmounting.
    return () => {
      cancelled = true;
    };
  }, [instance]);

  // Get the current user's display name.
  const displayName = accounts[0]?.name || accounts[0]?.username || "User";

  // Generate initials for the account avatar.
  const initials = displayName
    .split(/[ .@_-]+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("");

  // Create a persistent conversation for the signed-in user.
  async function startNewConversation() {
    // Prevent repeated clicks while a conversation is being created.
    if (historyLoading) return;

    // Show the loading state during creation.
    setHistoryLoading(true);

    try {
      // Create a conversation through our authenticated FastAPI endpoint.
      const conversation = await createConversation(instance);

      // Make the new conversation active in the chat panel.
      setActiveConversationId(conversation.conversation_id);

      // Add the newly created conversation to the top of the sidebar.
      const now = new Date().toISOString();

      // Update the displayed conversation list.
      setConversations((previous) => [
        {
          ...conversation,
          created_at: now,
          updated_at: now,
        },
        ...previous,
      ]);

      // Clear any previous history error.
      setHistoryError(null);

      // Reset the chat panel to a new conversation.
      window.dispatchEvent(new Event("nexora:new-conversation"));

      // Close the mobile sidebar after creating a conversation.
      setSidebarOpen(false);
    } catch (error) {
      // Display a readable error if conversation creation fails.
      setHistoryError(
        error instanceof Error ? error.message : "Unable to create conversation.",
      );
    } finally {
      // Restore the normal sidebar state.
      setHistoryLoading(false);
    }
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
            onClick={() => void startNewConversation()}
            className="flex w-full items-center gap-3 rounded-xl bg-[#722F43] px-4 py-3 text-left text-sm font-semibold text-white transition hover:bg-[#512132]"
          >
            <span className="text-xl leading-none">+</span>
            New conversation
          </button>

          {/* Display the authenticated user's saved conversations. */}
          <div className="mt-8">
            {/* Label the conversation history section. */}
            <p className="mb-3 px-3 text-xs font-semibold uppercase tracking-wider text-[#94A3B8]">
              Recent conversations
            </p>

            {/* Show a loading indicator while retrieving history. */}
            {historyLoading && (
              <p className="px-3 text-sm text-[#64748B]">
                Loading conversations...
              </p>
            )}

            {/* Display a readable error if history cannot be loaded. */}
            {historyError && (
              <p role="alert" className="px-3 text-sm text-red-600">
                {historyError}
              </p>
            )}

            {/* Explain when the user has no saved conversations. */}
            {!historyLoading && !historyError && conversations.length === 0 && (
              <p className="px-3 text-sm text-[#94A3B8]">
                No conversations yet
              </p>
            )}

            {/* Render the user's saved conversation titles. */}
            {!historyLoading && !historyError && (
              <div className="space-y-1">
                {conversations.map((conversation) => (
                  <button
                    key={conversation.conversation_id}
                    type="button"
                    onClick={() => {
                      // Select the conversation in the workspace.
                      setActiveConversationId(conversation.conversation_id);

                      // Close the navigation on mobile.
                      setSidebarOpen(false);
                    }}
                    className={`block w-full truncate rounded-lg px-3 py-2 text-left text-sm transition hover:bg-[#F5E9ED] ${
                      activeConversationId === conversation.conversation_id
                        ? "bg-[#F5E9ED] font-semibold text-[#722F43]"
                        : "text-[#475569]"
                    }`}
                    title={conversation.title}
                    aria-current={
                      activeConversationId === conversation.conversation_id
                        ? "page"
                        : undefined
                    }
                  >
                    {conversation.title}
                  </button>
                ))}
              </div>
            )}
          </div>
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
          <ChatPanel conversationId={activeConversationId} />
        </main>
      </div>
    </div>
  );
}
