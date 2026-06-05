
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response


router = APIRouter(prefix="/api/report", tags=["HM Summary Report V600"])


def _safe_float(x: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _fmt(x: Any) -> str:
    if x is None:
        return "N/A"
    if isinstance(x, bool):
        return str(x)
    try:
        f = float(x)
        if abs(f - int(f)) < 1e-12:
            return str(int(f))
        return f"{f:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return escape(str(x))


def _quality(score: Any) -> str:
    s = _safe_float(score)
    if s is None:
        return "N/A"
    if s >= 90:
        return "Good"
    if s >= 70:
        return "Fair"
    if s >= 50:
        return "Weak"
    return "Poor"


def _score_color(score: Any) -> str:
    s = _safe_float(score)
    if s is None:
        return "#64748b"
    if s >= 90:
        return "#16a34a"
    if s >= 70:
        return "#84cc16"
    if s >= 50:
        return "#f59e0b"
    return "#ef4444"


def _risk_color(score: Any) -> str:
    # For mismatch severity: higher is worse.
    s = _safe_float(score)
    if s is None:
        return "#64748b"
    if s >= 70:
        return "#ef4444"
    if s >= 40:
        return "#f59e0b"
    return "#16a34a"


def _load_evidence() -> List[Dict[str, Any]]:
    try:
        from app.universal_reservoir_orchestrator_v500 import (
            _v514_get_all_diag_wells,
            _v514_evidence_for_well,
        )
    except Exception:
        return []

    rows: List[Dict[str, Any]] = []

    try:
        raw_wells = _v514_get_all_diag_wells()
    except Exception:
        raw_wells = []

    for raw in raw_wells:
        if not isinstance(raw, dict):
            continue
        try:
            e = _v514_evidence_for_well(raw)
        except Exception:
            e = raw

        if not isinstance(e, dict) or not e.get("well"):
            continue

        water_score = _safe_float(e.get("water_score"))
        bhp_score = _safe_float(e.get("bhp_score"))
        gas_score = _safe_float(e.get("gas_score"))
        oil_score = _safe_float(e.get("oil_score"))
        overall = _safe_float(e.get("overall_score"))

        e["water_mismatch"] = max(0.0, 100.0 - water_score) if water_score is not None else None
        e["bhp_mismatch"] = max(0.0, 100.0 - bhp_score) if bhp_score is not None else None
        e["gas_mismatch"] = max(0.0, 100.0 - gas_score) if gas_score is not None else None
        e["oil_mismatch"] = max(0.0, 100.0 - oil_score) if oil_score is not None else None
        e["overall_score"] = overall

        rows.append(e)

    return rows


def _avg(rows: List[Dict[str, Any]], key: str) -> Optional[float]:
    vals = [_safe_float(r.get(key)) for r in rows]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _count_quality(rows: List[Dict[str, Any]], key: str) -> Dict[str, int]:
    out = {"Good": 0, "Fair": 0, "Weak": 0, "Poor": 0, "N/A": 0}
    for r in rows:
        out[_quality(r.get(key))] = out.get(_quality(r.get(key)), 0) + 1
    return out


def _table(headers: List[str], rows: List[Dict[str, Any]], cls: str = "") -> str:
    th = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = []

    for r in rows:
        tds = []
        for h in headers:
            val = r.get(h)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                val = _fmt(val)
            elif val is None:
                val = "N/A"
            else:
                val = escape(str(val))
            tds.append(f"<td>{val}</td>")
        body.append("<tr>" + "".join(tds) + "</tr>")

    return f"""
    <table class="data-table {cls}">
      <thead><tr>{th}</tr></thead>
      <tbody>{''.join(body)}</tbody>
    </table>
    """


def _well_map_svg(rows: List[Dict[str, Any]], score_key: str, title: str, subtitle: str = "") -> str:
    pts = []

    for r in rows:
        i = _safe_float(r.get("i"))
        j = _safe_float(r.get("j"))
        if i is None or j is None:
            continue
        pts.append((r, i, j))

    if not pts:
        return f"""
        <div class="map-card">
          <h3>{escape(title)}</h3>
          <p class="muted">No I/J coordinate data available for this map.</p>
        </div>
        """

    min_i = min(p[1] for p in pts)
    max_i = max(p[1] for p in pts)
    min_j = min(p[2] for p in pts)
    max_j = max(p[2] for p in pts)

    ri = max(max_i - min_i, 1.0)
    rj = max(max_j - min_j, 1.0)

    width = 720
    height = 440
    pad = 46

    circles = []

    for r, i, j in pts:
        x = pad + (i - min_i) / ri * (width - 2 * pad)
        # Invert Y so lower J is visually lower.
        y = height - pad - (j - min_j) / rj * (height - 2 * pad)

        score = r.get(score_key)
        color = _score_color(score)

        label = escape(str(r.get("well") or ""))
        tooltip = (
            f"{label} | {score_key}: {_fmt(score)} | "
            f"Water: {_fmt(r.get('water_score'))} | "
            f"BHP: {_fmt(r.get('bhp_score'))} | "
            f"TRAN pct: {_fmt(r.get('tran_percentile'))}"
        )

        circles.append(f"""
        <g>
          <title>{escape(tooltip)}</title>
          <circle cx="{x:.2f}" cy="{y:.2f}" r="11" fill="{color}" stroke="#ffffff" stroke-width="2"/>
          <text x="{x:.2f}" y="{y - 16:.2f}" text-anchor="middle" class="well-label">{label}</text>
        </g>
        """)

    return f"""
    <div class="map-card">
      <div class="section-title-row">
        <div>
          <h3>{escape(title)}</h3>
          <p class="muted">{escape(subtitle)}</p>
        </div>
        <div class="legend">
          <span><i style="background:#16a34a"></i>Good</span>
          <span><i style="background:#84cc16"></i>Fair</span>
          <span><i style="background:#f59e0b"></i>Weak</span>
          <span><i style="background:#ef4444"></i>Poor</span>
        </div>
      </div>
      <svg viewBox="0 0 {width} {height}" class="well-map" role="img">
        <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#08111f"/>
        <line x1="{pad}" y1="{height - pad}" x2="{width - pad}" y2="{height - pad}" stroke="#334155" stroke-width="1"/>
        <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height - pad}" stroke="#334155" stroke-width="1"/>
        <text x="{width/2:.2f}" y="{height - 12}" text-anchor="middle" class="axis-label">I index</text>
        <text x="16" y="{height/2:.2f}" transform="rotate(-90 16 {height/2:.2f})" text-anchor="middle" class="axis-label">J index</text>
        {''.join(circles)}
      </svg>
    </div>
    """


def _kpi_card(title: str, value: Any, caption: str, quality_score: Any = None) -> str:
    color = _score_color(quality_score if quality_score is not None else value)
    return f"""
    <div class="kpi-card" style="border-top-color:{color}">
      <div class="kpi-title">{escape(title)}</div>
      <div class="kpi-value">{_fmt(value)}</div>
      <div class="kpi-caption">{escape(caption)}</div>
    </div>
    """


def _build_model(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    overall_avg = _avg(rows, "overall_score")
    oil_avg = _avg(rows, "oil_score")
    water_avg = _avg(rows, "water_score")
    gas_avg = _avg(rows, "gas_score")
    bhp_avg = _avg(rows, "bhp_score")

    weak_water = sorted(
        rows,
        key=lambda r: _safe_float(r.get("water_score"), 9999.0),
    )[:5]

    weak_bhp = sorted(
        rows,
        key=lambda r: _safe_float(r.get("bhp_score"), 9999.0),
    )[:5]

    review_rows = []
    for r in rows:
        water_mis = _safe_float(r.get("water_mismatch"), 0.0) or 0.0
        bhp_mis = _safe_float(r.get("bhp_mismatch"), 0.0) or 0.0
        gas_mis = _safe_float(r.get("gas_mismatch"), 0.0) or 0.0
        oil_mis = _safe_float(r.get("oil_mismatch"), 0.0) or 0.0
        review = 0.35 * water_mis + 0.30 * bhp_mis + 0.20 * gas_mis + 0.15 * oil_mis
        review_rows.append((review, r))

    top_review = [r for _, r in sorted(review_rows, key=lambda x: x[0], reverse=True)[:5]]

    direction_counts: Dict[str, int] = {}
    for r in rows:
        d = str(r.get("water_direction") or "unknown")
        direction_counts[d] = direction_counts.get(d, 0) + 1

    return {
        "overall_avg": overall_avg,
        "oil_avg": oil_avg,
        "water_avg": water_avg,
        "gas_avg": gas_avg,
        "bhp_avg": bhp_avg,
        "weak_water": weak_water,
        "weak_bhp": weak_bhp,
        "top_review": top_review,
        "direction_counts": direction_counts,
        "quality_counts": {
            "overall": _count_quality(rows, "overall_score"),
            "water": _count_quality(rows, "water_score"),
            "bhp": _count_quality(rows, "bhp_score"),
        },
    }


def build_hm_summary_html() -> str:
    rows = _load_evidence()
    model = _build_model(rows)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not rows:
        return """
        <html><body><h1>History Match Diagnostic Summary Report</h1>
        <p>No diagnostic data available.</p></body></html>
        """

    phase_rows = [
        {
            "Area": "Overall",
            "Average score": model["overall_avg"],
            "Quality": _quality(model["overall_avg"]),
            "Executive interpretation": "Usable model, but water and pressure need focused calibration.",
        },
        {
            "Area": "Oil",
            "Average score": model["oil_avg"],
            "Quality": _quality(model["oil_avg"]),
            "Executive interpretation": "Oil production match is robust across the analysed wells.",
        },
        {
            "Area": "Gas/GOR",
            "Average score": model["gas_avg"],
            "Quality": _quality(model["gas_avg"]),
            "Executive interpretation": "Gas match is generally strong and not the primary mismatch driver.",
        },
        {
            "Area": "Water/WCT",
            "Average score": model["water_avg"],
            "Quality": _quality(model["water_avg"]),
            "Executive interpretation": "Water/WCT is the weakest dimension and drives most calibration risk.",
        },
        {
            "Area": "BHP/Pressure",
            "Average score": model["bhp_avg"],
            "Quality": _quality(model["bhp_avg"]),
            "Executive interpretation": "Pressure match is secondary concern; review connectivity/support/constraints.",
        },
    ]

    weak_water_rows = []
    for r in model["weak_water"]:
        weak_water_rows.append({
            "Well": r.get("well"),
            "Water score": r.get("water_score"),
            "Direction": r.get("water_direction"),
            "Timing": r.get("water_timing"),
            "Oil": r.get("oil_score"),
            "Gas": r.get("gas_score"),
            "BHP": r.get("bhp_score"),
            "TRAN pct": r.get("tran_percentile"),
            "PERM pct": r.get("perm_percentile"),
            "WCT bias": r.get("wct_bias"),
        })

    weak_bhp_rows = []
    for r in model["weak_bhp"]:
        weak_bhp_rows.append({
            "Well": r.get("well"),
            "BHP score": r.get("bhp_score"),
            "Pressure delta": r.get("delta_pressure"),
            "Water score": r.get("water_score"),
            "Gas score": r.get("gas_score"),
            "TRAN pct": r.get("tran_percentile"),
            "Interpretation": "Review pressure support, connectivity, controls or boundary assumptions.",
        })

    top_review_rows = []
    for r in model["top_review"]:
        top_review_rows.append({
            "Well": r.get("well"),
            "Overall": r.get("overall_score"),
            "Oil": r.get("oil_score"),
            "Water": r.get("water_score"),
            "Gas": r.get("gas_score"),
            "BHP": r.get("bhp_score"),
            "Main concern": (
                "Water/WCT" if (_safe_float(r.get("water_score"), 999) or 999) < 70
                else "Pressure/BHP" if (_safe_float(r.get("bhp_score"), 999) or 999) < 70
                else "Review"
            ),
            "Recommended review": "Integrated review of profiles, TRAN/PERM/SWAT, pressure and relperm endpoints.",
        })

    direction_text = ", ".join([f"{k}: {v}" for k, v in model["direction_counts"].items()])

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>History Match Diagnostic Summary Report</title>
<style>
  @page {{
    size: A4;
    margin: 10mm 10mm 12mm 10mm;
  }}

  * {{
    box-sizing: border-box;
  }}

  body {{
    margin: 0;
    font-family: Inter, Segoe UI, Arial, sans-serif;
    background: #eef3f8;
    color: #0f172a;
  }}

  .page {{
    page-break-after: always;
    min-height: 1120px;
    background: #f8fafc;
    padding: 34px 38px;
    position: relative;
  }}

  .cover {{
    background:
      radial-gradient(circle at top right, rgba(56,189,248,0.28), transparent 38%),
      linear-gradient(135deg, #07111f 0%, #0f172a 54%, #1e293b 100%);
    color: white;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }}

  .brand-pill {{
    display: inline-block;
    padding: 8px 14px;
    border: 1px solid rgba(255,255,255,0.24);
    border-radius: 999px;
    background: rgba(255,255,255,0.08);
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    font-size: 12px;
  }}

  .cover h1 {{
    margin: 90px 0 18px 0;
    font-size: 48px;
    line-height: 1.02;
    letter-spacing: -0.04em;
  }}

  .cover .subtitle {{
    max-width: 720px;
    font-size: 18px;
    color: #cbd5e1;
    line-height: 1.55;
  }}

  .cover-grid {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-top: 44px;
  }}

  .cover-card {{
    border: 1px solid rgba(255,255,255,0.14);
    background: rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 18px;
  }}

  .cover-card .label {{
    color: #94a3b8;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  .cover-card .value {{
    font-size: 28px;
    font-weight: 800;
    margin-top: 8px;
  }}

  h2 {{
    margin: 0 0 14px 0;
    font-size: 27px;
    letter-spacing: -0.025em;
  }}

  h3 {{
    margin: 0 0 8px 0;
    font-size: 17px;
  }}

  .muted {{
    color: #64748b;
    margin: 0;
    font-size: 12px;
  }}

  .section-head {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
    padding-bottom: 14px;
    border-bottom: 1px solid #dbe4ee;
  }}

  .section-kicker {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #2563eb;
    font-weight: 800;
    margin-bottom: 6px;
  }}

  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    margin: 18px 0 20px 0;
  }}

  .kpi-card {{
    background: white;
    border-radius: 16px;
    border: 1px solid #dbe4ee;
    border-top: 5px solid #2563eb;
    padding: 15px;
    box-shadow: 0 10px 28px rgba(15,23,42,0.06);
  }}

  .kpi-title {{
    color: #64748b;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 800;
  }}

  .kpi-value {{
    margin-top: 8px;
    font-size: 28px;
    font-weight: 850;
    letter-spacing: -0.03em;
  }}

  .kpi-caption {{
    margin-top: 5px;
    color: #64748b;
    font-size: 11px;
    line-height: 1.35;
  }}

  .insight-box {{
    background: white;
    border: 1px solid #dbe4ee;
    border-radius: 18px;
    padding: 18px 20px;
    box-shadow: 0 10px 28px rgba(15,23,42,0.05);
    margin: 16px 0;
  }}

  .insight-box p {{
    margin: 0;
    line-height: 1.55;
  }}

  .data-table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 10.5px;
    background: white;
    border: 1px solid #dbe4ee;
    border-radius: 14px;
    overflow: hidden;
    margin: 12px 0 18px 0;
  }}

  .data-table th {{
    background: #0f172a;
    color: white;
    padding: 9px 8px;
    text-align: left;
    font-weight: 800;
  }}

  .data-table td {{
    padding: 8px;
    border-top: 1px solid #e2e8f0;
    vertical-align: top;
  }}

  .data-table tr:nth-child(even) td {{
    background: #f8fafc;
  }}

  .map-card {{
    background: white;
    border: 1px solid #dbe4ee;
    border-radius: 20px;
    padding: 18px;
    margin-bottom: 20px;
    box-shadow: 0 10px 28px rgba(15,23,42,0.05);
  }}

  .well-map {{
    width: 100%;
    height: auto;
    display: block;
    margin-top: 12px;
  }}

  .well-label {{
    fill: #e2e8f0;
    font-size: 11px;
    font-weight: 800;
  }}

  .axis-label {{
    fill: #94a3b8;
    font-size: 11px;
    font-weight: 700;
  }}

  .section-title-row {{
    display: flex;
    justify-content: space-between;
    gap: 18px;
    align-items: flex-start;
  }}

  .legend {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    font-size: 10px;
    color: #475569;
  }}

  .legend span {{
    display: flex;
    align-items: center;
    gap: 5px;
  }}

  .legend i {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 99px;
  }}

  .two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }}

  .callout {{
    padding: 15px 16px;
    border-radius: 16px;
    background: #eff6ff;
    border: 1px solid #bfdbfe;
    color: #1e3a8a;
    line-height: 1.5;
    font-size: 13px;
  }}

  .recommend-list {{
    margin: 12px 0 0 0;
    padding-left: 18px;
    line-height: 1.55;
  }}

  .footer {{
    position: absolute;
    bottom: 16px;
    left: 38px;
    right: 38px;
    color: #94a3b8;
    font-size: 10px;
    display: flex;
    justify-content: space-between;
    border-top: 1px solid #e2e8f0;
    padding-top: 8px;
  }}
