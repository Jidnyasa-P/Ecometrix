import type { Cell, FieldDef } from "../lib/types";
import { fmtNum } from "../lib/format";
import { EvidenceBadge } from "./Bits";

export default function CellCard({ cell, fields, onClose }: { cell: Cell; fields: FieldDef[]; onClose: () => void }) {
  return (
    <aside className="cellcard" aria-label="Selected hexagon">
      <div className="cellcard__head">
        <div>
          <p className="kicker">Selected hexagon</p>
          <p className="cellcard__loc">{cell.lat.toFixed(4)}°N, {cell.lng.toFixed(4)}°E · {fmtNum(cell.area_km2 * 100, 1)} ha</p>
        </div>
        <button className="iconbtn" onClick={onClose} aria-label="Close hexagon details">✕</button>
      </div>
      <dl className="cellcard__list">
        {fields.map(f => {
          const v = cell.v[f.key];
          return (
            <div key={f.key} className="cellcard__row">
              <dt>{f.label} <EvidenceBadge kind={f.evidence} title={f.about} /></dt>
              <dd>{v == null ? <span className="muted">no data</span> : <><strong>{fmtNum(v, f.decimals > 1 ? 2 : f.decimals)}</strong> <span className="muted">{f.unit}</span></>}</dd>
            </div>
          );
        })}
      </dl>
      <p className="cellcard__foot">Hexagon id <code>{cell.h3}</code>. Sources for each value are listed on the Method page.</p>
    </aside>
  );
}
