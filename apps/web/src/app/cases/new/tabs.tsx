"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";

type TabId = "chat" | "form";

const tabs: ReadonlyArray<{ id: TabId; label: string }> = [
  { id: "chat", label: "Chat with Karen" },
  { id: "form", label: "Structured form" },
];

const mockMessages: ReadonlyArray<{
  from: "karen" | "you";
  text: string;
}> = [
  {
    from: "karen",
    text: "Hi, I'm Karen. Tell me what happened and I'll take it from here. Which company wronged you?",
  },
  {
    from: "you",
    text: "My airline cancelled my flight and only offered a voucher.",
  },
  {
    from: "karen",
    text: "Classic. Depending on the route, you may be owed a full cash refund. Do you have the booking confirmation email?",
  },
];

export function NewCaseTabs() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");

  return (
    <div>
      <div role="tablist" aria-label="Case intake method" className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`panel-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            className={`min-h-11 flex-1 rounded-md px-4 text-sm font-semibold transition-colors ${
              activeTab === tab.id
                ? "bg-white text-ink-900 shadow-sm"
                : "text-ink-600 hover:text-ink-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div
        role="tabpanel"
        id="panel-chat"
        aria-labelledby="tab-chat"
        hidden={activeTab !== "chat"}
        className="mt-6"
      >
        <Card className="p-0">
          <ul className="flex flex-col gap-4 p-6">
            {mockMessages.map((message, index) => (
              <li
                key={index}
                className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
                  message.from === "karen"
                    ? "self-start bg-slate-100 text-ink-900"
                    : "self-end bg-accent-600 text-white"
                }`}
              >
                {message.text}
              </li>
            ))}
          </ul>
          <div className="flex gap-3 border-t border-slate-200 p-4">
            <label htmlFor="chat-input" className="sr-only">
              Message Karen
            </label>
            <input
              id="chat-input"
              type="text"
              placeholder="Describe what happened…"
              disabled
              className="min-h-11 flex-1 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm"
            />
            <Button disabled>Send</Button>
          </div>
        </Card>
        <p className="mt-3 text-xs text-ink-400">
          Chat is a preview — not functional yet.
        </p>
      </div>

      <div
        role="tabpanel"
        id="panel-form"
        aria-labelledby="tab-form"
        hidden={activeTab !== "form"}
        className="mt-6"
      >
        <Card>
          <form className="flex flex-col gap-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="company" className="text-sm font-medium">
                  Company
                </label>
                <input
                  id="company"
                  type="text"
                  placeholder="e.g. Acme Airlines"
                  disabled
                  className="min-h-11 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="category" className="text-sm font-medium">
                  Category
                </label>
                <select
                  id="category"
                  disabled
                  className="min-h-11 rounded-lg border border-slate-300 bg-slate-50 px-3 text-sm"
                >
                  <option>Refund</option>
                  <option>Cancellation</option>
                  <option>Billing dispute</option>
                  <option>Defective product</option>
                  <option>Other</option>
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="incident-date" className="text-sm font-medium">
                  Incident date
                </label>
                <input
                  id="incident-date"
                  type="date"
                  disabled
                  className="min-h-11 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="amount" className="text-sm font-medium">
                  Amount (USD)
                </label>
                <input
                  id="amount"
                  type="number"
                  placeholder="0.00"
                  disabled
                  className="min-h-11 rounded-lg border border-slate-300 bg-slate-50 px-4 text-sm"
                />
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="description" className="text-sm font-medium">
                What happened?
              </label>
              <textarea
                id="description"
                rows={4}
                placeholder="Give Karen the details — dates, order numbers, who you talked to…"
                disabled
                className="rounded-lg border border-slate-300 bg-slate-50 px-4 py-3 text-sm"
              />
            </div>
            <div>
              <Button type="submit" disabled>
                Submit case
              </Button>
            </div>
          </form>
        </Card>
        <p className="mt-3 text-xs text-ink-400">
          Form is a preview — not functional yet.
        </p>
      </div>
    </div>
  );
}
