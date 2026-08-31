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
 * Calls Claude with the alxcooks reasoning playbook for one token decision. Uses the raw
 * Anthropic Messages API via fetch (no SDK dependency) so this stays a drop-in call site —
 * swap the endpoint/parsing here if you want a different provider, nothing else changes.
 */
export async function getAlxCooksDecision(
  context: TokenContext,
  recentLessons: string[],
): Promise<AlxCooksDecision | null> {
  if (!aiConfig.anthropicApiKey) {
    if (!warnedMissingKey) {
      console.warn("[alx-agent] ANTHROPIC_API_KEY not set — the agent can watch tokens but can't decide anything.");
      warnedMissingKey = true;
    }
    return null;
  }

  try {
    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": aiConfig.anthropicApiKey,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: aiConfig.model,
        max_tokens: 500,
        system: ALX_COOKS_SYSTEM_PROMPT,
        messages: [{ role: "user", content: buildDecisionPrompt(context, recentLessons) }],
      }),
      signal: AbortSignal.timeout(15_000),
    });

    if (!res.ok) {
      console.warn(`[alx-agent] LLM call failed: ${res.status} ${await res.text().catch(() => "")}`);
      return null;
    }

    const data = (await res.json()) as { content?: Array<{ type: string; text?: string }> };
    const text = data.content?.find((b) => b.type === "text")?.text;
    if (!text) return null;

    return parseDecision(text);
  } catch (err) {
    console.warn("[alx-agent] LLM call error:", err instanceof Error ? err.message : err);
    return null;
  }
}

/** The model is asked for raw JSON but may still wrap it in prose or a code fence — extract defensively. */
function parseDecision(text: string): AlxCooksDecision | null {
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) return null;

  try {
    const raw = JSON.parse(match[0]) as Partial<AlxCooksDecision>;
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
