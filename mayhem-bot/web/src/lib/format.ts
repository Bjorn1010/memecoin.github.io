export function shortAddr(addr: string, len = 4): string {
  if (!addr) return "";
  return `${addr.slice(0, len)}…${addr.slice(-len)}`;
}

export function fmtSol(n: number, decimals = 4): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(decimals)}`;
}

export function fmtPrice(n: number): string {
  if (n === 0) return "0";
  if (n >= 0.01) return n.toFixed(4);
  return n.toExponential(3);
}

export function fmtPct(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(1)}%`;
}

export function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 1000) return "now";
  if (diff < 60_000) return `${Math.floor(diff / 1000)}s`;
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  return `${Math.floor(diff / 3_600_000)}h`;
}