</style>
</head>
<body>

<section class="page cover">
  <div>
    <span class="brand-pill">Reservoir AI Diagnostic Report</span>
    <h1>History Match<br/>Diagnostic Summary</h1>
    <p class="subtitle">
      Executive and technical overview of history-match quality, key mismatch drivers,
      spatial diagnostic patterns and recommended model-review actions.
    </p>

    <div class="cover-grid">
      <div class="cover-card"><div class="label">Wells analysed</div><div class="value">{len(rows)}</div></div>
      <div class="cover-card"><div class="label">Overall score</div><div class="value">{_fmt(model["overall_avg"])}</div></div>
      <div class="cover-card"><div class="label">Water score</div><div class="value">{_fmt(model["water_avg"])}</div></div>
      <div class="cover-card"><div class="label">Pressure score</div><div class="value">{_fmt(model["bhp_avg"])}</div></div>
    </div>
  </div>

  <div>
    <p class="subtitle">
      Generated {escape(now)}. Report based on current diagnostic payload, profile evidence
      and spatial property/connectivity indicators available to the Reservoir AI workflow.
    </p>
  </div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="section-kicker">01 - Executive Summary</div>
      <h2>History-match quality overview</h2>
      <p class="muted">High-level readout for model review and prioritisation.</p>
    </div>
    <div class="muted">Generated {escape(now)}</div>
  </div>

  <div class="kpi-grid">
    {_kpi_card("Overall HM", model["overall_avg"], "Average overall score", model["overall_avg"])}
    {_kpi_card("Oil", model["oil_avg"], "Hydrocarbon liquid match", model["oil_avg"])}
    {_kpi_card("Gas/GOR", model["gas_avg"], "Gas behaviour match", model["gas_avg"])}
    {_kpi_card("Water/WCT", model["water_avg"], "Main calibration risk", model["water_avg"])}
    {_kpi_card("BHP", model["bhp_avg"], "Pressure match quality", model["bhp_avg"])}
  </div>

  <div class="insight-box">
    <p>
      <b>Executive readout.</b>
      The model is generally strong for oil and gas, while water/WCT and BHP/pressure remain the main calibration risks.
      Water behaviour should be reviewed jointly with pressure, TRAN/PERM/SWAT evidence and relperm/end-point assumptions.
      Water direction evidence: {escape(direction_text)}.
    </p>
  </div>

  {_table(["Area", "Average score", "Quality", "Executive interpretation"], phase_rows)}

  <div class="two-col">
    <div class="callout">
      <b>Main technical risk.</b><br/>
      Water movement and pressure support are not fully captured by a single hypothesis.
      The strongest workflow is a combined review of local connectivity, transmissibility corridors,
      saturation movement and water relative-permeability assumptions.
    </div>
    <div class="callout">
      <b>Recommended decision use.</b><br/>
      Oil and gas forecasts are more robust than water and BHP forecasts.
      Forecast scenarios should include sensitivities on water mobility, TRAN corridors and pressure support.
    </div>
  </div>

  <div class="footer"><span>Reservoir AI HM Diagnostic Report</span><span>01</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="section-kicker">02 - Spatial Diagnostics</div>
      <h2>Well maps by match quality</h2>
      <p class="muted">Wells coloured by score. Green indicates stronger match; red indicates weaker match.</p>
    </div>
  </div>

  {_well_map_svg(rows, "overall_score", "Overall HM quality map", "Spatial overview of integrated match quality by well.")}
  {_well_map_svg(rows, "water_score", "Water / WCT match quality map", "Highlights the primary HM weakness and spatial distribution of water mismatch.")}
  <div class="footer"><span>Reservoir AI HM Diagnostic Report</span><span>02</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="section-kicker">03 - Pressure and Connectivity Context</div>
      <h2>BHP / pressure quality and model review priorities</h2>
      <p class="muted">Pressure behaviour helps distinguish relperm-only problems from connectivity/support issues.</p>
    </div>
  </div>

  {_well_map_svg(rows, "bhp_score", "BHP / pressure match quality map", "Weak pressure match can indicate support, boundary, connectivity or control issues.")}

  <h3>Top model-review wells</h3>
  {_table(["Well", "Overall", "Oil", "Water", "Gas", "BHP", "Main concern", "Recommended review"], top_review_rows)}

  <div class="footer"><span>Reservoir AI HM Diagnostic Report</span><span>03</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="section-kicker">04 - Water / WCT Diagnostic Evidence</div>
      <h2>Weakest water-match wells</h2>
      <p class="muted">Water mismatch is prioritised because it is the dominant history-match uncertainty.</p>
    </div>
  </div>

  {_table(["Well", "Water score", "Direction", "Timing", "Oil", "Gas", "BHP", "TRAN pct", "PERM pct", "WCT bias"], weak_water_rows)}

  <div class="insight-box">
    <p>
      <b>Interpretation.</b>
      Weak water wells should not be corrected using one global knob.
      Where simulated water is too high, review water mobility, water-source strength, local completion connectivity and relperm endpoints.
      Where simulated water is too low, review transmissibility corridors, barriers, water-source access and saturation movement.
    </p>
  </div>

  <h3>Weakest BHP / pressure evidence</h3>
  {_table(["Well", "BHP score", "Pressure delta", "Water score", "Gas score", "TRAN pct", "Interpretation"], weak_bhp_rows)}

  <div class="footer"><span>Reservoir AI HM Diagnostic Report</span><span>04</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="section-kicker">05 - Recommendations</div>
      <h2>Recommended model-review actions</h2>
      <p class="muted">Suggested next checks for reservoir engineer review.</p>
    </div>
  </div>

  <div class="insight-box">
    <h3>Priority actions</h3>
    <ol class="recommend-list">
      <li>Review the weakest water/WCT wells using water profiles, WCT bias map and profile-overrides where diagnostic labels conflict with numeric evidence.</li>
      <li>Check BHP/pressure mismatch before applying relperm-only changes, especially where pressure support or connectivity evidence is weak.</li>
      <li>Compare TRAN-only, relperm-only and combined sensitivities on the top model-review wells.</li>
      <li>Use beginning/end history streamlines on TRAN_H background to confirm whether water movement follows expected corridors.</li>
      <li>Keep oil/gas match as constraint while tuning water and pressure behaviour.</li>
    </ol>
  </div>

  <div class="insight-box">
    <h3>Method notes</h3>
    <p>
      This report combines well-level diagnostic scores, profile/numeric water evidence overrides,
      spatial I/J well coordinates, TRAN/PERM/PORO indicators and pressure evidence. It is intended as
      a decision-support summary for model review, not as a replacement for detailed reservoir-engineering validation.
    </p>
  </div>

  <div class="footer"><span>Reservoir AI HM Diagnostic Report</span><span>05</span></div>
</section>

