import type { FieldDef } from "../lib/types";
import { cssGradient, type Theme } from "../lib/colors";
import { fmtNum } from "../lib/format";
import { EvidenceBadge } from "./Bits";

export default function Legend({ field, theme }: { field: FieldDef; theme: Theme }) {
  const d = field.decimals > 1 ? 2 : field.decimals;
  return (
    <div className="legend">
      <div className="legend__top">
        <strong>{field.label}</strong>
        <EvidenceBadge kind={field.evidence} />
      </div>
      <div className="legend__bar" style={{ background: cssGradient(field.ramp, theme) }} aria-hidden="true" />
      <div className="legend__ends">
        <span>{fmtNum(field.domain[0], d)}</span>
        <span className="legend__unit">{field.unit}</span>
        <span>{fmtNum(field.domain[1], d)}</span>
      </div>
      <p className="legend__note">Colours span the 2nd to 98th percentile of all hexagons, so a few extreme cells do not wash out the rest.</p>
    </div>
  );
}
