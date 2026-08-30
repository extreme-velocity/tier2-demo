#!/usr/bin/env node
// Local LLM bridge — exposes an OpenAI-compatible chat-completions endpoint
// backed by any SDK that isn't natively OpenAI-compatible (z-ai-web-dev-sdk
// in this repo's default install).
//
// Why: every AI script in this kit talks to an OpenAI-compatible
// `/v1/chat/completions` URL (AI_REVIEW_BASE_URL). Point that variable at
// this bridge and you can exercise the full review/sweep pipeline — real
// prompts, real diffs, real parsing — against a local model before you
// spend a cent on API keys.
//
//   cd scripts/dev/llm-bridge && npm install && npm start
//   # then, from the kit root:
//   AI_REVIEW_BASE_URL=http://127.0.0.1:8787/v1 \
//   AI_REVIEW_API_KEY=local-dev AI_REVIEW_MODEL=zai-local \
//   AI_REVIEW_DRY_RUN=1 REPO=owner/repo PR_NUMBER=42 GITHUB_TOKEN=ghp_x \
//     python3 scripts/ai_review.py
//
// The bridge is intentionally dumb: no auth, no rate limiting, localhost
// only. Do NOT expose it beyond your machine.

import http from "node:http";
import ZAI from "z-ai-web-dev-sdk";

const PORT = Number(process.env.PORT || 8787);
const HOST = process.env.HOST || "127.0.0.1";

const zai = await ZAI.create();

// OpenAI messages -> SDK messages.
// The zai SDK takes the system prompt as the FIRST message with
// role 'assistant'; user/assistant messages pass through unchanged.
function toSdkMessages(messages) {
  return messages.map((m) => ({
    role: m.role === "system" ? "assistant" : m.role,
    content: m.content,
  }));
}

function openAiResponse(model, content) {
  return {
    id: `bridge-${Date.now().toString(36)}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model,
    choices: [
      {
        index: 0,
        message: { role: "assistant", content },
        finish_reason: "stop",
      },
    ],
    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  };
}

const server = http.createServer(async (req, res) => {
  const send = (code, obj) => {
    res.writeHead(code, { "Content-Type": "application/json" });
    res.end(JSON.stringify(obj));
  };

  if (req.method === "GET" && (req.url === "/healthz" || req.url === "/")) {
    return send(200, { ok: true, bridge: "zai-local", endpoints: ["/v1/chat/completions"] });
  }

  // Minimal /v1/models so generic OpenAI clients can enumerate.
  if (req.method === "GET" && req.url === "/v1/models") {
    return send(200, {
      object: "list",
      data: [{ id: "zai-local", object: "model", owned_by: "bridge" }],
    });
  }

  if (
    req.method === "POST" &&
    (req.url === "/v1/chat/completions" || req.url === "/chat/completions")
  ) {
    let raw = "";
    for await (const chunk of req) raw += chunk;
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      return send(400, { error: { message: "invalid JSON body" } });
    }
    const inChars = (payload.messages || []).reduce((n, m) => n + (m.content || "").length, 0);
    const started = Date.now();
    try {
      const completion = await zai.chat.completions.create({
        messages: toSdkMessages(payload.messages || []),
        thinking: { type: "disabled" },
      });
      const content = completion?.choices?.[0]?.message?.content ?? "";
      if (!content.trim()) throw new Error("empty completion from SDK");
      console.error(
        `[bridge] ${payload.model || "zai-local"} in=${inChars}ch out=${content.length}ch ${Date.now() - started}ms`,
      );
      return send(200, openAiResponse(payload.model || "zai-local", content));
    } catch (err) {
      console.error(`[bridge] error after ${Date.now() - started}ms: ${err.message}`);
      return send(502, { error: { message: `bridge upstream error: ${err.message}` } });
    }
  }

  send(404, { error: { message: `no route ${req.method} ${req.url}` } });
});

server.listen(PORT, HOST, () => {
  console.error(`[bridge] OpenAI-compatible zai bridge listening on http://${HOST}:${PORT}/v1`);
});
