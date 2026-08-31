/**
 * Reporting over a recorded run.
 *
 *   npm run report -- --dir data/20260831-220000
 *   npm run report -- --observations <path> --attempts <path>
 */
import { existsSync } from "node:fs";
import { join } from "node:path";
import {
  buildObserveReport,
  renderAttemptReport,
  renderObserveReport,
} from "../obs/reports.js";

function flag(name: string): string | null {
  const i = process.argv.indexOf(name);
  return i >= 0 && i + 1 < process.argv.length ? process.argv[i + 1]! : null;
}

function main(): void {
  const dir = flag("--dir");
  const observations = flag("--observations") ?? (dir ? join(dir, "observations.jsonl") : null);
  const attempts = flag("--attempts") ?? (dir ? join(dir, "attempts.jsonl") : null);

  if (!observations && !attempts) {
    console.error("usage: npm run report -- --dir data/<run>");
    process.exit(2);
  }

  if (observations && existsSync(observations)) {
    console.log(renderObserveReport(buildObserveReport(observations)));
    console.log("");
  }
  if (attempts && existsSync(attempts)) {
    console.log(renderAttemptReport(attempts));
  }
}

main();
