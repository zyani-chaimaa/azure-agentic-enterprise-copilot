"use client";

// Import React hooks for managing conversation state.
import { useEffect, useRef, useState } from "react";

// Access the existing Microsoft authentication client.
import { useMsal } from "@azure/msal-react";

// Render model-generated Markdown as structured React elements.
import ReactMarkdown from "react-markdown";

// Support Markdown tables, lists, and other GitHub-flavored syntax.
import remarkGfm from "remark-gfm";

// Import our authenticated copilot API function and its response type.
import {
  askCopilot,
  listConversationMessages,
  type CopilotResponse,
} from "@/lib/api";

// Define the structure of a displayed conversation message.
type Message = {
  id: number; // Unique local identifier.
  role: "user" | "assistant"; // Who created the message.
  content: string; // The text displayed in the conversation.
  result?: CopilotResponse; // Optional structured AI response.
};

// Display and manage the main conversation experience.
export default function ChatPanel({
  conversationId,
  onRequestLoadingChange,
}: {
  conversationId: string | null;
  onRequestLoadingChange?: (loading: boolean) => void;
}) {
  // Access the signed-in user's Microsoft authentication client.
  const { instance } = useMsal();

  // Store messages for the current browser session.
  const [messages, setMessages] = useState<Message[]>([]);

  // Store the text currently entered by the user.
  const [question, setQuestion] = useState("");

  // Track whether an AI request is in progress.
  const [loading, setLoading] = useState(false);

  // Notify the parent workspace when an AI request starts or finishes.
  useEffect(() => {
    onRequestLoadingChange?.(loading);
  }, [loading, onRequestLoadingChange]);

  // Track whether saved conversation messages are being restored.
  const [restoringHistory, setRestoringHistory] = useState(false);

  // Store any error that should be shown to the user.
  const [error, setError] = useState<string | null>(null);

  // Generate local message identifiers.
  const nextId = useRef(1);

  // Restore saved messages whenever the selected conversation changes.
  useEffect(() => {
    // Ignore outdated responses after switching conversations.
    let cancelled = false;

    // Block message submission while saved messages are loading.
    setRestoringHistory(Boolean(conversationId));

    // Clear messages from the previously selected conversation.
    setMessages([]);

    // Clear errors and unsent text from the previous conversation.
    setError(null);
    setQuestion("");

    // Do nothing when no persistent conversation is selected.
    if (!conversationId) {
      return () => {
        cancelled = true;
      };
    }

    // Load the selected conversation's messages from Azure SQL.
    async function restoreConversation() {
      try {
        // Retrieve messages through the authenticated FastAPI endpoint.
        const savedMessages = await listConversationMessages(
          instance,
          conversationId!,
        );

        // Ignore results from an outdated conversation selection.
        if (cancelled) return;

        // Convert saved database messages into ChatPanel's existing format.
        const restoredMessages: Message[] = savedMessages.map((message, index) => ({
          // Generate a unique local identifier for React rendering.
          id: index + 1,

          // Preserve the original message role.
          role: message.role,

          // Preserve the original question or AI answer.
          content: message.content,

          // Reconstruct tool data for assistant messages.
          result:
            message.role === "assistant"
              ? {
                  answer: message.content,
                  tool_calls: message.tool_results ?? [],
                  response_id: "",
                }
              : undefined,
        }));

        // Restore the conversation in the chat interface.
        setMessages(restoredMessages);

        // Allow new questions after restoration succeeds.
        setRestoringHistory(false);

        // Continue generating unique local message identifiers.
        nextId.current = restoredMessages.length + 1;
      } catch (cause) {
        // Show a readable error without exposing authentication tokens.
        if (!cancelled) {
          setRestoringHistory(false);
          setError(
            cause instanceof Error
              ? `Unable to load conversation. ${cause.message}`
              : "Unable to load conversation.",
          );
        }
      }
    }

    // Start loading the selected conversation.
    void restoreConversation();

    // Cancel outdated results when the conversation changes.
    return () => {
      cancelled = true;
    };
  }, [conversationId, instance]);

  // Reference the end of the conversation for automatic scrolling.
  const bottomRef = useRef<HTMLDivElement>(null);

  // Scroll to the latest message when the conversation changes.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, loading]);

  // Send a question to the real Azure-backed copilot.
  async function sendQuestion(text: string) {
    // Remove unnecessary whitespace.
    const trimmed = text.trim();

    // Reject empty questions and prevent concurrent requests.
    if (!trimmed || loading || restoringHistory) return;

    // Match the backend's maximum question length.
    if (trimmed.length > 2000) {
      setError("Questions must contain 2,000 characters or fewer.");
      return;
    }

    // Clear any previous error and reset the composer.
    setError(null);
    setQuestion("");

    // Add the user's question to the conversation.
    setMessages((previous) => [
      ...previous,
      {
        id: nextId.current++,
        role: "user",
        content: trimmed,
      },
    ]);

    // Show the loading state while the backend processes the question.
    setLoading(true);

    try {
      // Send the authenticated request to our unified FastAPI endpoint.
      const result = await askCopilot(instance, trimmed, conversationId ?? undefined);

      // Display the model's answer and the executed tool information.
      setMessages((previous) => [
        ...previous,
        {
          id: nextId.current++,
          role: "assistant",
          content: result.answer || "The copilot returned no text.",
          result,
        },
      ]);
    } catch (cause) {
      // Convert unexpected errors into a readable message.
      const description =
        cause instanceof Error ? cause.message : "Unknown request error.";

      // Explain the failure without deleting the user's question.
      setError(`Unable to complete the request. ${description}`);
    } finally {
      // Restore the composer regardless of the request outcome.
      setLoading(false);
    }
  }

  // Start a fresh conversation without changing the signed-in account.
  function newConversation() {
    // Do not reset the interface while a request is still running.
    if (loading) return;

    // Clear the current browser-only conversation.
    setMessages([]);

    // Clear the input and any previous error.
    setQuestion("");
    setError(null);
  }

  // Allow the sidebar to start a new conversation.
  useEffect(() => {
    function handleNewConversation() {
      if (loading) return;
      setMessages([]);
      setQuestion("");
      setError(null);
    }

    window.addEventListener("nexora:new-conversation", handleNewConversation);

    return () => {
      window.removeEventListener("nexora:new-conversation", handleNewConversation);
    };
  }, [loading]);

  // Extract unique document sources from the actual retrieval results.
  function getDocumentSources(result: CopilotResponse) {
    // Store validated sources using a filename-and-page identifier.
    const sources = new Map<string, { filename: string; page: number | null; content: string | null }>();

    // Inspect only the document search tool's recorded outputs.
    for (const call of result.tool_calls) {
      if (call.name !== "search_enterprise_documents") continue;

      // Ensure the tool result is an object containing passages.
      const output = call.result;
      if (!output || typeof output !== "object" || !("passages" in output)) {
        continue;
      }

      // Retrieve the passage list without assuming its runtime type.
      const passages = output.passages;
      if (!Array.isArray(passages)) continue;

      // Validate the metadata returned by Azure AI Search.
      for (const passage of passages) {
        if (!passage || typeof passage !== "object") continue;

        const filename = passage.filename;
        const rawPage = passage.page_number;

        // Never display a filename that was not returned by retrieval.
        if (typeof filename !== "string" || !filename.trim()) continue;

        // Preserve valid page numbers; otherwise show only the filename.
        const page =
          typeof rawPage === "number" &&
          Number.isInteger(rawPage) &&
          rawPage >= 1
            ? rawPage
            : null;

        // Avoid repeating the same document page.
        const key = `${filename}:${page ?? "unknown"}`;
        const content =
          typeof passage.content === "string" && passage.content.trim()
            ? passage.content.trim()
            : null;

        if (!sources.has(key) || (!sources.get(key)?.content && content)) {
          sources.set(key, { filename, page, content });
        }
      }
    }

    // Return the unique, verified references.
    return [...sources.values()];
  }

  // Determine which high-level AI capabilities executed.
  function getCapabilities(result: CopilotResponse) {
    // Extract the names of functions called by the orchestrator.
    const names = result.tool_calls.map((call) => call.name);

    // Identify document retrieval.
    const documents = names.includes("search_enterprise_documents");

    // Identify the SQL analytics functions.
    const analytics = names.some((name) =>
      [
        "get_revenue_summary",
        "get_olist_revenue_summary",
        "get_top_product_categories",
      ].includes(name),
    );

    // Return only capabilities that actually executed.
    return { analytics, documents };
  }

  // Render the conversation interface.
  return (
    <section className="flex min-h-0 w-full max-w-3xl flex-1 flex-col">
      {/* Show suggestions when there are no messages. */}
      {messages.length === 0 ? (
        <div className="flex min-h-0 flex-1 flex-col justify-center overflow-y-auto">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#722F43]">
            Your intelligence workspace
          </p>

          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">
            What would you like to explore?
          </h1>

          <p className="mt-4 max-w-xl text-sm leading-7 text-[#64748B]">
            Explore business performance, investigate trends, or find
            answers in your enterprise knowledge base.
          </p>


        </div>
      ) : (
        /* Show the actual conversation after the first question. */
        <div
          aria-label="Conversation"
          aria-live="polite"
          className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto overscroll-contain pb-4 pr-2"
        >
          {messages.map((message) => {
            // Inspect the executed tools when this is an AI response.
            const capabilities = message.result
              ? getCapabilities(message.result)
              : null;

            // Render each user or assistant message.
            return (
              <article
                key={message.id}
                className={
                  message.role === "user"
                    ? "ml-auto max-w-[90%] rounded-2xl rounded-tr-sm bg-[#722F43] px-5 py-4 text-sm leading-7 text-white"
                    : "rounded-2xl border border-[#E2E8F0] bg-white px-6 py-5"
                }
              >
                {/* Label assistant messages clearly. */}
                {message.role === "assistant" && (
                  <div className="mb-4 flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold text-[#722F43]">
                      NEXORA
                    </span>

                    {/* Display analytics only if an analytics function ran. */}
                    {capabilities?.analytics && (
                      <span className="rounded-full bg-[#F0FDFA] px-2.5 py-1 text-[11px] font-semibold text-[#0F766E]">
                        Analytics
                      </span>
                    )}

                    {/* Display document intelligence only if retrieval ran. */}
                    {capabilities?.documents && (
                      <span className="rounded-full bg-[#F5F3FF] px-2.5 py-1 text-[11px] font-semibold text-[#6D28D9]">
                        Documents
                      </span>
                    )}
                  </div>
                )}

                {/* Preserve line breaks in the returned answer. */}
                {message.role === "assistant" ? (
                  <div className="min-w-0 break-words text-sm leading-7 text-[#334155]">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      skipHtml
                      components={{
                        p: ({ children }) => (
                          <p className="mb-3 last:mb-0">{children}</p>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-[#17243A]">
                            {children}
                          </strong>
                        ),
                        ul: ({ children }) => (
                          <ul className="mb-4 list-disc space-y-1 pl-6">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="mb-4 list-decimal space-y-1 pl-6">
                            {children}
                          </ol>
                        ),
                        h2: ({ children }) => (
                          <h2 className="mb-3 mt-5 text-lg font-semibold text-[#17243A]">
                            {children}
                          </h2>
                        ),
                        h3: ({ children }) => (
                          <h3 className="mb-2 mt-4 font-semibold text-[#17243A]">
                            {children}
                          </h3>
                        ),
                        table: ({ children }) => (
                          <div className="my-4 overflow-x-auto rounded-lg border border-[#E2E8F0]">
                            <table className="w-full text-left text-sm">
                              {children}
                            </table>
                          </div>
                        ),
                        th: ({ children }) => (
                          <th className="border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3 font-semibold">
                            {children}
                          </th>
                        ),
                        td: ({ children }) => (
                          <td className="border-b border-[#F1F5F9] px-4 py-3">
                            {children}
                          </td>
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap break-words text-sm leading-7">
                    {message.content}
                  </p>
                )}

                {/* Display source metadata directly from Azure AI Search. */}
                {message.result &&
                  getDocumentSources(message.result).length > 0 && (
                    <div className="mt-5 rounded-xl border border-[#EAD5DD] bg-[#FAF7F8] p-4">
                      <p className="mb-3 text-xs font-semibold text-[#722F43]">
                        Sources · Azure AI Search
                      </p>

                      <div className="space-y-2">
                        {getDocumentSources(message.result).map((source) => (
                          <details
                            key={`${source.filename}:${source.page ?? "unknown"}`}
                            className="group rounded-lg border border-[#E9E3E3] bg-white"
                          >
                            <summary className="flex cursor-pointer list-none flex-wrap items-center gap-2 px-3 py-3 [&::-webkit-details-marker]:hidden">
                              <span className="min-w-0 flex-1 break-all text-xs font-medium text-[#334155]">
                                {source.filename}
                              </span>

                              {source.page !== null && (
                                <span className="shrink-0 rounded-md bg-[#F5E9ED] px-2 py-1 text-[11px] font-semibold text-[#722F43]">
                                  Page {source.page}
                                </span>
                              )}

                              <span className="text-xs text-[#722F43] group-open:hidden">
                                View passage ↓
                              </span>
                              <span className="hidden text-xs text-[#722F43] group-open:inline">
                                Hide passage ↑
                              </span>
                            </summary>

                            <div className="border-t border-[#E9E3E3] px-4 py-3">
                              <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-[#722F43]">
                                Retrieved passage
                              </p>
                              <p className="whitespace-pre-wrap break-words text-xs leading-6 text-[#475569]">
                                {source.content ?? "No passage text was returned for this source."}
                              </p>
                            </div>
                          </details>
                        ))}
                      </div>
                    </div>
                  )}

                {/* Show the actual tool names for transparent execution. */}
                {message.result && message.result.tool_calls.length > 0 && (
                  <div className="mt-5 border-t border-[#E2E8F0] pt-4">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-[#64748B]">
                      Tools used
                    </p>
                    <p className="mt-2 break-words text-xs leading-5 text-[#64748B]">
                      {[
                        ...new Set(
                          message.result.tool_calls.map((call) => call.name),
                        ),
                      ].join(" · ")}
                    </p>
                  </div>
                )}
              </article>
            );
          })}

          {/* Indicate that the copilot is processing a request. */}
          {loading && (
            <div
              role="status"
              className="rounded-xl border border-[#E2E8F0] bg-white px-5 py-4 text-sm text-[#64748B]"
            >
              Analyzing your question...
            </div>
          )}

          {/* Keep the newest message visible. */}
          <div ref={bottomRef} />
        </div>
      )}

      {/* Display recoverable API errors. */}
      {error && (
        <div
          role="alert"
          className="mt-5 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}

      {/* Provide a real question input and submission form. */}
      <form
        onSubmit={(event) => {
          // Prevent a browser page reload.
          event.preventDefault();

          // Send the currently entered question.
          void sendQuestion(question);
        }}
        className="mt-4 shrink-0 rounded-xl border border-[#CBD5E1] bg-white p-4 shadow-sm focus-within:border-[#C79BAA]"
      >
        {/* Accept multi-line questions. */}
        <textarea
          aria-label="Ask Enterprise Copilot"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={(event) => {
            // Enter sends; Shift+Enter inserts a new line.
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void sendQuestion(question);
            }
          }}
          disabled={loading}
          maxLength={2000}
          rows={2}
          placeholder="Ask a question about your business or documents..."
          className="w-full resize-none border-0 bg-transparent text-sm leading-6 text-[#17243A] outline-none ring-0 focus:border-0 focus:outline-none focus:ring-0 placeholder:text-[#94A3B8] disabled:opacity-60"
        />

        {/* Show the input limit and working Send button. */}
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-[#94A3B8]">
            {question.length}/2000 characters
          </span>

          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="rounded-lg bg-[#722F43] px-5 py-2.5 text-xs font-semibold text-white transition hover:bg-[#512132] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Working..." : "Send"}
          </button>
        </div>
      </form>

      {/* Explain that AI answers require appropriate review. */}
      <p className="mt-4 text-center text-xs text-[#94A3B8]">
        AI-generated responses should be reviewed before business decisions.
      </p>
    </section>
  );
}
