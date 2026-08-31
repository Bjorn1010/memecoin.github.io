import {
  ALX_COOKS_SYSTEM_PROMPT,
  buildDecisionPrompt,
  type AlxCooksDecision,
  type AlxCooksAction,
  type TokenContext,
} from "./alxcooksPlaybook.js";
import { aiConfig } from "./aiConfig.js";

const VALID_ACTIONS: AlxCooksAction[] = ["skip", "enter_scout", "scale_in", "hold", "scale_out", "exit_full"];

let warnedMissingKey = false;

/**
 * Calls a free-tier LLM (Groq — OpenAI-compatible chat completions, no cost, no card —
 * see console.groq.com) with the alxcooks reasoning playbook for one token decision.
 * Kept as a plain fetch call, not the OpenAI SDK, so the whole agent stays dependency-free;
 * swap the endpoint/body here if you want a different OpenAI-compatible provider later.
 */
export async function getAlxCooksDecision(
  context: TokenContext,
  recentLessons: string[],
): Promise<AlxCooksDecision | null> {
  if (!aiConfig.groqApiKey) {
    if (!warnedMissingKey) {
      console.warn("[alx-agent] GROQ_API_KEY not set — the agent can watch tokens but can't decide anything.");
      console.warn("[alx-agent] get a free key at https://console.groq.com/keys");
      warnedMissingKey = true;
    }
    return null;
  }

  try {
    const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${aiConfig.groqApiKey}`,
      },
      body: JSON.stringify({
        model: aiConfig.model,
        max_tokens: 500,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: ALX_COOKS_SYSTEM_PROMPT },
          { role: "user", content: buildDecisionPrompt(context, recentLessons) },
        ],
      }),
      signal: AbortSignal.timeout(15_000),
    });

    if (!res.ok) {
      console.warn(`[alx-agent] LLM call failed: ${res.status} ${await res.text().catch(() => "")}`);
      return null;
    }

    const data = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> };
    const text = data.choices?.[0]?.message?.content;
    if (!text) return null;

    return parseDecision(text);
  } catch (err) {
    console.warn("[alx-agent] LLM call error:", err instanceof Error ? err.message : err);
    return null;
  }
}

/** response_format:"json_object" guarantees valid JSON, but the shape/fields still need validating. */
function parseDecision(text: string): AlxCooksDecision | null {
  try {
    const raw = JSON.parse(text) as Partial<AlxCooksDecision>;
    if (!raw.action || !VALID_ACTIONS.includes(raw.action)) return null;

    return {
      action: raw.action,
      sizePct: clamp(Number(raw.sizePct) || 0, 0, 100),
      confidence: clamp(Number(raw.confidence) || 0, 0, 100),
      reasoning: typeof raw.reasoning === "string" ? raw.reasoning : "",
      redFlags: Array.isArray(raw.redFlags) ? raw.redFlags.filter((f) => typeof f === "string") : [],
      memoryNote: typeof raw.memoryNote === "string" ? raw.memoryNote : undefined,
    };
  } catch {
    return null;
  }
}

function clamp(v: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, v));
}