</body>
</html>
"""


@router.get("/hm-summary/html", response_class=HTMLResponse)
async def hm_summary_html() -> HTMLResponse:
    return HTMLResponse(build_hm_summary_html())


@router.get("/hm-summary/pdf")
async def hm_summary_pdf() -> Response:
    html = build_hm_summary_html()

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Playwright is not installed or Chromium is missing. "
                "Run: python -m pip install playwright; python -m playwright install chromium. "
                f"Original error: {exc}"
            ),
        )

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={"width": 1240, "height": 1754})
            await page.set_content(html, wait_until="networkidle")
            pdf = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            )
            await browser.close()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    filename = f"hm_summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ==========================================================
# V600B LOCAL EDGE/CHROME PDF FALLBACK
#
# Corporate proxy/certificate may block:
#   python -m playwright install chromium
#
# This override generates PDF using installed Microsoft Edge / Chrome
# without downloading bundled Chromium.
# ==========================================================

import os
from fastapi.responses import Response
from fastapi import HTTPException
from datetime import datetime


def _v600b_existing_browser_paths():
    candidates = [
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    return [p for p in candidates if os.path.exists(p)]


async def _v600b_launch_browser(pw):
    errors = []

    # 1) Prefer channel launch. This uses installed branded browsers when available.
    for channel in ["msedge", "chrome"]:
        try:
            return await pw.chromium.launch(channel=channel, headless=True)
        except Exception as exc:
            errors.append(f"channel={channel}: {exc}")

    # 2) Fallback to explicit executable paths.
    for path in _v600b_existing_browser_paths():
        try:
            return await pw.chromium.launch(executable_path=path, headless=True)
        except Exception as exc:
            errors.append(f"executable_path={path}: {exc}")

    raise RuntimeError(
        "Could not launch local Edge/Chrome. Tried msedge/chrome channels and common executable paths. "
        + " | ".join(errors[-4:])
    )


@router.get("/hm-summary/pdf-local")
async def hm_summary_pdf_local_v600b() -> Response:
    html = build_hm_summary_html()

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Playwright Python package is not installed. Run: python -m pip install playwright. "
                "Do NOT run playwright install chromium if your corporate certificate blocks it. "
                f"Original error: {exc}"
            ),
        )

    try:
        async with async_playwright() as p:
            browser = await _v600b_launch_browser(p)
            page = await browser.new_page(viewport={"width": 1240, "height": 1754})
            await page.set_content(html, wait_until="networkidle")
            pdf = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            )
            await browser.close()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "PDF generation with local Edge/Chrome failed. "
                "Check that Microsoft Edge or Chrome is installed and can be launched by Playwright. "
                f"Original error: {exc}"
            ),
        )

    filename = f"hm_summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# Override original PDF endpoint as well, so /pdf uses local browser fallback.
@router.get("/hm-summary/pdf-v600b")
async def hm_summary_pdf_v600b() -> Response:
    return await hm_summary_pdf_local_v600b()

# END V600B LOCAL EDGE/CHROME PDF FALLBACK


# ==========================================================
# V600C_HTML REAL HTML REPORT UPGRADE
#
# This overrides build_hm_summary_html() used by:
# - /api/report/hm-summary/html
# - /api/report/hm-summary/pdf-local
#
# Adds:
# - Dashboard-like map orientation: X = J, Y = -I
# - Inactive wells on maps as grey hollow points
# - Compact report layout
# - Area analysis by spatial quadrant
# - Critical well mini profile plots as inline SVG
# - Dedicated V600C preview/PDF routes
# ==========================================================

from pathlib import Path as _PathV600C
from datetime import datetime as _datetimeV600C
from fastapi.responses import HTMLResponse as _HTMLResponseV600C, Response as _ResponseV600C
from fastapi import HTTPException as _HTTPExceptionV600C
import math as _mathV600C
import os as _osV600C


def _v600c_num(x, default=None):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _v600c_fmt(x):
    try:
        if x is None:
            return "N/A"
        f = float(x)
        if not _mathV600C.isfinite(f):
            return "N/A"
        if abs(f - int(f)) < 1e-12:
            return str(int(f))
        return f"{f:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return escape(str(x))


def _v600c_quality(score):
    s = _v600c_num(score)
    if s is None:
        return "N/A"
    if s >= 90:
        return "Good"
    if s >= 70:
        return "Fair"
    if s >= 50:
        return "Weak"
    return "Poor"


def _v600c_score_color(score):
    s = _v600c_num(score)
    if s is None:
        return "#64748b"
    if s >= 90:
        return "#16a34a"
    if s >= 70:
        return "#84cc16"
    if s >= 50:
        return "#f59e0b"
    return "#ef4444"


def _v600c_inactive_color():
    return "#94a3b8"


def _v600c_table(headers, rows, cls=""):
    th = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = []
        for h in headers:
            v = r.get(h) if isinstance(r, dict) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                txt = _v600c_fmt(v)
            elif v is None:
                txt = "N/A"
            else:
                txt = escape(str(v))
            tds.append(f"<td>{txt}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f"""
    <table class="data-table {cls}">
      <thead><tr>{th}</tr></thead>
      <tbody>{''.join(trs)}</tbody>
    </table>
    """


def _v600c_try_load_artifact_wells():
    """
    Load inactive/extra wells from diagnosis artifact if present.
    This complements diagnostic evidence, which may contain only HM wells.
    """
    root = _PathV600C(".")
    candidates = [
        root / "artifacts" / "diagnosis" / "well_property_driver_context.csv",
        root / "artifacts" / "well_property_driver_context.csv",
    ]

    for pth in candidates:
        if not pth.exists():
            continue
        try:
            import csv
            rows = []
            with pth.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    if not r:
                        continue
                    rows.append(r)
            if rows:
                return rows
        except Exception:
            pass
    return []


def _v600c_load_all_wells():
    """
    Merge diagnostic evidence and artifact well table.
    Diagnostic evidence gives HM scores; artifact table can add inactive wells.
    """
    diagnostic_rows = _load_evidence()
    artifact_rows = _v600c_try_load_artifact_wells()

    by_compact = {}

    def compact(w):
        import re
        return re.sub(r"[^A-Z0-9]", "", str(w or "").upper())

    def put(row, source):
        if not isinstance(row, dict):
            return
        well = row.get("well") or row.get("WELL") or row.get("Well") or row.get("name") or row.get("well_name")
        if not well:
            return
        key = compact(well)
        if not key:
            return
        existing = by_compact.get(key, {})
        merged = dict(existing)
        merged.update(row)
        merged["well"] = str(well)
        srcs = set(str(merged.get("_sources", "")).split(",")) if merged.get("_sources") else set()
        srcs.add(source)
        merged["_sources"] = ",".join(sorted(srcs))
        by_compact[key] = merged

    for r in artifact_rows:
        put(r, "artifact")

    for r in diagnostic_rows:
        put(r, "diagnostic")

    rows = list(by_compact.values())

    # Normalize coordinates and scores.
    for r in rows:
        for src, dst in [
            ("I", "i"),
            ("J", "j"),
            ("X", "i"),
            ("Y", "j"),
        ]:
            if dst not in r and src in r:
                r[dst] = r.get(src)

        for k in [
            "i", "j", "overall_score", "oil_score", "water_score", "gas_score", "bhp_score",
            "tran_percentile", "perm_percentile", "poro_percentile", "delta_pressure",
        ]:
            if k in r:
                r[k] = _v600c_num(r.get(k))

        # Active/inactive detection.
        active = True
        for k in ["active_producer", "active", "is_active", "producer_active"]:
            if k in r:
                val = str(r.get(k)).strip().lower()
                if val in {"false", "0", "no", "n", "inactive"}:
                    active = False
                elif val in {"true", "1", "yes", "y", "active"}:
                    active = True

        for k in ["exclude_from_hm", "excluded", "inactive"]:
            if k in r:
                val = str(r.get(k)).strip().lower()
                if val in {"true", "1", "yes", "y"}:
                    active = False

        # If no diagnostic source and no scores, treat as inactive/context well.
        if "diagnostic" not in str(r.get("_sources", "")):
            active = False

        r["is_active_well_v600c"] = active

        water = _v600c_num(r.get("water_score"))
        bhp = _v600c_num(r.get("bhp_score"))
        gas = _v600c_num(r.get("gas_score"))
        oil = _v600c_num(r.get("oil_score"))

        r["water_mismatch"] = max(0, 100 - water) if water is not None else None
        r["bhp_mismatch"] = max(0, 100 - bhp) if bhp is not None else None
        r["gas_mismatch"] = max(0, 100 - gas) if gas is not None else None
        r["oil_mismatch"] = max(0, 100 - oil) if oil is not None else None

    return rows


def _v600c_avg(rows, key, active_only=True):
    vals = []
    for r in rows:
        if active_only and not r.get("is_active_well_v600c", True):
            continue
        v = _v600c_num(r.get(key))
        if v is not None:
            vals.append(v)
    return sum(vals) / len(vals) if vals else None


def _v600c_kpi_card(title, value, caption, score=None):
    color = _v600c_score_color(score if score is not None else value)
    return f"""
    <div class="kpi-card" style="border-top-color:{color}">
      <div class="kpi-title">{escape(title)}</div>
      <div class="kpi-value">{_v600c_fmt(value)}</div>
      <div class="kpi-caption">{escape(caption)}</div>
    </div>
    """


def _v600c_dashboard_xy(row):
    """
    Match dashboard-style orientation:
    X = J
    Y = -I
    """
    i = _v600c_num(row.get("i"))
    j = _v600c_num(row.get("j"))
    if i is None or j is None:
        return None, None
    return j, -i


def _v600c_map_svg(rows, score_key, title, comment, compact=True, highlight_wells=None):
    highlight_wells = set(highlight_wells or [])
    pts = []
    for r in rows:
        x, y = _v600c_dashboard_xy(r)
        if x is None or y is None:
            continue
        pts.append((r, x, y))

    if not pts:
        return f"""
        <div class="panel">
          <h3>{escape(title)}</h3>
          <p class="muted">No I/J coordinates found.</p>
        </div>
        """

    minx = min(p[1] for p in pts)
    maxx = max(p[1] for p in pts)
    miny = min(p[2] for p in pts)
    maxy = max(p[2] for p in pts)
    rx = max(maxx - minx, 1)
    ry = max(maxy - miny, 1)

    width = 560 if compact else 720
    height = 330 if compact else 430
    pad = 35

    circles = []
    for r, x0, y0 in pts:
        x = pad + (x0 - minx) / rx * (width - 2 * pad)
        y = height - pad - (y0 - miny) / ry * (height - 2 * pad)

        well = str(r.get("well") or "")
        active = bool(r.get("is_active_well_v600c", True))
        score = r.get(score_key)

        fill = _v600c_score_color(score) if active else "none"
        stroke = "#ffffff" if active else _v600c_inactive_color()
        radius = 9 if active else 7
        dash = "" if active else 'stroke-dasharray="3 3"'
        opacity = "0.96" if active else "0.72"

        label_color = "#e2e8f0" if active else "#94a3b8"
        is_highlight = well in highlight_wells

        tooltip = (
            f"{well} | active={active} | {score_key}={_v600c_fmt(score)} | "
            f"Water={_v600c_fmt(r.get('water_score'))} | BHP={_v600c_fmt(r.get('bhp_score'))} | "
            f"TRAN={_v600c_fmt(r.get('tran_percentile'))}"
        )

        circles.append(f"""
        <g opacity="{opacity}">
          <title>{escape(tooltip)}</title>
          <circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{3 if is_highlight else 1.8}" {dash}/>
          <text x="{x + 10:.2f}" y="{y - 7:.2f}" class="well-label" fill="{label_color}">{escape(well)}</text>
        </g>
        """)

    return f"""
    <div class="panel map-panel">
      <div class="panel-head">
        <div>
          <h3>{escape(title)}</h3>
          <p class="muted">{escape(comment)}</p>
        </div>
        <div class="legend small">
          <span><i style="background:#16a34a"></i>Good</span>
          <span><i style="background:#84cc16"></i>Fair</span>
          <span><i style="background:#f59e0b"></i>Weak</span>
          <span><i style="background:#ef4444"></i>Poor</span>
          <span><i class="hollow"></i>Inactive/context</span>
        </div>
      </div>
      <svg viewBox="0 0 {width} {height}" class="well-map">
        <rect x="0" y="0" width="{width}" height="{height}" rx="18" fill="#08111f"/>
        <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#334155" stroke-width="1"/>
        <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#334155" stroke-width="1"/>
        <text x="{width/2:.2f}" y="{height-8}" class="axis-label" text-anchor="middle">J index</text>
        <text x="11" y="{height/2:.2f}" class="axis-label" transform="rotate(-90 11 {height/2:.2f})" text-anchor="middle">-I index</text>
        {''.join(circles)}
      </svg>
    </div>
    """


def _v600c_profile_data(well, variable):
    try:
        from app.universal_reservoir_orchestrator_v500 import _v510_get_profile_data
        d = _v510_get_profile_data(well, variable)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def _v600c_numeric_list(vals, nmax=None):
    out = []
    for v in vals or []:
        f = _v600c_num(v)
        if f is not None:
            out.append(f)
    if nmax and len(out) > nmax:
        step = max(1, int(len(out) / nmax))
        out = out[::step]
    return out


def _v600c_mini_profile_svg(well, variable, title):
    d = _v600c_profile_data(well, variable)
    sim = _v600c_numeric_list(d.get("simulated") or d.get("sim") or d.get("simulation") or [], nmax=90)
    obs = _v600c_numeric_list(d.get("observed") or d.get("obs") or d.get("history") or [], nmax=90)

    if not sim and not obs:
        return f"""
        <div class="mini-plot empty">
          <div class="mini-title">{escape(title)}</div>
          <div class="muted">No profile arrays available.</div>
        </div>
        """

    width, height = 310, 130
    pad_l, pad_r, pad_t, pad_b = 28, 10, 16, 24

    allv = sim + obs
    ymin = min(allv)
    ymax = max(allv)
    if abs(ymax - ymin) < 1e-12:
        ymax = ymin + 1

    n = max(len(sim), len(obs), 2)

    def xy(vals):
        pts = []
        for idx, val in enumerate(vals):
            x = pad_l + idx / max(len(vals)-1, 1) * (width - pad_l - pad_r)
            y = height - pad_b - (val - ymin) / (ymax - ymin) * (height - pad_t - pad_b)
            pts.append(f"{x:.2f},{y:.2f}")
        return " ".join(pts)

    sim_line = f'<polyline points="{xy(sim)}" fill="none" stroke="#38bdf8" stroke-width="2.2"/>' if sim else ""
    obs_line = f'<polyline points="{xy(obs)}" fill="none" stroke="#f97316" stroke-width="2.2"/>' if obs else ""

    return f"""
    <div class="mini-plot">
      <div class="mini-title">{escape(title)}</div>
      <svg viewBox="0 0 {width} {height}" class="mini-svg">
        <rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#08111f"/>
        <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#334155"/>
        <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#334155"/>
        {sim_line}
        {obs_line}
        <text x="{pad_l}" y="12" class="mini-axis">max {_v600c_fmt(ymax)}</text>
        <text x="{pad_l}" y="{height-5}" class="mini-axis">min {_v600c_fmt(ymin)}</text>
        <text x="{width-116}" y="14" class="mini-axis"><tspan fill="#38bdf8">sim</tspan> / <tspan fill="#f97316">obs</tspan></text>
      </svg>
    </div>
    """


def _v600c_critical_variable(row):
    scores = {
        "water": _v600c_num(row.get("water_score")),
        "bhp": _v600c_num(row.get("bhp_score")),
        "gas": _v600c_num(row.get("gas_score")),
        "oil": _v600c_num(row.get("oil_score")),
    }
    scores = {k: v for k, v in scores.items() if v is not None}
    if not scores:
        return "water"
    return min(scores, key=scores.get)


def _v600c_area_analysis(rows):
    pts = []
    for r in rows:
        x, y = _v600c_dashboard_xy(r)
        if x is not None and y is not None:
            pts.append((r, x, y))

    if not pts:
        return [], "<p class='muted'>No spatial coordinates available for area analysis.</p>"

    xs = [p[1] for p in pts]
    ys = [p[2] for p in pts]
    xmed = sorted(xs)[len(xs)//2]
    ymed = sorted(ys)[len(ys)//2]

    def area(x, y):
        ns = "N" if y >= ymed else "S"
        ew = "E" if x >= xmed else "W"
        return ns + ew

    grouped = {}
    for r, x, y in pts:
        a = area(x, y)
        grouped.setdefault(a, []).append(r)

    area_rows = []
    comments = []
    for a in ["NW", "NE", "SW", "SE"]:
        g = grouped.get(a, [])
        if not g:
            continue
        avg_overall = _v600c_avg(g, "overall_score", active_only=False)
        avg_water = _v600c_avg(g, "water_score", active_only=False)
        avg_bhp = _v600c_avg(g, "bhp_score", active_only=False)
        avg_tran = _v600c_avg(g, "tran_percentile", active_only=False)
        active_count = sum(1 for r in g if r.get("is_active_well_v600c", True))

        values = {
            "Water/WCT": avg_water,
            "BHP/Pressure": avg_bhp,
            "Overall": avg_overall,
        }
        weak = min({k: v for k, v in values.items() if v is not None}.items(), key=lambda x: x[1])[0] if any(v is not None for v in values.values()) else "N/A"

        if weak == "Water/WCT":
            driver = "water movement, relperm/endpoints or water connectivity"
        elif weak == "BHP/Pressure":
            driver = "pressure support, connectivity or constraints"
        else:
            driver = "mixed HM quality"

        area_rows.append({
            "Area": a,
            "Wells": len(g),
            "Active HM wells": active_count,
            "Overall avg": avg_overall,
            "Water avg": avg_water,
            "BHP avg": avg_bhp,
            "TRAN avg": avg_tran,
            "Dominant issue": weak,
            "Likely driver": driver,
        })

        comments.append(
            f"<li><b>{a}</b>: {len(g)} wells ({active_count} active HM wells). "
            f"Dominant issue: {escape(weak)}; likely driver: {escape(driver)}.</li>"
        )

    return area_rows, "<ul class='area-comments'>" + "".join(comments) + "</ul>"


def _v600c_build_critical_cards(rows):
    active_rows = [r for r in rows if r.get("is_active_well_v600c", True)]
    if not active_rows:
        active_rows = rows

    scored = []
    for r in active_rows:
        wm = _v600c_num(r.get("water_mismatch"), 0) or 0
        bm = _v600c_num(r.get("bhp_mismatch"), 0) or 0
        gm = _v600c_num(r.get("gas_mismatch"), 0) or 0
        om = _v600c_num(r.get("oil_mismatch"), 0) or 0
        priority = 0.38 * wm + 0.30 * bm + 0.18 * gm + 0.14 * om
        scored.append((priority, r))

    top = [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)[:4]]

    cards = []
    for r in top:
        well = str(r.get("well") or "")
        var = _v600c_critical_variable(r)
        score = r.get(f"{var}_score")
        direction = r.get(f"{var}_direction") or r.get("water_direction") or ""
        timing = r.get(f"{var}_timing") or r.get("water_timing") or ""
        plot_var = "water" if var == "water" else ("bhp" if var == "bhp" else var)

        interp = ""
        if var == "water":
            interp = "Water/WCT is the main mismatch driver. Review water mobility, source connection, relperm endpoints and local TRAN/PERM context."
        elif var == "bhp":
            interp = "Pressure/BHP mismatch is dominant. Review pressure support, connectivity, boundary conditions and well controls."
        elif var == "gas":
            interp = "Gas/GOR mismatch is dominant. Review gas allocation, GOR behaviour and local pressure coupling."
        else:
            interp = "Oil mismatch is dominant. Review rate allocation, controls and local productivity assumptions."

        cards.append(f"""
        <div class="critical-card">
          <div class="critical-head">
            <div>
              <h3>{escape(well)}</h3>
              <p class="muted">Main issue: {escape(var.upper())} | score {_v600c_fmt(score)}</p>
            </div>
            <span class="badge" style="background:{_v600c_score_color(score)}">{escape(_v600c_quality(score))}</span>
          </div>
          {_v600c_mini_profile_svg(well, plot_var, f"{well} {plot_var.upper()} sim vs obs")}
          <p class="critical-text">
            {escape(interp)}
            {(" Direction: " + escape(str(direction)) + ".") if direction else ""}
            {(" Timing: " + escape(str(timing)) + ".") if timing else ""}
          </p>
        </div>
        """)

    return "".join(cards), [str(r.get("well") or "") for r in top]


def build_hm_summary_html() -> str:
    rows = _v600c_load_all_wells()
    now = _datetimeV600C.now().strftime("%Y-%m-%d %H:%M")
    version = "V600C_HTML"

    if not rows:
        return f"""
        <html><body><h1>History Match Diagnostic Summary Report</h1>
        <p>No diagnostic/well data available.</p><p>{version}</p></body></html>
        """

    active_rows = [r for r in rows if r.get("is_active_well_v600c", True)]
    inactive_rows = [r for r in rows if not r.get("is_active_well_v600c", True)]

    overall_avg = _v600c_avg(rows, "overall_score")
    oil_avg = _v600c_avg(rows, "oil_score")
    water_avg = _v600c_avg(rows, "water_score")
    gas_avg = _v600c_avg(rows, "gas_score")
    bhp_avg = _v600c_avg(rows, "bhp_score")

    phase_rows = [
        {"Area": "Overall", "Average score": overall_avg, "Quality": _v600c_quality(overall_avg), "Executive readout": "Integrated HM quality across active diagnostic wells."},
        {"Area": "Oil", "Average score": oil_avg, "Quality": _v600c_quality(oil_avg), "Executive readout": "Hydrocarbon liquid match; typically robust if score is high."},
        {"Area": "Gas/GOR", "Average score": gas_avg, "Quality": _v600c_quality(gas_avg), "Executive readout": "Gas behaviour and GOR consistency."},
        {"Area": "Water/WCT", "Average score": water_avg, "Quality": _v600c_quality(water_avg), "Executive readout": "Usually the strongest indicator of dynamic mismatch risk."},
        {"Area": "BHP/Pressure", "Average score": bhp_avg, "Quality": _v600c_quality(bhp_avg), "Executive readout": "Pressure support/connectivity/control behaviour."},
    ]

    critical_cards, critical_wells = _v600c_build_critical_cards(rows)
    area_rows, area_comments = _v600c_area_analysis(rows)

    top_review = []
    for r in active_rows:
        wm = _v600c_num(r.get("water_mismatch"), 0) or 0
        bm = _v600c_num(r.get("bhp_mismatch"), 0) or 0
        gm = _v600c_num(r.get("gas_mismatch"), 0) or 0
        om = _v600c_num(r.get("oil_mismatch"), 0) or 0
        priority = 0.38 * wm + 0.30 * bm + 0.18 * gm + 0.14 * om
        top_review.append((priority, r))

    review_rows = []
    for _, r in sorted(top_review, key=lambda x: x[0], reverse=True)[:8]:
        var = _v600c_critical_variable(r)
        review_rows.append({
            "Well": r.get("well"),
            "Overall": r.get("overall_score"),
            "Oil": r.get("oil_score"),
            "Water": r.get("water_score"),
            "Gas": r.get("gas_score"),
            "BHP": r.get("bhp_score"),
            "Main issue": var.upper(),
            "Recommended review": "Check profile, map context, TRAN/PERM/SWAT and pressure evidence.",
        })

    weak_water_rows = []
    for r in sorted(active_rows, key=lambda x: _v600c_num(x.get("water_score"), 999))[:8]:
        weak_water_rows.append({
            "Well": r.get("well"),
            "Water score": r.get("water_score"),
            "Direction": r.get("water_direction"),
            "Timing": r.get("water_timing"),
            "Oil": r.get("oil_score"),
            "Gas": r.get("gas_score"),
            "BHP": r.get("bhp_score"),
            "TRAN pct": r.get("tran_percentile"),
            "PERM pct": r.get("perm_percentile"),
        })

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>History Match Diagnostic Summary Report - {version}</title>
<style>
@page {{ size: A4; margin: 9mm; }}
* {{ box-sizing: border-box; }}
body {{
  margin:0;
  font-family: Inter, Segoe UI, Arial, sans-serif;
  background:#e8eef6;
  color:#0f172a;
}}
.page {{
  page-break-after: always;
  min-height: 1080px;
  background:#f8fafc;
  padding:28px 32px;
  position:relative;
}}
.cover {{
  background: radial-gradient(circle at top right, rgba(56,189,248,.25), transparent 35%),
              linear-gradient(135deg,#06101e,#0f172a 55%,#1e293b);
  color:white;
}}
.brand {{
  display:inline-block;
  padding:7px 12px;
  border:1px solid rgba(255,255,255,.22);
  border-radius:999px;
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.1em;
  font-weight:800;
  background:rgba(255,255,255,.08);
}}
.cover h1 {{
  font-size:46px;
  line-height:1.02;
  letter-spacing:-.04em;
  margin:72px 0 16px;
}}
.subtitle {{
  color:#cbd5e1;
  font-size:16px;
  line-height:1.5;
  max-width:760px;
}}
.version-pill {{
  display:inline-block;
  margin-top:18px;
  padding:8px 12px;
  border-radius:12px;
  background:#0ea5e9;
  color:white;
  font-weight:800;
}}
.kpi-grid {{
  display:grid;
  grid-template-columns: repeat(5, 1fr);
  gap:10px;
  margin:18px 0 16px;
}}
.kpi-card {{
  background:white;
  border:1px solid #dbe4ee;
  border-top:5px solid #2563eb;
  border-radius:15px;
  padding:13px;
  box-shadow:0 8px 20px rgba(15,23,42,.06);
}}
.kpi-title {{
  color:#64748b;
  font-size:10px;
  text-transform:uppercase;
  letter-spacing:.08em;
  font-weight:800;
}}
.kpi-value {{
  margin-top:7px;
  font-size:25px;
  font-weight:850;
}}
.kpi-caption {{
  margin-top:4px;
  color:#64748b;
  font-size:10px;
  line-height:1.25;
}}
.section-head {{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  margin-bottom:14px;
  padding-bottom:10px;
  border-bottom:1px solid #dbe4ee;
}}
.kicker {{
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.11em;
  color:#2563eb;
  font-weight:900;
  margin-bottom:4px;
}}
h2 {{
  margin:0;
  font-size:25px;
  letter-spacing:-.03em;
}}
h3 {{
  margin:0 0 7px;
  font-size:15px;
}}
.muted {{
  color:#64748b;
  margin:0;
  font-size:11px;
  line-height:1.35;
}}
.panel {{
  background:white;
  border:1px solid #dbe4ee;
  border-radius:18px;
  padding:14px;
  box-shadow:0 8px 22px rgba(15,23,42,.05);
  margin-bottom:13px;
}}
.panel.dark {{
  background:#0f172a;
  color:white;
}}
.panel-head {{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:flex-start;
}}
.two-col {{
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap:13px;
}}
.three-col {{
  display:grid;
  grid-template-columns: repeat(3, 1fr);
  gap:12px;
}}
.well-map {{
  width:100%;
  height:auto;
  display:block;
  margin-top:8px;
}}
.well-label {{
  font-size:8.5px;
  font-weight:800;
}}
.axis-label {{
  fill:#94a3b8;
  font-size:9px;
  font-weight:700;
}}
.legend {{
  display:flex;
  gap:8px;
  flex-wrap:wrap;
  color:#475569;
  font-size:9px;
}}
.legend span {{
  display:flex;
  align-items:center;
  gap:4px;
}}
.legend i {{
  display:inline-block;
  width:9px;
  height:9px;
  border-radius:99px;
}}
.legend i.hollow {{
  border:1.5px dashed #94a3b8;
  background:transparent;
}}
.data-table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  font-size:9.5px;
  background:white;
  border:1px solid #dbe4ee;
  border-radius:12px;
  overflow:hidden;
  margin:8px 0 12px;
}}
.data-table th {{
  background:#0f172a;
  color:white;
  padding:7px 6px;
  text-align:left;
  font-weight:800;
}}
.data-table td {{
  padding:6px;
  border-top:1px solid #e2e8f0;
  vertical-align:top;
}}
.data-table tr:nth-child(even) td {{
  background:#f8fafc;
}}
.critical-grid {{
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap:12px;
}}
.critical-card {{
  background:white;
  border:1px solid #dbe4ee;
  border-radius:16px;
  padding:12px;
  box-shadow:0 8px 20px rgba(15,23,42,.05);
}}
.critical-head {{
  display:flex;
  justify-content:space-between;
  gap:10px;
  align-items:flex-start;
}}
.badge {{
  color:white;
  border-radius:999px;
  padding:5px 9px;
  font-size:10px;
  font-weight:900;
}}
.critical-text {{
  font-size:10.5px;
  color:#334155;
  line-height:1.35;
  margin:8px 0 0;
}}
.mini-plot {{
  margin-top:8px;
}}
.mini-title {{
  font-size:10px;
  color:#475569;
  font-weight:800;
  margin-bottom:4px;
}}
.mini-svg {{
  width:100%;
  height:auto;
}}
.mini-axis {{
  fill:#94a3b8;
  font-size:8px;
  font-weight:700;
}}
.area-comments {{
  margin:8px 0 0;
  padding-left:17px;
  color:#334155;
  font-size:11px;
  line-height:1.45;
}}
.footer {{
  position:absolute;
  bottom:13px;
  left:32px;
  right:32px;
  color:#94a3b8;
  font-size:9px;
  display:flex;
  justify-content:space-between;
  border-top:1px solid #e2e8f0;
  padding-top:7px;
}}
</style>
</head>
<body>

<section class="page cover">
  <span class="brand">Reservoir AI Diagnostic Report</span>
  <h1>History Match<br>Diagnostic Summary</h1>
  <p class="subtitle">
    Compact executive and technical report with KPI overview, dashboard-oriented well maps,
    inactive/context wells, spatial area analysis and critical well profile evidence.
  </p>
  <span class="version-pill">{version}</span>
  <div class="kpi-grid" style="margin-top:52px;">
    {_v600c_kpi_card("Wells", len(rows), f"{len(active_rows)} active / {len(inactive_rows)} inactive", overall_avg)}
    {_v600c_kpi_card("Overall", overall_avg, "Average HM score", overall_avg)}
    {_v600c_kpi_card("Oil", oil_avg, "Oil match", oil_avg)}
    {_v600c_kpi_card("Water", water_avg, "Water/WCT match", water_avg)}
    {_v600c_kpi_card("BHP", bhp_avg, "Pressure match", bhp_avg)}
  </div>
  <p class="subtitle" style="margin-top:50px;">Generated {escape(now)}. Map orientation: X = J, Y = -I, aligned with dashboard-style spatial reading.</p>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">01 - Executive overview</div>
      <h2>HM quality and main risks</h2>
      <p class="muted">Summary based on active diagnostic wells; inactive/context wells are shown on maps only.</p>
    </div>
    <div class="muted">{version}</div>
  </div>

  <div class="kpi-grid">
    {_v600c_kpi_card("Overall", overall_avg, "Integrated score", overall_avg)}
    {_v600c_kpi_card("Oil", oil_avg, "Production match", oil_avg)}
    {_v600c_kpi_card("Gas/GOR", gas_avg, "Gas behaviour", gas_avg)}
    {_v600c_kpi_card("Water/WCT", water_avg, "Main calibration risk", water_avg)}
    {_v600c_kpi_card("BHP", bhp_avg, "Pressure quality", bhp_avg)}
  </div>

  <div class="two-col">
    <div class="panel">
      <h3>Executive interpretation</h3>
      <p class="muted">
        Oil and gas quality are interpreted as constraints, while water/WCT and pressure are the primary calibration-risk dimensions.
        Critical wells are selected using combined water, BHP, gas and oil mismatch severity.
      </p>
    </div>
    <div class="panel">
      <h3>Report reading guide</h3>
      <p class="muted">
        Maps use dashboard orientation: X = J and Y = -I. Filled coloured wells are active HM wells.
        Hollow grey wells are inactive/context wells included for spatial reference.
      </p>
    </div>
  </div>

  {_v600c_table(["Area", "Average score", "Quality", "Executive readout"], phase_rows)}

  <div class="footer"><span>Reservoir AI HM Report</span><span>01</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">02 - Spatial diagnosis</div>
      <h2>Dashboard-oriented well maps</h2>
      <p class="muted">Same spatial convention requested for the dashboard: X = J, Y = -I.</p>
    </div>
  </div>

  <div class="two-col">
    {_v600c_map_svg(rows, "overall_score", "Overall HM map", "Integrated match quality. Critical wells highlighted by label/stroke.", compact=True, highlight_wells=critical_wells)}
    {_v600c_map_svg(rows, "water_score", "Water/WCT HM map", "Water/WCT match quality. Red/orange areas drive most HM risk.", compact=True, highlight_wells=critical_wells)}
  </div>

  <div class="two-col">
    {_v600c_map_svg(rows, "bhp_score", "BHP/pressure HM map", "Pressure quality, useful to separate relperm from connectivity/support problems.", compact=True, highlight_wells=critical_wells)}
    {_v600c_map_svg(rows, "tran_percentile", "TRAN percentile context", "Transmissibility context. High TRAN alone does not guarantee good water match.", compact=True, highlight_wells=critical_wells)}
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>02</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">03 - Area analysis</div>
      <h2>Spatial mismatch concentration by area</h2>
      <p class="muted">First-pass area split using dashboard coordinates. This can later be replaced by reservoir-defined sectors.</p>
    </div>
  </div>

  <div class="panel">
    <h3>Area interpretation</h3>
    {area_comments}
  </div>

  {_v600c_table(["Area", "Wells", "Active HM wells", "Overall avg", "Water avg", "BHP avg", "TRAN avg", "Dominant issue", "Likely driver"], area_rows)}

  <div class="panel">
    <h3>How to use this page</h3>
    <p class="muted">
      If a specific area shows low water score but high TRAN, the issue may be water mobility, endpoints or source strength rather than missing transmissibility.
      If water score is low and TRAN/PERM are also low, local connectivity or barriers become more plausible.
      Pressure/BHP mismatch should be checked before making relperm-only changes.
    </p>
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>03</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">04 - Critical well evidence</div>
      <h2>Examples of observed vs simulated mismatch</h2>
      <p class="muted">Mini-plots show the variable most responsible for each critical well priority.</p>
    </div>
  </div>

  <div class="critical-grid">
    {critical_cards}
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>04</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">05 - Detailed tables</div>
      <h2>Top review wells and weakest water evidence</h2>
      <p class="muted">Tabular evidence supporting the executive and spatial diagnosis.</p>
    </div>
  </div>

  <h3>Top model-review wells</h3>
  {_v600c_table(["Well", "Overall", "Oil", "Water", "Gas", "BHP", "Main issue", "Recommended review"], review_rows)}

  <h3>Weakest water/WCT wells</h3>
  {_v600c_table(["Well", "Water score", "Direction", "Timing", "Oil", "Gas", "BHP", "TRAN pct", "PERM pct"], weak_water_rows)}

  <div class="panel">
    <h3>Recommended next actions</h3>
    <p class="muted">
      1. Review critical well mini-plots before applying global tuning.
      2. Use water map and area analysis to identify whether mismatch is localized or systematic.
      3. Compare TRAN/PERM context with WCT and pressure mismatch before choosing connectivity or relperm sensitivities.
      4. Use initial/end streamlines on TRAN background to validate proposed dynamic flow corridors.
    </p>
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>05</span></div>
</section>

</body>
</html>
"""


