import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

/**
 * Flat-file rolling list of one-line lessons the agent has written about its own past
 * trades ("j'ai acheté X parce que Y, résultat Z"). This is the "learning" mechanism
 * discussed for this agent — not weight updates, a growing playbook fed back into every
 * future decision prompt (see buildDecisionPrompt in alxcooksPlaybook.ts).
 */
export class MemoryStore {
  private lessons: string[] = [];

  constructor(
    private filePath: string,
    private maxEntries: number,
  ) {
    this.load();
  }

  private load() {
    try {
      if (existsSync(this.filePath)) {
        const raw = JSON.parse(readFileSync(this.filePath, "utf-8"));
        if (Array.isArray(raw)) this.lessons = raw.filter((l) => typeof l === "string");
      }
    } catch {
      this.lessons = [];
    }
  }

  private persist() {
    try {
      mkdirSync(dirname(this.filePath), { recursive: true });
      writeFileSync(this.filePath, JSON.stringify(this.lessons, null, 2));
    } catch (err) {
      console.warn("[alx-agent] failed to persist memory:", err instanceof Error ? err.message : err);
    }
  }

  add(lesson: string) {
    this.lessons.push(lesson);
    if (this.lessons.length > this.maxEntries) this.lessons.shift();
    this.persist();
  }

  recent(n = 10): string[] {
    return this.lessons.slice(-n);
  }
}
