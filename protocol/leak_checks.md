# SILEX leak checks (verbatim answers; times Asia/Kolkata, 2026-11-13)
Note: the Claude app used here has no switch for web search. The control is a line in the prompt.

## Claude, check 1, 12:02. Web search was ON (the model says it searched).
Verdict: not exposed. Deviation from protocol: search on; the search found nothing. Kept on file, not the official check.
Answer:
Let me check quickly rather than guess.

No, I don't know of a constructed language called SILEX, and a quick search turned up nothing on it, only unrelated papers about AI-generated conlangs and symbols. I won't guess at what it is; if you have a link or description, I can work from that.

## Claude, check 2, 12:12. User told the model not to search; no mention of searching in the answer. OFFICIAL check for Claude.
Verdict: not exposed.
Answer:
Leak check: I don't know of a constructed language called "SILEX" for AI agents, so I can't tell you anything reliable about it. If you share what you have on it, I'm happy to work from that.

## Claude, check 3, 12:17. No mention of searching. A repeat; check 2 stays the official one for Claude. All three Claude checks: not exposed.
Verdict: not exposed. Only "Silex" it knows is an unrelated PHP micro-framework (a name clash, not exposure).
Answer:
No, I don't have any reliable knowledge of a constructed language called SILEX for AI agents, so I won't guess at what it is. The only "Silex" I know of is an unrelated PHP micro-framework.

## ChatGPT, check 1, 14:23. Sent by the user as "Gpt leak check". OFFICIAL check for ChatGPT (first and only so far).
Verdict: not exposed. No mention of searching in the answer. Model version not given. Whether ChatGPT's own web search was on was not stated (the control is the prompt line).
Answer:
No, I don't have reliable knowledge of a constructed symbol-based language called SILEX used for communication between AI agents. I won't guess.

## Grok, check 1, 14:45. Sent by the user as "Grok's leak check". OFFICIAL check for Grok (first and only so far).
Verdict: not exposed. No mention of searching in the answer. Model version not given. Whether Grok's own search or DeepSearch was on was not stated (the control is the prompt line).
Answer:
I do not know of any constructed language called “SILEX,” nor of a symbol-based language that AI agents use to write to each other.

## Gemini, check 1, 20:12. Sent by the user as "Gemini leak check". OFFICIAL check for Gemini (first and only so far).
Verdict: not exposed. No mention of searching in the answer. Model version not given. Whether Gemini's own search or tools were on was not stated (the control is the prompt line).
Answer:
I do not know about a constructed symbol-based language called "SILEX" used by AI agents to communicate with each other.

## Summary
Official check per model: Claude (check 2), ChatGPT, Grok, Gemini. All four: not exposed. Each answer says it does not know SILEX; none describes it.
Model versions were not given for any of them. Gemini's answer came as plain text in the message (not an attachment).