@router.get("/hm-summary/html-v600c", response_class=_HTMLResponseV600C)
async def hm_summary_html_v600c() -> _HTMLResponseV600C:
    return _HTMLResponseV600C(
        build_hm_summary_html(),
        headers={"Cache-Control": "no-store, max-age=0"}
    )


@router.get("/hm-summary/pdf-local-v600c")
async def hm_summary_pdf_local_v600c() -> _ResponseV600C:
    html = build_hm_summary_html()

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise _HTTPExceptionV600C(status_code=500, detail=f"Playwright package not installed: {exc}")

    async def _launch(pw):
        errors = []
        for channel in ["msedge", "chrome"]:
            try:
                return await pw.chromium.launch(channel=channel, headless=True)
            except Exception as exc:
                errors.append(str(exc))

        for path in [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]:
            if _osV600C.path.exists(path):
                try:
                    return await pw.chromium.launch(executable_path=path, headless=True)
                except Exception as exc:
                    errors.append(str(exc))

        raise RuntimeError("Could not launch Edge/Chrome locally. " + " | ".join(errors[-3:]))

    try:
        async with async_playwright() as p:
            browser = await _launch(p)
            page = await browser.new_page(viewport={"width": 1240, "height": 1754})
            await page.set_content(html, wait_until="networkidle")
            pdf = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            )
            await browser.close()
    except Exception as exc:
        raise _HTTPExceptionV600C(status_code=500, detail=f"V600C local PDF generation failed: {exc}")

    filename = f"hm_summary_report_v600c_{_datetimeV600C.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return _ResponseV600C(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# END V600C_HTML REAL HTML REPORT UPGRADE


