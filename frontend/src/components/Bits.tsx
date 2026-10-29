import type { ReactNode } from "react";
import type { Evidence } from "../lib/types";

export function EvidenceBadge({ kind, title }: { kind: Evidence; title?: string }) {
  return <span className={`badge badge--${kind.toLowerCase()}`} title={title}>{kind}</span>;
}

export const Arrow = () => (
  <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11m-4-5 5 5-5 5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
);

export const HexMark = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
    <path d="M32 6l21 12.5v27L32 58 11 45.500v-27z" fill="none" stroke="currentColor" strokeWidth="5" strokeLinejoin="round" />
    <path d="M32 42V27m0 7c-5.500 0-9-3.500-9-9 5.500 0 9 3.500 9 9zm0 2c4.500 0 8-2.500 8-8-4.500 0-8 2.500-8 8z" fill="var(--accent)" />
  </svg>
);

export function Section({ id, className = "", children }: { id?: string; className?: string; children: ReactNode }) {
  return <section id={id} className={`section ${className}`}><div className="wrap">{children}</div></section>;
}

export function PageHead({ kicker, title, children }: { kicker: string; title: string; children?: ReactNode }) {
  return (
    <header className="pagehead">
      <div className="wrap">
        <p className="kicker">{kicker}</p>
        <h1 className="display">{title}</h1>
        {children && <div className="lede">{children}</div>}
      </div>
    </header>
  );
}

/** Honest states for loading, waking, missing data and errors. */
export function Notice({ tone = "info", title, children }: { tone?: "info" | "warn" | "error"; title: string; children?: ReactNode }) {
  return (
    <div className={`notice notice--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
