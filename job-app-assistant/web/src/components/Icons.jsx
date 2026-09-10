// Icônes minimalistes (style outline), dessinées à la main en SVG pour éviter
// une dépendance externe. Toutes acceptent une prop `className`.

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function IconBuilding({ className }) {
  return (
    <svg {...base} className={className}>
      <rect x="4" y="3" width="12" height="18" rx="1" />
      <path d="M16 21V9l4 2v10" />
      <path d="M8 7h1M11 7h1M8 10.5h1M11 10.5h1M8 14h1M11 14h1M8 17.5h1M11 17.5h1" />
    </svg>
  );
}

export function IconFileText({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M7 3h7l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" />
      <path d="M14 3v4h4" />
      <path d="M9 12.5h6M9 15.5h6M9 9.5h2" />
    </svg>
  );
}

export function IconUpload({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M12 15V4" />
      <path d="m7.5 8.5 4.5-4.5 4.5 4.5" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

export function IconDownload({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M12 4v11" />
      <path d="m7.5 11.5 4.5 4.5 4.5-4.5" />
      <path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1" />
    </svg>
  );
}

export function IconSparkles({ className }) {
  return (
    <svg {...base} fill="currentColor" stroke="none" viewBox="0 0 24 24" className={className}>
      <path d="M11 2.5a.6.6 0 0 1 1.14-.26l1.2 2.9 2.9 1.2a.6.6 0 0 1 0 1.1l-2.9 1.2-1.2 2.9a.6.6 0 0 1-1.14 0l-1.2-2.9-2.9-1.2a.6.6 0 0 1 0-1.1l2.9-1.2Z" />
      <path d="M18.5 13a.5.5 0 0 1 .95-.2l.6 1.5 1.5.6a.5.5 0 0 1 0 .95l-1.5.6-.6 1.5a.5.5 0 0 1-.95 0l-.6-1.5-1.5-.6a.5.5 0 0 1 0-.95l1.5-.6Z" />
      <path d="M5 15a.5.5 0 0 1 .95-.2l.4 1 1 .4a.5.5 0 0 1 0 .95l-1 .4-.4 1a.5.5 0 0 1-.95 0l-.4-1-1-.4a.5.5 0 0 1 0-.95l1-.4Z" />
    </svg>
  );
}

export function IconCheck({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="m5 13 4 4L19 7" />
    </svg>
  );
}

export function IconCheckCircle({ className }) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" />
    </svg>
  );
}

export function IconTrash({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M5 7h14" />
      <path d="M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
      <path d="M7 7l1 13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l1-13" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

export function IconArrowLeft({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M19 12H5" />
      <path d="m11 6-6 6 6 6" />
    </svg>
  );
}

export function IconLogOut({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M9 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h3" />
      <path d="M15 16l4-4-4-4" />
      <path d="M19 12H9" />
    </svg>
  );
}

export function IconPlus({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function IconLoader({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={className}>
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeDasharray="42 100"
      />
    </svg>
  );
}

export function IconGraduationCap({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="m2 9 10-4 10 4-10 4-10-4Z" />
      <path d="M6 11v4.5c0 1 2.5 2.5 6 2.5s6-1.5 6-2.5V11" />
      <path d="M21 9v6" />
    </svg>
  );
}

export function IconUserCircle({ className }) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.3 18a6 6 0 0 1 11.4 0" />
    </svg>
  );
}

export function IconMapPin({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M12 21s7-6.1 7-11.5A7 7 0 0 0 5 9.5C5 14.9 12 21 12 21Z" />
      <circle cx="12" cy="9.5" r="2.25" />
    </svg>
  );
}

export function IconLink({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M9.5 14.5 14.5 9.5" />
      <path d="M11 6.5 12.4 5a3.5 3.5 0 0 1 5 5L16 11.4" />
      <path d="M13 17.5 11.6 19a3.5 3.5 0 0 1-5-5L8 12.6" />
    </svg>
  );
}

export function IconMenu({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M4 6h16M4 12h16M4 18h16" />
    </svg>
  );
}

export function IconX({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export function IconChevronRight({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

export function IconClock({ className }) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </svg>
  );
}

export function IconInbox({ className }) {
  return (
    <svg {...base} className={className}>
      <path d="M4 13h4.2l1.4 2.5h4.8L15.8 13H20" />
      <path d="M5.5 6h13l1.5 7v5a1.5 1.5 0 0 1-1.5 1.5H5.5A1.5 1.5 0 0 1 4 18v-5l1.5-7Z" />
    </svg>
  );
}

export function IconAlertCircle({ className }) {
  return (
    <svg {...base} className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v5" />
      <path d="M12 16.2v.1" />
    </svg>
  );
}
