"use client";

import ReactMarkdown from "react-markdown";
import { ChatMessage as ChatMessageType } from "@/types";

interface Props {
  message: ChatMessageType;
}

function stripChips(text: string): string {
  return text.replace(/\[CHIPS[:\s].*\](?!.*\])/gs, "").replace(/\[CHIPS[:\s].*$/s, "").trim();
}

const KOSIN_BASE = "https://umane.emeal.nttdata.com/jiraito/browse";

function TokenBadge({ token }: { token: string }) {
  return (
    <span className="px-1.5 py-0.5 bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 rounded text-xs font-mono font-bold">
      {token}
    </span>
  );
}

function renderInlineTokens(text: string): (string | JSX.Element)[] {
  const pattern = /(\[LINK:(.*?):(.*?)\])|(PESESG-\d+)|(\[[A-Z_]+\d*\])/g;
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));

    if (match[1]) {
      parts.push(
        <a key={match.index} href={match[2]} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-primary hover:text-blue-700 underline font-medium">
          {match[3]}
        </a>
      );
    } else if (match[4]) {
      parts.push(
        <a key={match.index} href={`${KOSIN_BASE}/${match[4]}`} target="_blank" rel="noopener noreferrer"
          className="text-primary hover:text-blue-700 underline font-medium">
          {match[4]}
        </a>
      );
    } else if (match[5]) {
      parts.push(<TokenBadge key={match.index} token={match[5]} />);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

const AgentIcon = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" className="text-primary">
    <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 110 2h-1.07A7.001 7.001 0 0113 22h-2a7.001 7.001 0 01-6.93-6H3a1 1 0 110-2h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
  </svg>
);

function AgentContent({ content }: { content: string }) {
  const cleaned = stripChips(content);

  return (
    <div className="text-sm leading-relaxed text-slate-800 dark:text-slate-200 prose prose-sm prose-slate dark:prose-invert max-w-none
      prose-headings:text-slate-900 dark:prose-headings:text-gray-100 prose-headings:font-bold prose-headings:mt-4 prose-headings:mb-2
      prose-h2:text-base prose-h3:text-sm
      prose-p:my-2 prose-p:leading-relaxed
      prose-strong:text-slate-900 dark:prose-strong:text-gray-100 prose-strong:font-semibold
      prose-ol:my-2 prose-ul:my-2 prose-li:my-0.5
      prose-a:text-primary prose-a:no-underline hover:prose-a:underline">
      <ReactMarkdown
        components={{
          p: ({ children }) => {
            if (typeof children === "string") {
              return <p>{renderInlineTokens(children)}</p>;
            }
            return <p>{children}</p>;
          },
          li: ({ children }) => {
            if (typeof children === "string") {
              return <li>{renderInlineTokens(children)}</li>;
            }
            return <li>{children}</li>;
          },
          code: ({ children }) => (
            <code className="px-1.5 py-0.5 bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded text-xs font-mono">{children}</code>
          ),
        }}
      >
        {cleaned}
      </ReactMarkdown>
    </div>
  );
}

export function ChatMessage({ message }: Props) {
  const isAgent = message.role === "agent";

  return (
    <div className={`flex gap-4 mb-6 ${isAgent ? "max-w-[85%]" : "justify-end"}`}>
      {isAgent && (
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0 border border-primary/20">
          <AgentIcon />
        </div>
      )}

      <div className={
        isAgent
          ? "bg-white dark:bg-slate-800 border-l-4 border-primary shadow-sm rounded-r-xl rounded-bl-xl p-4"
          : "bg-primary text-white shadow-md rounded-l-xl rounded-br-xl p-4 max-w-[85%]"
      }>
        {isAgent ? (
          <AgentContent content={message.content} />
        ) : (
          <div className="text-sm leading-relaxed text-white">{message.content}</div>
        )}
        <span className={`text-xs mt-2 block ${isAgent ? "text-slate-400 dark:text-slate-500" : "text-blue-100 text-right"}`}>
          <time dateTime={message.timestamp}>
            {isAgent ? "AI Agent" : "Tu"} &bull;{" "}
            {new Date(message.timestamp).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
          </time>
        </span>
      </div>

      {!isAgent && (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-slate-300 to-slate-400 dark:from-slate-600 dark:to-slate-500 flex items-center justify-center shrink-0">
          <span className="text-white text-xs font-bold">OP</span>
        </div>
      )}
    </div>
  );
}
