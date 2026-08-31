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
        // gpt-oss models spend part of the token budget on an internal "reasoning" field
        // before writing the JSON content — measured 500-570 reasoning tokens per call by
        // default, which is most of why the free tier's daily quota (200k tokens/day)
        // burned out after less than half an hour of real traffic. reasoning_effort:"low"
        // (a gpt-oss-specific param, honored by Groq) cut that to ~6 tokens per call in
        // testing with no visible drop in decision quality — a ~2.4x cut in total tokens
        // per call, which directly multiplies how many decisions the free daily budget
        // actually buys. Harmless no-op on non-gpt-oss models if ALX_MODEL is swapped.
        reasoning_effort: "low",
        // Groq's rate limiter reserves max_tokens against the per-minute/per-day budget
        // UP FRONT, regardless of how much the model actually generates (confirmed live —
        // 429 "Requested" sizes matched prompt_tokens + max_tokens, not actual usage). With
        // reasoning_effort:"low" real completions run ~150-400 tokens, so 900 was wasting
        // roughly half of every reservation. 450 keeps real headroom without inflating the
        // reservation the limiter actually charges against.
        max_tokens: 450,
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
