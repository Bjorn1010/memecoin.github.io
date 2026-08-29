type IconProps = { className?: string };

export function PlayIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M8 5.14v13.72c0 .7.78 1.12 1.36.73l10.68-6.86a.87.87 0 0 0 0-1.46L9.36 4.41A.87.87 0 0 0 8 5.14Z" />
    </svg>
  );
}

export function StopIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  );
}

export function GearIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={className}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M10.5 3.75h3l.5 2.2a6.5 6.5 0 0 1 1.8 1.04l2.15-.7 1.5 2.6-1.7 1.5a6.6 6.6 0 0 1 0 2.08l1.7 1.5-1.5 2.6-2.15-.7a6.5 6.5 0 0 1-1.8 1.04l-.5 2.2h-3l-.5-2.2a6.5 6.5 0 0 1-1.8-1.04l-2.15.7-1.5-2.6 1.7-1.5a6.6 6.6 0 0 1 0-2.08l-1.7-1.5 1.5-2.6 2.15.7a6.5 6.5 0 0 1 1.8-1.04l.5-2.2Z"
      />
      <circle cx="12" cy="12" r="2.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BoltIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className={className}>
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
    </svg>
  );
}

export function WalletIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={className}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 7.5A2.5 2.5 0 0 1 5.5 5h11A2.5 2.5 0 0 1 19 7.5V8H5.5A2.5 2.5 0 0 1 3 5.5v2Z"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 8h15a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V8Z"
      />
      <circle cx="16.5" cy="14" r="1.25" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function ResetIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={className}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h5" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 9A7.5 7.5 0 1 1 4 13.5" />
    </svg>
  );
}

export function CoinsStackIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={className}>
      <ellipse cx="12" cy="6" rx="7" ry="3" />
      <path strokeLinecap="round" d="M5 6v5c0 1.66 3.13 3 7 3s7-1.34 7-3V6" />
      <path strokeLinecap="round" d="M5 11v5c0 1.66 3.13 3 7 3s7-1.34 7-3v-5" />
    </svg>
  );
}

export function ReceiptIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className={className}>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6 3h12v18l-2.5-1.5L13 21l-2.5-1.5L8 21l-2-1.5V3Z"
      />
      <path strokeLinecap="round" d="M9 8h6M9 12h6" />
    </svg>
  );
}
