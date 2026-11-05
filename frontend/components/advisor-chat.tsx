"use client";

import { type FormEvent, useState } from "react";

import {
  type AdvisorLanguage,
  type AdvisorMessage,
  type RecommendationRequest,
  type RecommendationResponse,
  udyamOneApi,
} from "@/lib/api";

const languages: Array<{ value: AdvisorLanguage; label: string }> = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "te", label: "తెలుగు" },
  { value: "ta", label: "தமிழ்" },
  { value: "kn", label: "ಕನ್ನಡ" },
];

const suggestedQuestions = [
  "I need reliable internet for my office.",
  "I have multiple business locations.",
  "Which package is more affordable?",
  "Why are you recommending this product?",
  "I need better data security.",
  "Can you explain the quotation?",
];

export function AdvisorChat({
  request,
  recommendation,
  onRecommendationUpdate,
}: {
  request: RecommendationRequest;
  recommendation: RecommendationResponse;
  onRecommendationUpdate: (
    recommendations: RecommendationResponse,
    request: RecommendationRequest,
  ) => void;
}) {
  const [messages, setMessages] = useState<AdvisorMessage[]>([]);
  const [language, setLanguage] = useState<AdvisorLanguage>("en");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessages = async (history: AdvisorMessage[]) => {
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await udyamOneApi.advisorChat({
        ...request,
        messages: history.slice(-12),
        language,
      });
      const nextHistory = [...history.slice(-11), { role: "assistant" as const, content: response.reply }];
      setMessages(nextHistory);
      if (response.recommendations_refreshed && response.recommendations) {
        onRecommendationUpdate(response.recommendations, {
          ...request,
          primary_requirements: [
            ...new Set([...request.primary_requirements, ...response.extracted_requirements]),
          ],
        });
      }
    } catch (sendError) {
      setError(sendError instanceof Error ? sendError.message : "The advisor could not respond.");
      setMessages(history.slice(-12));
    } finally {
      setLoading(false);
    }
  };

  const send = async (content: string) => {
    const trimmed = content.trim();
    if (!trimmed || loading) return;
    const history = [...messages, { role: "user" as const, content: trimmed }].slice(-12);
    setDraft("");
    await sendMessages(history);
  };

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void send(draft);
  };

  const clearConversation = () => {
    setMessages([]);
    setDraft("");
    setError(null);
  };

  return (
    <section aria-labelledby="advisor-title" className="mb-10 rounded-2xl border border-[#e3e8ee] bg-white p-5 shadow-[0_12px_34px_rgba(16,34,62,0.05)] sm:p-7">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-[#c93835]">AI business advisor</p>
          <h2 className="mt-2 text-xl font-semibold tracking-[-0.03em] text-[#10223e]" id="advisor-title">Talk through what your business needs.</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#68768a]">Ask questions about your requirements or the catalogue-backed options. New needs are checked by the existing recommendation rules.</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="sr-only" htmlFor="advisor-language">Response language</label>
          <select className="rounded-lg border border-[#d9e0e8] bg-white px-3 py-2 text-sm text-[#31445e]" id="advisor-language" onChange={(event) => setLanguage(event.target.value as AdvisorLanguage)} value={language}>
            {languages.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <button className="text-sm font-semibold text-[#c93835] hover:underline disabled:opacity-50" disabled={!messages.length || loading} onClick={clearConversation} type="button">Clear chat</button>
        </div>
      </div>

      <div aria-live="polite" className="mt-6 grid max-h-96 gap-3 overflow-y-auto rounded-xl bg-[#f7f8fa] p-4">
        {!messages.length ? <p className="text-sm leading-6 text-[#68768a]">Choose a suggested question or type your own. The configured AI provider processes messages; UdyamOne does not save this conversation.</p> : null}
        {messages.map((message, index) => (
          <div className={`max-w-[88%] rounded-xl px-4 py-3 text-sm leading-6 ${message.role === "user" ? "ml-auto bg-[#10223e] text-white" : "bg-white text-[#33455f] shadow-sm"}`} key={`${index}-${message.role}`}>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.12em] opacity-70">{message.role === "user" ? "You" : "Advisor"}</p>
            <p className="whitespace-pre-wrap">{message.content}</p>
          </div>
        ))}
        {loading ? <p className="text-sm text-[#68768a]" role="status">Advisor is thinking…</p> : null}
      </div>

      <form className="mt-4 flex flex-col gap-3 sm:flex-row" onSubmit={submit}>
        <label className="sr-only" htmlFor="advisor-message">Your message</label>
        <input autoComplete="off" className="min-h-12 flex-1 rounded-lg border border-[#d9e0e8] px-4 text-sm text-[#1f324c] outline-none focus:border-[#c93835] focus:ring-4 focus:ring-[#fdebea]" id="advisor-message" maxLength={1200} onChange={(event) => setDraft(event.target.value)} placeholder="Ask about your business needs…" value={draft} />
        <button className="min-h-12 rounded-lg bg-[#d9433f] px-6 text-sm font-semibold text-white transition hover:bg-[#c33532] disabled:cursor-not-allowed disabled:opacity-60" disabled={!draft.trim() || loading} type="submit">{loading ? "Sending…" : "Send"}</button>
      </form>

      {error ? <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg bg-[#fff1ef] p-3 text-sm text-[#a82e2b]" role="alert"><span>{error}</span><button className="font-semibold underline" disabled={loading} onClick={() => void sendMessages(messages)} type="button">Retry</button></div> : null}

      {!messages.length ? <div className="mt-4 flex flex-wrap gap-2">{suggestedQuestions.map((question) => <button className="rounded-full border border-[#dfe5eb] px-3 py-2 text-left text-xs font-medium text-[#526279] transition hover:border-[#c93835] hover:text-[#b53431] disabled:opacity-50" disabled={loading} key={question} onClick={() => void send(question)} type="button">{question}</button>)}</div> : null}

      <p className="mt-4 text-xs leading-5 text-[#7b8797]">Conversation stays in this browser session only. Messages are sent to the configured AI provider. Recommendations and prices are prototype outputs based on the current catalogue and are subject to commercial verification.</p>
      {recommendation.bundles.length ? <p className="mt-2 text-xs text-[#7b8797]">The bundle cards and quote preview below remain the authoritative source for product details and calculated prices.</p> : null}
    </section>
  );
}