# ==========================================================
# V600D_HTML REFINED DIAGNOSTIC REPORT
#
# Fixes user feedback:
# - Remove visible technical version label from report cover.
# - KPI values explicitly visible in boxes.
# - Map orientation aligned to dashboard convention requested:
#   I increases left-to-right, J increases top-to-bottom.
# - Smaller critical-well mini plots.
# - More written diagnostic interpretation that combines multiple evidence types.
# - More aggressive scan for inactive/context wells from artifacts/*.csv.
# ==========================================================

from pathlib import Path as _PathV600D
from datetime import datetime as _datetimeV600D
from fastapi.responses import HTMLResponse as _HTMLResponseV600D, Response as _ResponseV600D
from fastapi import HTTPException as _HTTPExceptionV600D
import os as _osV600D
import math as _mathV600D
import csv as _csvV600D
import re as _reV600D


def _v600d_num(x, default=None):
    try:
        if x is None or x == "":
            return default
        f = float(x)
        if not _mathV600D.isfinite(f):
            return default
        return f
    except Exception:
        return default


def _v600d_fmt(x):
    f = _v600d_num(x)
    if f is None:
        try:
            return escape(str(x)) if x not in [None, ""] else "N/A"
        except Exception:
            return "N/A"
    if abs(f - int(f)) < 1e-12:
        return str(int(f))
    return f"{f:.2f}".rstrip("0").rstrip(".")


def _v600d_quality(score):
    s = _v600d_num(score)
    if s is None:
        return "N/A"
    if s >= 90:
        return "Good"
    if s >= 70:
        return "Fair"
    if s >= 50:
        return "Weak"
    return "Poor"


def _v600d_score_color(score):
    s = _v600d_num(score)
    if s is None:
        return "#64748b"
    if s >= 90:
        return "#16a34a"
    if s >= 70:
        return "#84cc16"
    if s >= 50:
        return "#f59e0b"
    return "#ef4444"


def _v600d_compact_well(w):
    return _reV600D.sub(r"[^A-Z0-9]", "", str(w or "").upper())


def _v600d_find_col(row, names):
    keys = {str(k).strip().lower(): k for k in row.keys()}
    for n in names:
        if n.lower() in keys:
            return keys[n.lower()]
    return None


def _v600d_scan_context_wells_from_csv():
    """
    Scan artifacts CSVs for extra wells with I/J coordinates.
    These become inactive/context wells unless diagnostic scores are available.
    """
    root = _PathV600D(".")
    rows = []

    for pth in list((root / "artifacts").rglob("*.csv")) if (root / "artifacts").exists() else []:
        # Avoid extremely unrelated huge files if possible.
        name = pth.name.lower()
        if any(skip in name for skip in ["stress_test", "results", "summary_report"]):
            continue

        try:
            with pth.open("r", encoding="utf-8-sig", newline="") as f:
                reader = _csvV600D.DictReader(f)
                fieldnames = reader.fieldnames or []
                low = [c.lower() for c in fieldnames]

                has_well = any(c in low for c in ["well", "well_name", "name", "wellname"])
                has_i = any(c in low for c in ["i", "grid_i", "cell_i"])
                has_j = any(c in low for c in ["j", "grid_j", "cell_j"])

                if not (has_well and has_i and has_j):
                    continue

                for r in reader:
                    if not r:
                        continue
                    well_key = _v600d_find_col(r, ["well", "well_name", "wellname", "name"])
                    i_key = _v600d_find_col(r, ["i", "grid_i", "cell_i"])
                    j_key = _v600d_find_col(r, ["j", "grid_j", "cell_j"])

                    if not well_key or not i_key or not j_key:
                        continue

                    well = r.get(well_key)
                    i = _v600d_num(r.get(i_key))
                    j = _v600d_num(r.get(j_key))

                    if not well or i is None or j is None:
                        continue

                    rr = dict(r)
                    rr["well"] = str(well)
                    rr["i"] = i
                    rr["j"] = j
                    rr["_context_source_file"] = str(pth)
                    rows.append(rr)
        except Exception:
            pass

    return rows


