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

  const haveObservations = Boolean(observations && existsSync(observations));
  const haveAttempts = Boolean(attempts && existsSync(attempts));

  if (!haveObservations && !haveAttempts) {
    // Silence here would look like a broken command. An empty run is the most
    // common early result and it means something specific, so say it.
    console.log("=== nothing recorded ===");
    console.log("");
    console.log("No observations and no attempts were written for this run.");
    console.log("That is a result, not a failure: the bot evaluated cycles and none");
    console.log("cleared the gross-profit bar, so there was nothing to record.");
    console.log("");
    console.log("The run summary printed on shutdown shows the reject breakdown —");
    console.log("`not-profitable-gross` means the gaps were smaller than the fees,");
    console.log("`size-below-dust` means the pools were too shallow to trade at");
    console.log("MIN_TRADE_SIZE, and `stale-state` would mean a feed problem.");
    console.log("");
    console.log("Observe for longer, or widen MAX_WATCHED_POOLS, before concluding.");
    return;
  }

  if (haveObservations) {
    console.log(renderObserveReport(buildObserveReport(observations!)));
    console.log("");
  }
  if (haveAttempts) {
    console.log(renderAttemptReport(attempts!));
  }
}

main();