def _v600d_load_all_wells():
    """
    Merge diagnostic evidence with all context wells found in artifact CSVs.
    """
    by_key = {}

    def put(r, source):
        if not isinstance(r, dict):
            return

        well = r.get("well") or r.get("WELL") or r.get("Well") or r.get("well_name") or r.get("name")
        if not well:
            return

        key = _v600d_compact_well(well)
        if not key:
            return

        existing = by_key.get(key, {})
        merged = dict(existing)
        merged.update(r)
        merged["well"] = str(well)

        srcs = set(str(merged.get("_sources", "")).split(",")) if merged.get("_sources") else set()
        srcs.add(source)
        merged["_sources"] = ",".join(sorted(srcs))

        by_key[key] = merged

    # Context wells first.
    for r in _v600d_scan_context_wells_from_csv():
        put(r, "context_csv")

    # Existing V600C loader if available.
    try:
        for r in _v600c_load_all_wells():
            put(r, "v600c")
    except Exception:
        pass

    # Direct diagnostic evidence.
    try:
        for r in _load_evidence():
            put(r, "diagnostic")
    except Exception:
        pass

    rows = list(by_key.values())

    for r in rows:
        # Normalize I/J
        for src, dst in [("I", "i"), ("J", "j"), ("grid_i", "i"), ("grid_j", "j")]:
            if dst not in r and src in r:
                r[dst] = r.get(src)

        r["i"] = _v600d_num(r.get("i"))
        r["j"] = _v600d_num(r.get("j"))

        for k in [
            "overall_score", "oil_score", "water_score", "gas_score", "bhp_score",
            "tran_percentile", "perm_percentile", "poro_percentile",
            "delta_pressure", "delta_swat_percentile"
        ]:
            if k in r:
                r[k] = _v600d_num(r.get(k))

        srcs = str(r.get("_sources", ""))
        has_any_score = any(_v600d_num(r.get(k)) is not None for k in ["overall_score", "oil_score", "water_score", "gas_score", "bhp_score"])

        active = True
        for k in ["active", "active_producer", "is_active", "producer_active"]:
            if k in r:
                val = str(r.get(k)).lower().strip()
                if val in {"false", "0", "no", "n", "inactive"}:
                    active = False
                elif val in {"true", "1", "yes", "y", "active"}:
                    active = True

        for k in ["inactive", "exclude_from_hm", "excluded"]:
            if k in r:
                val = str(r.get(k)).lower().strip()
                if val in {"true", "1", "yes", "y", "inactive"}:
                    active = False

        # If the well only appears as a context CSV well and has no HM score, show it as inactive/context.
        if not has_any_score or ("diagnostic" not in srcs and "v600c" not in srcs):
            active = False

        r["is_active_well_v600d"] = active

        for phase, score_key in [
            ("water", "water_score"),
            ("bhp", "bhp_score"),
            ("gas", "gas_score"),
            ("oil", "oil_score"),
        ]:
            s = _v600d_num(r.get(score_key))
            r[f"{phase}_mismatch"] = max(0, 100 - s) if s is not None else None

    rows = [r for r in rows if r.get("i") is not None and r.get("j") is not None or r.get("well")]
    return rows


def _v600d_avg(rows, key, active_only=True):
    vals = []
    for r in rows:
        if active_only and not r.get("is_active_well_v600d", True):
            continue
        v = _v600d_num(r.get(key))
        if v is not None:
            vals.append(v)
    return sum(vals) / len(vals) if vals else None


def _v600d_kpi_card(title, value, caption, score=None):
    color = _v600d_score_color(score if score is not None else value)
    return f"""
    <div class="kpi-card" style="border-top-color:{color}">
      <div class="kpi-title">{escape(str(title))}</div>
      <div class="kpi-value">{_v600d_fmt(value)}</div>
      <div class="kpi-caption">{escape(str(caption))}</div>
    </div>
    """


def _v600d_table(headers, rows, cls=""):
    th = "".join(f"<th>{escape(str(h))}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = []
        for h in headers:
            v = r.get(h) if isinstance(r, dict) else None
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                txt = _v600d_fmt(v)
            elif v is None:
                txt = "N/A"
            else:
                txt = escape(str(v))
            tds.append(f"<td>{txt}</td>")
        trs.append("<tr>" + "".join(tds) + "</tr>")
    return f"""
    <table class="data-table {cls}">
      <thead><tr>{th}</tr></thead>
      <tbody>{''.join(trs)}</tbody>
    </table>
    """


def _v600d_dashboard_xy(row):
    """
    Dashboard convention requested by user:
    I increases left-to-right.
    J increases top-to-bottom.
    Since SVG Y naturally increases downward:
    X = I
    Y = J
    """
    i = _v600d_num(row.get("i"))
    j = _v600d_num(row.get("j"))
    if i is None or j is None:
        return None, None
    return i, j


def _v600d_map_svg(rows, score_key, title, comment, highlight_wells=None):
    highlight_wells = set(highlight_wells or [])

    pts = []
    for r in rows:
        x, y = _v600d_dashboard_xy(r)
        if x is not None and y is not None:
            pts.append((r, x, y))

    if not pts:
        return f"""
        <div class="panel">
          <h3>{escape(title)}</h3>
          <p class="muted">No I/J coordinates found.</p>
        </div>
        """

    minx, maxx = min(p[1] for p in pts), max(p[1] for p in pts)
    miny, maxy = min(p[2] for p in pts), max(p[2] for p in pts)
    rx, ry = max(maxx - minx, 1), max(maxy - miny, 1)

    width, height, pad = 500, 300, 32

    shapes = []
    for r, x0, y0 in pts:
        x = pad + (x0 - minx) / rx * (width - 2 * pad)
        y = pad + (y0 - miny) / ry * (height - 2 * pad)

        well = str(r.get("well") or "")
        active = bool(r.get("is_active_well_v600d", True))
        score = r.get(score_key)

        fill = _v600d_score_color(score) if active else "none"
        stroke = "#ffffff" if active else "#94a3b8"
        dash = "" if active else 'stroke-dasharray="3 3"'
        radius = 8.5 if active else 7
        opacity = "0.97" if active else "0.68"
        thick = 3 if well in highlight_wells else 1.6
        label_color = "#e2e8f0" if active else "#94a3b8"

        tooltip = (
            f"{well} | {'active' if active else 'inactive/context'} | "
            f"{score_key}: {_v600d_fmt(score)} | Water: {_v600d_fmt(r.get('water_score'))} | "
            f"BHP: {_v600d_fmt(r.get('bhp_score'))} | TRAN: {_v600d_fmt(r.get('tran_percentile'))}"
        )

        label = ""
        if active or well in highlight_wells:
            label = f'<text x="{x + 9:.2f}" y="{y - 5:.2f}" class="well-label" fill="{label_color}">{escape(well)}</text>'

        shapes.append(f"""
        <g opacity="{opacity}">
          <title>{escape(tooltip)}</title>
          <circle cx="{x:.2f}" cy="{y:.2f}" r="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{thick}" {dash}/>
          {label}
        </g>
        """)

    return f"""
    <div class="panel map-panel">
      <div class="panel-head">
        <div>
          <h3>{escape(title)}</h3>
          <p class="muted">{escape(comment)}</p>
        </div>
        <div class="legend small">
          <span><i style="background:#16a34a"></i>Good</span>
          <span><i style="background:#84cc16"></i>Fair</span>
          <span><i style="background:#f59e0b"></i>Weak</span>
          <span><i style="background:#ef4444"></i>Poor</span>
          <span><i class="hollow"></i>Inactive</span>
        </div>
      </div>
      <svg viewBox="0 0 {width} {height}" class="well-map">
        <rect x="0" y="0" width="{width}" height="{height}" rx="16" fill="#08111f"/>
        <line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#334155" stroke-width="1"/>
        <line x1="{pad}" y1="{pad}" x2="{pad}" y2="{height-pad}" stroke="#334155" stroke-width="1"/>
        <text x="{width/2:.2f}" y="{height-8}" class="axis-label" text-anchor="middle">I index</text>
        <text x="11" y="{height/2:.2f}" class="axis-label" transform="rotate(-90 11 {height/2:.2f})" text-anchor="middle">J index</text>
        {''.join(shapes)}
      </svg>
    </div>
    """


def _v600d_profile_data(well, variable):
    try:
        from app.universal_reservoir_orchestrator_v500 import _v510_get_profile_data
        d = _v510_get_profile_data(well, variable)
        if isinstance(d, dict):
            return d
    except Exception:
        pass
    return {}


def _v600d_numeric_list(vals, nmax=70):
    out = []
    for v in vals or []:
        f = _v600d_num(v)
        if f is not None:
            out.append(f)
    if nmax and len(out) > nmax:
        step = max(1, int(len(out) / nmax))
        out = out[::step]
    return out


def _v600d_mini_profile_svg(well, variable, title):
    d = _v600d_profile_data(well, variable)
    sim = _v600d_numeric_list(d.get("simulated") or d.get("sim") or d.get("simulation") or [])
    obs = _v600d_numeric_list(d.get("observed") or d.get("obs") or d.get("history") or [])

    if not sim and not obs:
        return f"""
        <div class="mini-plot empty">
          <div class="mini-title">{escape(title)}</div>
          <div class="muted">No profile arrays available.</div>
        </div>
        """

    width, height = 230, 86
    pad_l, pad_r, pad_t, pad_b = 24, 8, 12, 18

    allv = sim + obs
    ymin, ymax = min(allv), max(allv)
    if abs(ymax - ymin) < 1e-12:
        ymax = ymin + 1

    def pts(vals):
        out = []
        for idx, val in enumerate(vals):
            x = pad_l + idx / max(len(vals) - 1, 1) * (width - pad_l - pad_r)
            y = height - pad_b - (val - ymin) / (ymax - ymin) * (height - pad_t - pad_b)
            out.append(f"{x:.2f},{y:.2f}")
        return " ".join(out)

    sim_line = f'<polyline points="{pts(sim)}" fill="none" stroke="#38bdf8" stroke-width="2"/>' if sim else ""
    obs_line = f'<polyline points="{pts(obs)}" fill="none" stroke="#f97316" stroke-width="2"/>' if obs else ""

    return f"""
    <div class="mini-plot">
      <div class="mini-title">{escape(title)}</div>
      <svg viewBox="0 0 {width} {height}" class="mini-svg">
        <rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="#08111f"/>
        <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#334155"/>
        <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#334155"/>
        {sim_line}
        {obs_line}
        <text x="{pad_l}" y="10" class="mini-axis">max {_v600d_fmt(ymax)}</text>
        <text x="{width-80}" y="10" class="mini-axis"><tspan fill="#38bdf8">sim</tspan>/<tspan fill="#f97316">obs</tspan></text>
      </svg>
    </div>
    """


def _v600d_critical_variable(row):
    scores = {
        "water": _v600d_num(row.get("water_score")),
        "bhp": _v600d_num(row.get("bhp_score")),
        "gas": _v600d_num(row.get("gas_score")),
        "oil": _v600d_num(row.get("oil_score")),
    }
    scores = {k: v for k, v in scores.items() if v is not None}
    return min(scores, key=scores.get) if scores else "water"


def _v600d_explain_well(row, var):
    tran = _v600d_num(row.get("tran_percentile"))
    perm = _v600d_num(row.get("perm_percentile"))
    bhp = _v600d_num(row.get("bhp_score"))
    water = _v600d_num(row.get("water_score"))
    direction = str(row.get("water_direction") or "").lower()

    if var == "water":
        if "too high" in direction:
            if tran is not None and tran >= 65:
                return "The model overpredicts water despite high TRAN context. This points more toward water mobility/relperm/endpoints or water-source strength than a simple missing-connectivity correction."
            if tran is not None and tran < 45:
                return "The model overpredicts water in a low-TRAN context. This suggests a local over-connection/completion issue or overly strong water source near the well."
            return "Water is the dominant mismatch. The key review is water mobility, relperm endpoints and source connection."
        if "too low" in direction:
            if tran is not None and tran < 45:
                return "The model underpredicts water and local TRAN is low. Connectivity barriers or underestimated transmissibility corridors are plausible."
            return "The model underpredicts water. Review water-source access, saturation movement and water mobility."
        return "Water is the weakest dimension. Combine profile shape with TRAN/PERM and BHP before deciding relperm vs connectivity."

    if var == "bhp":
        return "Pressure/BHP is the dominant mismatch. This should be checked before phase tuning because it can indicate pressure support, boundary or connectivity issues."

    if var == "gas":
        return "Gas/GOR is the dominant mismatch. Check gas allocation, pressure coupling and whether gas trend mismatch is local or systematic."

    return "Oil is the dominant mismatch. Review productivity, controls and local property connection."


def _v600d_critical_cards(rows):
    active = [r for r in rows if r.get("is_active_well_v600d", True)]
    if not active:
        active = rows

    scored = []
    for r in active:
        wm = _v600d_num(r.get("water_mismatch"), 0) or 0
        bm = _v600d_num(r.get("bhp_mismatch"), 0) or 0
        gm = _v600d_num(r.get("gas_mismatch"), 0) or 0
        om = _v600d_num(r.get("oil_mismatch"), 0) or 0
        priority = 0.38 * wm + 0.30 * bm + 0.18 * gm + 0.14 * om
        scored.append((priority, r))

    top = [r for _, r in sorted(scored, key=lambda x: x[0], reverse=True)[:4]]
    cards = []

    for r in top:
        well = str(r.get("well") or "")
        var = _v600d_critical_variable(r)
        score = r.get(f"{var}_score")
        plot_var = "water" if var == "water" else ("bhp" if var == "bhp" else var)
        explanation = _v600d_explain_well(r, var)

        cards.append(f"""
        <div class="critical-card">
          <div class="critical-head">
            <div>
              <h3>{escape(well)}</h3>
              <p class="muted">Main issue: {escape(var.upper())} | score {_v600d_fmt(score)}</p>
            </div>
            <span class="badge" style="background:{_v600d_score_color(score)}">{escape(_v600d_quality(score))}</span>
          </div>
          {_v600d_mini_profile_svg(well, plot_var, f"{well} {plot_var.upper()}")}
          <p class="critical-text">{escape(explanation)}</p>
        </div>
        """)

    return "".join(cards), [str(r.get("well") or "") for r in top]


def _v600d_area_analysis(rows):
    pts = []
    for r in rows:
        x, y = _v600d_dashboard_xy(r)
        if x is not None and y is not None:
            pts.append((r, x, y))

    if not pts:
        return [], "<p class='muted'>No coordinates available.</p>"

    xs = [p[1] for p in pts]
    ys = [p[2] for p in pts]
    xmed = sorted(xs)[len(xs) // 2]
    ymed = sorted(ys)[len(ys) // 2]

    def area(x, y):
        # J increases downward: smaller J is North/top.
        ns = "N" if y <= ymed else "S"
        # I increases rightward.
        ew = "E" if x >= xmed else "W"
        return ns + ew

    grouped = {}
    for r, x, y in pts:
        grouped.setdefault(area(x, y), []).append(r)

    rows_out = []
    comments = []

    for a in ["NW", "NE", "SW", "SE"]:
        g = grouped.get(a, [])
        if not g:
            continue

        active_count = sum(1 for r in g if r.get("is_active_well_v600d", True))
        overall = _v600d_avg(g, "overall_score", active_only=False)
        water = _v600d_avg(g, "water_score", active_only=False)
        bhp = _v600d_avg(g, "bhp_score", active_only=False)
        tran = _v600d_avg(g, "tran_percentile", active_only=False)
        perm = _v600d_avg(g, "perm_percentile", active_only=False)

        candidates = {
            "Water/WCT": water,
            "BHP/Pressure": bhp,
            "Overall": overall,
        }
        candidates = {k: v for k, v in candidates.items() if v is not None}
        dominant = min(candidates, key=candidates.get) if candidates else "N/A"

        if dominant == "Water/WCT" and tran is not None and tran >= 65:
            driver = "water mobility / relperm / endpoints, not pure missing TRAN"
        elif dominant == "Water/WCT" and tran is not None and tran < 45:
            driver = "local connectivity / barriers / low transmissibility"
        elif dominant == "BHP/Pressure":
            driver = "pressure support / connectivity / controls"
        else:
            driver = "mixed diagnostic behaviour"

        rows_out.append({
            "Area": a,
            "Wells": len(g),
            "Active HM wells": active_count,
            "Overall avg": overall,
            "Water avg": water,
            "BHP avg": bhp,
            "TRAN avg": tran,
            "PERM avg": perm,
            "Dominant issue": dominant,
            "Likely driver": driver,
        })

        comments.append(
            f"<li><b>{a}</b>: {len(g)} wells ({active_count} active HM wells). "
            f"Dominant issue: {escape(dominant)}. "
            f"The combined evidence points to <b>{escape(driver)}</b>.</li>"
        )

    synthesis = """
    <p class="diagnostic-paragraph">
      This area analysis is useful because it does not look at a single score in isolation.
      It combines water mismatch, BHP mismatch and TRAN/PERM context. If water is poor but TRAN is high,
      a simple transmissibility increase is unlikely to be the safest first correction. If water is poor and TRAN/PERM are low,
      local connectivity, barriers or corridor definition become more plausible.
    </p>
    """

    return rows_out, synthesis + "<ul class='area-comments'>" + "".join(comments) + "</ul>"


def _v600d_main_synthesis(rows):
    active = [r for r in rows if r.get("is_active_well_v600d", True)]
    if not active:
        active = rows

    oil = _v600d_avg(active, "oil_score", active_only=False)
    gas = _v600d_avg(active, "gas_score", active_only=False)
    water = _v600d_avg(active, "water_score", active_only=False)
    bhp = _v600d_avg(active, "bhp_score", active_only=False)

    water_low = water is not None and water < 70
    bhp_low = bhp is not None and bhp < 70
    oil_good = oil is not None and oil >= 90
    gas_good = gas is not None and gas >= 90

    bullets = []
    if oil_good and gas_good and water_low:
        bullets.append("Oil and gas are good, while water is weak. This suggests the bulk hydrocarbon production capacity is acceptable, but water movement/mobility is not correctly represented.")
    if water_low and bhp_low:
        bullets.append("Water and pressure are both weak. This is important because a water-only relperm correction could hide an underlying connectivity, support or control issue.")
    if water_low and not bhp_low:
        bullets.append("Water is weak but pressure is not equally weak. This makes water mobility, endpoints, saturation functions or local water source representation more plausible.")
    if bhp_low and not water_low:
        bullets.append("Pressure is weak while water is not the main issue. Prioritise pressure support, boundary behaviour, controls and connectivity before phase tuning.")
    if not bullets:
        bullets.append("The model does not show one single dominant failure mode. The safest interpretation is to review weak wells individually and avoid global tuning.")

    return "<ul class='insight-list'>" + "".join(f"<li>{escape(b)}</li>" for b in bullets) + "</ul>"


def build_hm_summary_html() -> str:
    rows = _v600d_load_all_wells()
    now = _datetimeV600D.now().strftime("%Y-%m-%d %H:%M")

    if not rows:
        return "<html><body><h1>History Match Diagnostic Summary Report</h1><p>No data available.</p></body></html>"

    active_rows = [r for r in rows if r.get("is_active_well_v600d", True)]
    inactive_rows = [r for r in rows if not r.get("is_active_well_v600d", True)]

    overall = _v600d_avg(rows, "overall_score")
    oil = _v600d_avg(rows, "oil_score")
    water = _v600d_avg(rows, "water_score")
    gas = _v600d_avg(rows, "gas_score")
    bhp = _v600d_avg(rows, "bhp_score")

    phase_rows = [
        {"Area": "Overall", "Average score": overall, "Quality": _v600d_quality(overall), "Executive readout": "Integrated history-match quality across active wells."},
        {"Area": "Oil", "Average score": oil, "Quality": _v600d_quality(oil), "Executive readout": "Oil match acts as a constraint while tuning water and pressure."},
        {"Area": "Gas/GOR", "Average score": gas, "Quality": _v600d_quality(gas), "Executive readout": "Gas behaviour indicates whether GOR/gas allocation needs review."},
        {"Area": "Water/WCT", "Average score": water, "Quality": _v600d_quality(water), "Executive readout": "Usually the main signal of dynamic water movement mismatch."},
        {"Area": "BHP/Pressure", "Average score": bhp, "Quality": _v600d_quality(bhp), "Executive readout": "Separates relperm-only issues from connectivity/support problems."},
    ]

    critical_cards, critical_wells = _v600d_critical_cards(rows)
    area_rows, area_comments = _v600d_area_analysis(rows)
    synthesis = _v600d_main_synthesis(rows)

    top_review = []
    for r in active_rows:
        wm = _v600d_num(r.get("water_mismatch"), 0) or 0
        bm = _v600d_num(r.get("bhp_mismatch"), 0) or 0
        gm = _v600d_num(r.get("gas_mismatch"), 0) or 0
        om = _v600d_num(r.get("oil_mismatch"), 0) or 0
        priority = 0.38 * wm + 0.30 * bm + 0.18 * gm + 0.14 * om
        top_review.append((priority, r))

    review_rows = []
    for _, r in sorted(top_review, key=lambda x: x[0], reverse=True)[:8]:
        var = _v600d_critical_variable(r)
        review_rows.append({
            "Well": r.get("well"),
            "Overall": r.get("overall_score"),
            "Oil": r.get("oil_score"),
            "Water": r.get("water_score"),
            "Gas": r.get("gas_score"),
            "BHP": r.get("bhp_score"),
            "Main issue": var.upper(),
            "Integrated interpretation": _v600d_explain_well(r, var),
        })

    weak_water_rows = []
    for r in sorted(active_rows, key=lambda x: _v600d_num(x.get("water_score"), 999))[:8]:
        weak_water_rows.append({
            "Well": r.get("well"),
            "Water score": r.get("water_score"),
            "Direction": r.get("water_direction"),
            "Timing": r.get("water_timing"),
            "Oil": r.get("oil_score"),
            "Gas": r.get("gas_score"),
            "BHP": r.get("bhp_score"),
            "TRAN pct": r.get("tran_percentile"),
            "PERM pct": r.get("perm_percentile"),
        })

    return f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>History Match Diagnostic Summary Report</title>
<style>
@page {{ size:A4; margin:9mm; }}
* {{ box-sizing:border-box; }}
body {{
  margin:0;
  font-family:Inter, Segoe UI, Arial, sans-serif;
  background:#e8eef6;
  color:#0f172a;
}}
.page {{
  page-break-after:always;
  min-height:1080px;
  background:#f8fafc;
  padding:28px 32px;
  position:relative;
}}
.cover {{
  background:radial-gradient(circle at top right,rgba(56,189,248,.22),transparent 36%),
             linear-gradient(135deg,#06101e,#0f172a 55%,#1e293b);
  color:white;
}}
.brand {{
  display:inline-block;
  padding:7px 12px;
  border:1px solid rgba(255,255,255,.22);
  border-radius:999px;
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.1em;
  font-weight:800;
  background:rgba(255,255,255,.08);
}}
.cover h1 {{
  font-size:46px;
  line-height:1.02;
  letter-spacing:-.04em;
  margin:72px 0 16px;
}}
.subtitle {{
  color:#cbd5e1;
  font-size:16px;
  line-height:1.5;
  max-width:780px;
}}
.kpi-grid {{
  display:grid;
  grid-template-columns:repeat(5,1fr);
  gap:10px;
  margin:18px 0 16px;
}}
.kpi-card {{
  background:#ffffff;
  border:1px solid #dbe4ee;
  border-top:5px solid #2563eb;
  border-radius:15px;
  padding:13px;
  box-shadow:0 8px 20px rgba(15,23,42,.06);
  min-height:92px;
}}
.cover .kpi-card {{
  background:#ffffff;
}}
.kpi-title {{
  color:#475569;
  font-size:10px;
  text-transform:uppercase;
  letter-spacing:.08em;
  font-weight:900;
}}
.kpi-value {{
  margin-top:7px;
  font-size:26px;
  font-weight:900;
  color:#0f172a !important;
  line-height:1.1;
}}
.kpi-caption {{
  margin-top:4px;
  color:#64748b;
  font-size:10px;
  line-height:1.25;
}}
.section-head {{
  display:flex;
  justify-content:space-between;
  align-items:flex-start;
  margin-bottom:14px;
  padding-bottom:10px;
  border-bottom:1px solid #dbe4ee;
}}
.kicker {{
  font-size:11px;
  text-transform:uppercase;
  letter-spacing:.11em;
  color:#2563eb;
  font-weight:900;
  margin-bottom:4px;
}}
h2 {{
  margin:0;
  font-size:25px;
  letter-spacing:-.03em;
}}
h3 {{
  margin:0 0 7px;
  font-size:15px;
}}
.muted {{
  color:#64748b;
  margin:0;
  font-size:11px;
  line-height:1.35;
}}
.panel {{
  background:white;
  border:1px solid #dbe4ee;
  border-radius:18px;
  padding:14px;
  box-shadow:0 8px 22px rgba(15,23,42,.05);
  margin-bottom:13px;
}}
.panel-head {{
  display:flex;
  justify-content:space-between;
  gap:12px;
  align-items:flex-start;
}}
.two-col {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:13px;
}}
.well-map {{
  width:100%;
  height:auto;
  display:block;
  margin-top:8px;
}}
.well-label {{
  font-size:8px;
  font-weight:800;
}}
.axis-label {{
  fill:#94a3b8;
  font-size:9px;
  font-weight:700;
}}
.legend {{
  display:flex;
  gap:7px;
  flex-wrap:wrap;
  color:#475569;
  font-size:8.5px;
}}
.legend span {{
  display:flex;
  align-items:center;
  gap:4px;
}}
.legend i {{
  display:inline-block;
  width:9px;
  height:9px;
  border-radius:99px;
}}
.legend i.hollow {{
  border:1.5px dashed #94a3b8;
  background:transparent;
}}
.data-table {{
  width:100%;
  border-collapse:separate;
  border-spacing:0;
  font-size:9.2px;
  background:white;
  border:1px solid #dbe4ee;
  border-radius:12px;
  overflow:hidden;
  margin:8px 0 12px;
}}
.data-table th {{
  background:#0f172a;
  color:white;
  padding:7px 6px;
  text-align:left;
  font-weight:800;
}}
.data-table td {{
  padding:6px;
  border-top:1px solid #e2e8f0;
  vertical-align:top;
}}
.data-table tr:nth-child(even) td {{
  background:#f8fafc;
}}
.critical-grid {{
  display:grid;
  grid-template-columns:1fr 1fr;
  gap:14px;
}}
.critical-card {{
  background:white;
  border:1px solid #dbe4ee;
  border-radius:16px;
  padding:13px;
  min-height:285px;
  box-shadow:0 8px 20px rgba(15,23,42,.05);
}}
.critical-head {{
  display:flex;
  justify-content:space-between;
  gap:8px;
  align-items:flex-start;
}}
.badge {{
  color:white;
  border-radius:999px;
  padding:4px 8px;
  font-size:9px;
  font-weight:900;
}}
.critical-text {{
  font-size:10px;
  color:#334155;
  line-height:1.42;
  margin:9px 0 0;
}}
.mini-plot {{
  margin-top:9px;
}}
.mini-title {{
  font-size:9.5px;
  color:#475569;
  font-weight:800;
  margin-bottom:3px;
}}
.mini-svg {{
  width:100%;
  height:auto;
  max-height:138px;
}}
.mini-axis {{
  fill:#94a3b8;
  font-size:7.5px;
  font-weight:700;
}}
.area-comments {{
  margin:8px 0 0;
  padding-left:17px;
  color:#334155;
  font-size:10.8px;
  line-height:1.45;
}}
.diagnostic-paragraph {{
  color:#334155;
  font-size:11px;
  line-height:1.5;
  margin:0 0 8px;
}}
.insight-list {{
  margin:8px 0 0;
  padding-left:18px;
  color:#334155;
  font-size:11px;
  line-height:1.5;
}}
.footer {{
  position:absolute;
  bottom:13px;
  left:32px;
  right:32px;
  color:#94a3b8;
  font-size:9px;
  display:flex;
  justify-content:space-between;
  border-top:1px solid #e2e8f0;
  padding-top:7px;
}}
</style>
</head>
<body>

<section class="page cover">
  <span class="brand">Reservoir AI Diagnostic Report</span>
  <h1>History Match<br>Diagnostic Summary</h1>
  <p class="subtitle">
    Executive and technical report combining KPI scores, well-map context, inactive/context wells,
    area-level mismatch patterns and critical well profile evidence.
  </p>
  <div class="kpi-grid" style="margin-top:52px;">
    {_v600d_kpi_card("Wells", len(rows), f"{len(active_rows)} active / {len(inactive_rows)} inactive", overall)}
    {_v600d_kpi_card("Overall", overall, "Average HM score", overall)}
    {_v600d_kpi_card("Oil", oil, "Oil match", oil)}
    {_v600d_kpi_card("Water", water, "Water/WCT match", water)}
    {_v600d_kpi_card("BHP", bhp, "Pressure match", bhp)}
  </div>
  <p class="subtitle" style="margin-top:50px;">
    Generated {escape(now)}. Map orientation follows the dashboard convention: I increases left-to-right and J increases top-to-bottom.
  </p>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">01 - Executive overview</div>
      <h2>What the integrated evidence says</h2>
      <p class="muted">This page explains what is learned by combining profiles, phase scores, BHP and spatial evidence.</p>
    </div>
  </div>

  <div class="kpi-grid">
    {_v600d_kpi_card("Overall", overall, "Integrated score", overall)}
    {_v600d_kpi_card("Oil", oil, "Production match", oil)}
    {_v600d_kpi_card("Gas/GOR", gas, "Gas behaviour", gas)}
    {_v600d_kpi_card("Water/WCT", water, "Main calibration risk", water)}
    {_v600d_kpi_card("BHP", bhp, "Pressure quality", bhp)}
  </div>

  <div class="two-col">
    <div class="panel">
      <h3>Integrated diagnostic synthesis</h3>
      {synthesis}
    </div>
    <div class="panel">
      <h3>Why this is more than a KPI table</h3>
      <p class="diagnostic-paragraph">
        The report does not only rank low scores. It checks whether weak water wells also have weak BHP,
        and whether they sit in high or low TRAN/PERM context. This helps separate likely relperm/water mobility
        problems from likely connectivity/support problems.
      </p>
    </div>
  </div>

  {_v600d_table(["Area", "Average score", "Quality", "Executive readout"], phase_rows)}

  <div class="footer"><span>Reservoir AI HM Report</span><span>01</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">02 - Spatial diagnosis</div>
      <h2>Well maps aligned with dashboard orientation</h2>
      <p class="muted">I increases left-to-right. J increases top-to-bottom. Hollow grey points are inactive/context wells.</p>
    </div>
  </div>

  <div class="two-col">
    {_v600d_map_svg(rows, "overall_score", "Overall HM map", "Integrated match quality; critical wells are highlighted.", highlight_wells=critical_wells)}
    {_v600d_map_svg(rows, "water_score", "Water/WCT HM map", "Water/WCT match quality; red/orange points drive most uncertainty.", highlight_wells=critical_wells)}
  </div>

  <div class="two-col">
    {_v600d_map_svg(rows, "bhp_score", "BHP/pressure HM map", "Pressure quality helps distinguish relperm-only issues from connectivity/support issues.", highlight_wells=critical_wells)}
    {_v600d_map_svg(rows, "tran_percentile", "TRAN percentile context", "Transmissibility context used to interpret whether a water issue is likely connectivity-driven.", highlight_wells=critical_wells)}
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>02</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">03 - Area analysis</div>
      <h2>Where mismatch concentrates and what it may mean</h2>
      <p class="muted">Areas are based on dashboard I/J quadrants. This can later be replaced by reservoir-defined sectors.</p>
    </div>
  </div>

  <div class="panel">
    <h3>Area-level interpretation</h3>
    {area_comments}
  </div>

  {_v600d_table(["Area", "Wells", "Active HM wells", "Overall avg", "Water avg", "BHP avg", "TRAN avg", "PERM avg", "Dominant issue", "Likely driver"], area_rows)}

  <div class="panel">
    <h3>Decision logic</h3>
    <p class="diagnostic-paragraph">
      A low water score in a high-TRAN area should not automatically trigger a TRAN increase: it may instead point to water mobility,
      relperm endpoints or water-source strength. A low water score in a low-TRAN/PERM area makes local connectivity, barriers or corridor definition more plausible.
      If BHP is weak in the same area, pressure support and boundary assumptions must be reviewed before phase tuning.
    </p>
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>03</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">04 - Critical well evidence</div>
      <h2>Examples of the mismatch behind the scores</h2>
      <p class="muted">Mini-plots are intentionally small: they provide evidence without overwhelming the report layout.</p>
    </div>
  </div>

  <div class="critical-grid">
    {critical_cards}
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>04</span></div>
</section>

<section class="page">
  <div class="section-head">
    <div>
      <div class="kicker">05 - Detailed evidence</div>
      <h2>Top review wells and weakest water evidence</h2>
      <p class="muted">Tabular support for the executive conclusions.</p>
    </div>
  </div>

  <h3>Top model-review wells</h3>
  {_v600d_table(["Well", "Overall", "Oil", "Water", "Gas", "BHP", "Main issue", "Integrated interpretation"], review_rows)}

  <h3>Weakest water/WCT wells</h3>
  {_v600d_table(["Well", "Water score", "Direction", "Timing", "Oil", "Gas", "BHP", "TRAN pct", "PERM pct"], weak_water_rows)}

  <div class="panel">
    <h3>Recommended next actions</h3>
    <p class="diagnostic-paragraph">
      Review critical well profiles first, then check whether the same mismatch is spatially clustered.
      Use streamlines at beginning/end of history over TRAN background to validate whether the proposed water movement paths are realistic.
      Avoid tuning relperm or TRAN globally before checking BHP and area-level behaviour.
    </p>
  </div>

  <div class="footer"><span>Reservoir AI HM Report</span><span>05</span></div>
</section>

</body>
</html>
"""


@router.get("/hm-summary/html-v600d", response_class=_HTMLResponseV600D)
async def hm_summary_html_v600d() -> _HTMLResponseV600D:
    return _HTMLResponseV600D(build_hm_summary_html(), headers={"Cache-Control": "no-store, max-age=0"})


@router.get("/hm-summary/pdf-local-v600d")
async def hm_summary_pdf_local_v600d() -> _ResponseV600D:
    html = build_hm_summary_html()

    try:
        from playwright.async_api import async_playwright
    except Exception as exc:
        raise _HTTPExceptionV600D(status_code=500, detail=f"Playwright package not installed: {exc}")

    async def _launch(pw):
        errors = []
        for channel in ["msedge", "chrome"]:
            try:
                return await pw.chromium.launch(channel=channel, headless=True)
            except Exception as exc:
                errors.append(str(exc))

        for path in [
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]:
            if _osV600D.path.exists(path):
                try:
                    return await pw.chromium.launch(executable_path=path, headless=True)
                except Exception as exc:
                    errors.append(str(exc))

        raise RuntimeError("Could not launch Edge/Chrome locally. " + " | ".join(errors[-3:]))

    try:
        async with async_playwright() as p:
            browser = await _launch(p)
            page = await browser.new_page(viewport={"width": 1240, "height": 1754})
            await page.set_content(html, wait_until="networkidle")
            pdf = await page.pdf(
                format="A4",
                print_background=True,
                margin={"top": "0mm", "right": "0mm", "bottom": "0mm", "left": "0mm"},
            )
            await browser.close()
    except Exception as exc:
        raise _HTTPExceptionV600D(status_code=500, detail=f"V600D local PDF generation failed: {exc}")

    filename = f"hm_summary_report_v600d_{_datetimeV600D.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return _ResponseV600D(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

# END V600D_HTML REFINED DIAGNOSTIC REPORT


# ==========================================================
# V600E LARGER CRITICAL WELL MINI-PLOTS
#
# Override only the mini-profile SVG geometry used by the existing
# V600D critical well cards.
# ==========================================================

def _v600d_mini_profile_svg(well, variable, title):
    d = _v600d_profile_data(well, variable)
    sim = _v600d_numeric_list(d.get("simulated") or d.get("sim") or d.get("simulation") or [], nmax=80)
    obs = _v600d_numeric_list(d.get("observed") or d.get("obs") or d.get("history") or [], nmax=80)

    if not sim and not obs:
        return f"""
        <div class="mini-plot empty">
          <div class="mini-title">{escape(title)}</div>
          <div class="muted">No profile arrays available.</div>
        </div>
        """

    width, height = 330, 132
    pad_l, pad_r, pad_t, pad_b = 34, 12, 18, 25

    allv = sim + obs
    ymin, ymax = min(allv), max(allv)

    if abs(ymax - ymin) < 1e-12:
        ymax = ymin + 1

    def pts(vals):
        out = []
        for idx, val in enumerate(vals):
            x = pad_l + idx / max(len(vals) - 1, 1) * (width - pad_l - pad_r)
            y = height - pad_b - (val - ymin) / (ymax - ymin) * (height - pad_t - pad_b)
            out.append(f"{x:.2f},{y:.2f}")
        return " ".join(out)

    sim_line = f'<polyline points="{pts(sim)}" fill="none" stroke="#38bdf8" stroke-width="2.4"/>' if sim else ""
    obs_line = f'<polyline points="{pts(obs)}" fill="none" stroke="#f97316" stroke-width="2.4"/>' if obs else ""

    return f"""
    <div class="mini-plot">
      <div class="mini-title">{escape(title)} - observed vs simulated</div>
      <svg viewBox="0 0 {width} {height}" class="mini-svg">
        <rect x="0" y="0" width="{width}" height="{height}" rx="12" fill="#08111f"/>
        <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#334155"/>
        <line x1="{pad_l}" y1="{pad_t}" x2="{pad_l}" y2="{height-pad_b}" stroke="#334155"/>
        <line x1="{pad_l}" y1="{pad_t}" x2="{width-pad_r}" y2="{pad_t}" stroke="#16263d"/>
        <line x1="{pad_l}" y1="{height-pad_b}" x2="{width-pad_r}" y2="{height-pad_b}" stroke="#334155"/>
        {sim_line}
        {obs_line}
        <text x="{pad_l}" y="13" class="mini-axis">max {_v600d_fmt(ymax)}</text>
        <text x="{pad_l}" y="{height-7}" class="mini-axis">min {_v600d_fmt(ymin)}</text>
        <text x="{width-116}" y="13" class="mini-axis">
          <tspan fill="#38bdf8">simulated</tspan>
        </text>
        <text x="{width-116}" y="27" class="mini-axis">
          <tspan fill="#f97316">observed</tspan>
        </text>
      </svg>
    </div>
    """

# END V600E LARGER CRITICAL WELL MINI-PLOTS
