import csv
import math
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


ROOT = Path(__file__).resolve().parents[1]
CONTEXT_CSV = ROOT / "artifacts" / "diagnosis" / "well_property_driver_context.csv"


def safe_float(v):
    try:
        if v is None or v == "":
            return None
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    except Exception:
        return None




# ==========================================================
# NUMERIC HELPERS V39
# ==========================================================
def avg(values):
    xs = []
    for v in values or []:
        try:
            if v is None or v == "":
                continue
            x = float(v)
            if x == x:
                xs.append(x)
        except Exception:
            pass

    if not xs:
        return None

    return sum(xs) / len(xs)


def load_rows() -> List[Dict[str, Any]]:
    if not CONTEXT_CSV.exists():
        return []

    with CONTEXT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def is_cluster_map_request(message: str) -> bool:
    q = str(message or "").lower()

    triggers = [
        "cluster map",
        "clusterize",
        "clusterise",
        "clustering map",
        "mismatch map",
        "pattern map",
        "spatial pattern map",
        "systemic map",
        "regional pattern",
        "show clusters",
        "show mismatch clusters",
        "map of mismatch",
        "map mismatch",
        "water mismatch map",
        "oil mismatch map",
        "bhp mismatch map",
        "pressure mismatch map",
        "gas mismatch map",
    ]

    return any(t in q for t in triggers)


def detect_variable(message: str) -> str:
    q = str(message or "").lower()

    if any(x in q for x in ["water", "wct", "water cut"]):
        return "water"

    if any(x in q for x in ["oil", "opr"]):
        return "oil"

    if any(x in q for x in ["gas", "gor"]):
        return "gas"

    if any(x in q for x in ["bhp", "pressure"]):
        return "bhp"

    return "dominant"


def score(row, key):
    return safe_float(row.get(key))


def classify_score(x):
    if x is None:
        return "Not evaluated"
    if x >= 75:
        return "Good"
    if x >= 60:
        return "Fair"
    return "Poor"


def dominant_issue(row):
    metrics = {
        "Oil": score(row, "oil_hm_score"),
        "Water": score(row, "water_hm_score"),
        "Gas": score(row, "gas_hm_score"),
        "BHP": score(row, "bhp_hm_score"),
    }

    valid = {k: v for k, v in metrics.items() if v is not None}

    if not valid:
        return "Not evaluated", None

    weak = {k: v for k, v in valid.items() if v < 75}

    if not weak:
        return "Good match", min(valid.values())

    worst_name = min(valid, key=lambda k: valid[k])
    worst_score = valid[worst_name]

    weak_count = len(weak)

    if weak_count >= 2:
        return "Multi-variable issue", worst_score

    return f"{worst_name} issue", worst_score


def variable_issue(row, variable):
    key = {
        "water": "water_hm_score",
        "oil": "oil_hm_score",
        "gas": "gas_hm_score",
        "bhp": "bhp_hm_score",
    }.get(variable)

    if not key:
        return dominant_issue(row)

    x = score(row, key)
    cls = classify_score(x)

    label = {
        "water": "Water issue",
        "oil": "Oil issue",
        "gas": "Gas issue",
        "bhp": "BHP issue",
    }[variable]

    if cls == "Good":
        return "Good match", x

    if cls == "Not evaluated":
        return "Not evaluated", x

    return label, x


def issue_code(issue: str) -> int:
    mapping = {
        "Good match": 0,
        "Water issue": 1,
        "Oil issue": 2,
        "Gas issue": 3,
        "BHP issue": 4,
        "Multi-variable issue": 5,
        "Not evaluated": 6,
        "Inactive / excluded": 7,
    }
    return mapping.get(issue, 6)


def clean_direction(v):
    s = str(v or "").strip()
    if not s:
        return ""
    return s.replace("_", " ")


def row_excluded(row):
    if str(row.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]:
        return True
    if str(row.get("inactive_producer_zero_oil_history") or "").lower() in ["true", "1", "yes"]:
        return True
    return False


def build_cluster_map_payload(variable: str = "dominant") -> Dict[str, Any]:
    rows = load_rows()

    wells = []

    for r in rows:
        i = safe_float(r.get("i"))
        j = safe_float(r.get("j"))

        if i is None or j is None:
            continue

        if row_excluded(r):
            issue = "Inactive / excluded"
            issue_score = None
        else:
            if variable == "dominant":
                issue, issue_score = dominant_issue(r)
            else:
                issue, issue_score = variable_issue(r, variable)

        water_direction = clean_direction(r.get("water_direction") or r.get("water_final_direction"))
        water_timing = clean_direction(r.get("water_timing_issue"))

        wells.append({
            "well": r.get("well"),
            "i": i,
            "j": j,
            "issue": issue,
            "issue_code": issue_code(issue),
            "issue_score": issue_score,
            "overall_score": score(r, "overall_hm_score"),
            "overall_class": r.get("overall_hm_class"),
            "oil_score": score(r, "oil_hm_score"),
            "water_score": score(r, "water_hm_score"),
            "gas_score": score(r, "gas_hm_score"),
            "bhp_score": score(r, "bhp_hm_score"),
            "oil_class": r.get("oil_hm_class"),
            "water_class": r.get("water_hm_class"),
            "gas_class": r.get("gas_hm_class"),
            "bhp_class": r.get("bhp_hm_class"),
            "water_direction": water_direction,
            "water_timing": water_timing,
            "delta_swat": score(r, "delta_swat"),
            "delta_swat_percentile": score(r, "delta_swat_percentile"),
            "delta_pressure": score(r, "delta_pressure"),
            "delta_pressure_percentile": score(r, "delta_pressure_percentile"),
            "tran_percentile": score(r, "wellconn_weighted_tran_h_percentile"),
            "perm_percentile": score(r, "mean_perm_h_percentile"),
            "poro_percentile": score(r, "mean_poro_percentile"),
            "driver": clean_direction(r.get("primary_driver") or r.get("likely_driver") or r.get("driver")),
            "driver_family": clean_direction(r.get("driver_family")),
        })

    summary = {}
    for w in wells:
        summary.setdefault(w["issue"], 0)
        summary[w["issue"]] += 1

    # Simple spatial summaries by issue.
    issue_centers = []
    for issue, count in summary.items():
        pts = [w for w in wells if w["issue"] == issue]
        if not pts:
            continue
        issue_centers.append({
            "issue": issue,
            "count": count,
            "avg_i": sum(p["i"] for p in pts) / len(pts),
            "avg_j": sum(p["j"] for p in pts) / len(pts),
            "weakest_wells": [
                p["well"] for p in sorted(
                    pts,
                    key=lambda x: x["issue_score"] if x["issue_score"] is not None else 999
                )[:5]
            ],
        })

    issue_centers.sort(key=lambda x: -x["count"])

    return {
        "variable": variable,
        "wells": wells,
        "summary": summary,
        "issue_centers": issue_centers,
        "legend": [
            {"issue": "Good match", "code": 0},
            {"issue": "Water issue", "code": 1},
            {"issue": "Oil issue", "code": 2},
            {"issue": "Gas issue", "code": 3},
            {"issue": "BHP issue", "code": 4},
            {"issue": "Multi-variable issue", "code": 5},
            {"issue": "Not evaluated", "code": 6},
            {"issue": "Inactive / excluded", "code": 7},
        ],
    }


def build_cluster_answer(payload: Dict[str, Any]) -> str:
    variable = payload.get("variable")
    summary = payload.get("summary") or {}
    centers = payload.get("issue_centers") or []

    if not summary:
        return "I could not build a cluster map because no well-level diagnostic points were available."

    dominant = centers[0] if centers else None

    if variable == "dominant":
        base = "I built a spatial cluster map using the dominant mismatch family for each well."
    else:
        base = f"I built a spatial cluster map focused on {variable} mismatch."

    if dominant:
        base += (
            f" The largest cluster is '{dominant['issue']}' with {dominant['count']} wells. "
            f"Weakest examples in that cluster: {', '.join(dominant['weakest_wells'])}."
        )

    base += " Use the map to see whether mismatch is isolated by well or spatially organized by area."

    return base


def answer_cluster_map_question(message: str) -> Optional[Dict[str, Any]]:
    if not is_cluster_map_request(message):
        return None

    variable = detect_variable(message)
    payload = build_similarity_cluster_map_payload(variable=variable)
    answer = build_similarity_cluster_answer(payload)

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "cluster_map",
        "ui_blocks": [
            {
                "type": "cluster_map",
                "title": (
                    "Diagnostic Similarity Cluster Map"
                    if variable == "dominant"
                    else f"{variable.title()} Diagnostic Similarity Cluster Map"
                ),
                "payload": payload,
            },
            {
                "type": "compact_table",
                "title": "Cluster summary",
                "columns": ["cluster_label", "count", "common_evidence", "weakest_wells", "wells"],
                "rows": payload.get("clusters") or [],
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    "Show water mismatch patterns",
                    "Analyze neighborhood around the weakest water well",
                    "Show delta SWAT map with final streamlines",
                    "Show pressure depletion map",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "ClusterMapAgent": {
                "variable": variable,
                "summary": payload.get("summary"),
            }
        },
    }


if __name__ == "__main__":
    for q in [
        "show cluster map",
        "show water mismatch cluster map",
        "show pressure mismatch map",
    ]:
        print("=" * 80)
        print(q)
        r = answer_cluster_map_question(q)
        print(r["intent"] if r else None)
        print(r["answer"] if r else None)
        print(r["data"]["summary"] if r else None)



# ==========================================================
# SIMILARITY CLUSTERING V32
# Groups wells by diagnostic signature, not only by mismatch category.
# No sklearn dependency: deterministic lightweight k-means.
# ==========================================================

def _num(v, default=0.0):
    x = safe_float(v)
    return default if x is None else x


def _scale01(v, min_v, max_v):
    x = safe_float(v)
    if x is None:
        return 0.5
    if max_v == min_v:
        return 0.5
    return max(0.0, min(1.0, (x - min_v) / (max_v - min_v)))


def _direction_code(s):
    s = str(s or "").lower()
    if "too low" in s or "under" in s:
        return -1.0
    if "too high" in s or "over" in s:
        return 1.0
    if "early" in s:
        return 0.75
    if "late" in s:
        return -0.75
    if "negligible" in s:
        return 0.0
    return 0.0


def _timing_code(s):
    s = str(s or "").lower()
    if "early" in s:
        return 1.0
    if "late" in s:
        return -1.0
    if "close" in s:
        return 0.2
    if "no breakthrough" in s:
        return -0.2
    if "negligible" in s:
        return 0.0
    return 0.0


def _build_feature_rows(variable: str = "dominant"):
    rows = load_rows()
    active = []

    for r in rows:
        i = safe_float(r.get("i"))
        j = safe_float(r.get("j"))
        if i is None or j is None:
            continue
        if row_excluded(r):
            continue

        active.append(r)

    if not active:
        return []

    # Ranges for spatial normalization.
    is_ = [_num(r.get("i")) for r in active]
    js_ = [_num(r.get("j")) for r in active]

    min_i, max_i = min(is_), max(is_)
    min_j, max_j = min(js_), max(js_)

    feature_rows = []

    for r in active:
        water_score = _num(r.get("water_hm_score"), 100.0)
        oil_score = _num(r.get("oil_hm_score"), 100.0)
        gas_score = _num(r.get("gas_hm_score"), 100.0)
        bhp_score = _num(r.get("bhp_hm_score"), 100.0)

        # Convert scores into mismatch severity, so high means stronger issue.
        water_bad = (100.0 - water_score) / 100.0
        oil_bad = (100.0 - oil_score) / 100.0
        gas_bad = (100.0 - gas_score) / 100.0
        bhp_bad = (100.0 - bhp_score) / 100.0

        delta_swat_pct = _num(r.get("delta_swat_percentile"), 50.0) / 100.0
        swat_eoh_pct = _num(r.get("mean_swat_eoh_percentile"), 50.0) / 100.0
        dp_pct = _num(r.get("delta_pressure_percentile"), 50.0) / 100.0
        tran_pct = _num(r.get("wellconn_weighted_tran_h_percentile"), 50.0) / 100.0
        perm_pct = _num(r.get("mean_perm_h_percentile"), 50.0) / 100.0
        poro_pct = _num(r.get("mean_poro_percentile"), 50.0) / 100.0

        water_dir = _direction_code(r.get("water_direction") or r.get("water_final_direction"))
        water_timing = _timing_code(r.get("water_timing_issue"))

        # Include spatial features lightly: enough to prefer spatially coherent clusters,
        # not enough to dominate the diagnostic signature.
        spatial_i = _scale01(r.get("i"), min_i, max_i)
        spatial_j = _scale01(r.get("j"), min_j, max_j)

        if variable == "water":
            features = [
                water_bad * 2.0,
                water_dir,
                water_timing,
                delta_swat_pct,
                swat_eoh_pct,
                tran_pct,
                perm_pct,
                dp_pct,
                spatial_i * 0.35,
                spatial_j * 0.35,
            ]
        elif variable == "bhp":
            features = [
                bhp_bad * 2.0,
                dp_pct,
                tran_pct,
                perm_pct,
                poro_pct,
                water_bad * 0.5,
                spatial_i * 0.35,
                spatial_j * 0.35,
            ]
        else:
            features = [
                water_bad,
                oil_bad,
                gas_bad,
                bhp_bad,
                delta_swat_pct,
                dp_pct,
                tran_pct,
                perm_pct,
                poro_pct,
                water_dir,
                water_timing,
                spatial_i * 0.35,
                spatial_j * 0.35,
            ]

        issue, issue_score = dominant_issue(r) if variable == "dominant" else variable_issue(r, variable)

        feature_rows.append({
            "row": r,
            "features": features,
            "issue": issue,
            "issue_score": issue_score,
        })

    return feature_rows


def _euclidean(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _mean_vec(vecs):
    if not vecs:
        return []
    n = len(vecs[0])
    return [sum(v[i] for v in vecs) / len(vecs) for i in range(n)]


def _kmeans(feature_rows, k=4, iterations=25):
    if not feature_rows:
        return []

    n = len(feature_rows)
    k = max(1, min(k, n))

    # Deterministic initialization: take spread across sorted wells.
    ordered = sorted(feature_rows, key=lambda x: str(x["row"].get("well")))
    init_idx = [round(i * (n - 1) / max(k - 1, 1)) for i in range(k)]
    centers = [ordered[i]["features"][:] for i in init_idx]

    labels = [0] * n

    for _ in range(iterations):
        changed = False

        for idx, item in enumerate(feature_rows):
            dists = [_euclidean(item["features"], c) for c in centers]
            new_label = min(range(k), key=lambda j: dists[j])
            if new_label != labels[idx]:
                changed = True
                labels[idx] = new_label

        if not changed:
            break

        for j in range(k):
            members = [feature_rows[i]["features"] for i in range(n) if labels[i] == j]
            if members:
                centers[j] = _mean_vec(members)

    return labels


def _cluster_label_and_driver(members, variable):
    if not members:
        return "Empty cluster", "No members"

    avg_water = avg([100 - _num(m["row"].get("water_hm_score"), 100.0) for m in members])
    avg_oil = avg([100 - _num(m["row"].get("oil_hm_score"), 100.0) for m in members])
    avg_gas = avg([100 - _num(m["row"].get("gas_hm_score"), 100.0) for m in members])
    avg_bhp = avg([100 - _num(m["row"].get("bhp_hm_score"), 100.0) for m in members])

    avg_dswat_pct = avg([_num(m["row"].get("delta_swat_percentile"), 50.0) for m in members])
    avg_dp_pct = avg([_num(m["row"].get("delta_pressure_percentile"), 50.0) for m in members])
    avg_tran_pct = avg([_num(m["row"].get("wellconn_weighted_tran_h_percentile"), 50.0) for m in members])
    avg_perm_pct = avg([_num(m["row"].get("mean_perm_h_percentile"), 50.0) for m in members])

    timings = {}
    dirs = {}
    for m in members:
        t = str(m["row"].get("water_timing_issue") or "").replace("_", " ")
        d = str(m["row"].get("water_direction") or "").replace("_", " ")
        if t:
            timings[t] = timings.get(t, 0) + 1
        if d:
            dirs[d] = dirs.get(d, 0) + 1

    top_timing = max(timings, key=timings.get) if timings else ""
    top_dir = max(dirs, key=dirs.get) if dirs else ""

    # Choose label based on dominant average severity.
    severities = {
        "water": avg_water or 0,
        "oil": avg_oil or 0,
        "gas": avg_gas or 0,
        "pressure": avg_bhp or 0,
    }

    dominant = max(severities, key=severities.get)

    if severities[dominant] < 20:
        label = "Generally good-match cluster"
    elif dominant == "water":
        if "early" in top_timing.lower():
            label = "Early-water mismatch cluster"
        elif "too high" in top_dir.lower() or "over" in top_dir.lower():
            label = "High-water mismatch cluster"
        elif "too low" in top_dir.lower() or "under" in top_dir.lower():
            label = "Low-water mismatch cluster"
        else:
            label = "Water-mismatch cluster"
    elif dominant == "pressure":
        label = "Pressure/BHP mismatch cluster"
    else:
        label = f"{dominant.title()}-mismatch cluster"

    evidence = []

    if avg_dswat_pct is not None and avg_dswat_pct >= 65:
        evidence.append(f"high ΔSWAT percentile (~{avg_dswat_pct:.0f})")
    if avg_dp_pct is not None and avg_dp_pct <= 35:
        evidence.append(f"low pressure-depletion percentile (~{avg_dp_pct:.0f})")
    elif avg_dp_pct is not None and avg_dp_pct >= 65:
        evidence.append(f"high pressure-depletion percentile (~{avg_dp_pct:.0f})")
    if avg_tran_pct is not None and avg_tran_pct >= 65:
        evidence.append(f"high TRAN percentile (~{avg_tran_pct:.0f})")
    if avg_perm_pct is not None and avg_perm_pct >= 65:
        evidence.append(f"high permeability percentile (~{avg_perm_pct:.0f})")
    if top_timing:
        evidence.append(f"common timing signal: {top_timing}")
    if top_dir:
        evidence.append(f"common direction signal: {top_dir}")

    if not evidence:
        evidence.append("no single strong property driver dominates this cluster")

    driver = "; ".join(evidence)

    return label, driver


def build_similarity_cluster_map_payload(variable: str = "dominant") -> Dict[str, Any]:
    feature_rows = _build_feature_rows(variable=variable)

    if not feature_rows:
        return {
            "variable": variable,
            "wells": [],
            "clusters": [],
            "summary": {},
            "message": "No feature rows available for similarity clustering.",
        }

    # Choose k based on number of wells.
    n = len(feature_rows)
    k = 3 if n < 12 else 4 if n < 25 else 5

    labels = _kmeans(feature_rows, k=k)

    clusters = []
    wells = []

    for cid in sorted(set(labels)):
        members = [feature_rows[i] for i, lab in enumerate(labels) if lab == cid]
        label, driver = _cluster_label_and_driver(members, variable)

        member_wells = [m["row"].get("well") for m in members]

        avg_i = avg([safe_float(m["row"].get("i")) for m in members])
        avg_j = avg([safe_float(m["row"].get("j")) for m in members])

        clusters.append({
            "cluster_id": cid,
            "cluster_label": label,
            "count": len(members),
            "avg_i": avg_i,
            "avg_j": avg_j,
            "common_evidence": driver,
            "wells": member_wells,
            "weakest_wells": [
                m["row"].get("well")
                for m in sorted(
                    members,
                    key=lambda z: z.get("issue_score") if z.get("issue_score") is not None else 999
                )[:5]
            ],
        })

    cluster_lookup = {c["cluster_id"]: c for c in clusters}

    for item, cid in zip(feature_rows, labels):
        r = item["row"]
        c = cluster_lookup[cid]

        wells.append({
            "well": r.get("well"),
            "i": safe_float(r.get("i")),
            "j": safe_float(r.get("j")),
            "cluster_id": cid,
            "cluster_label": c["cluster_label"],
            "common_evidence": c["common_evidence"],
            "issue": item["issue"],
            "issue_score": item["issue_score"],
            "overall_score": score(r, "overall_hm_score"),
            "oil_score": score(r, "oil_hm_score"),
            "water_score": score(r, "water_hm_score"),
            "gas_score": score(r, "gas_hm_score"),
            "bhp_score": score(r, "bhp_hm_score"),
            "water_direction": clean_direction(r.get("water_direction") or r.get("water_final_direction")),
            "water_timing": clean_direction(r.get("water_timing_issue")),
            "delta_swat": score(r, "delta_swat"),
            "delta_swat_percentile": score(r, "delta_swat_percentile"),
            "delta_pressure": score(r, "delta_pressure"),
            "delta_pressure_percentile": score(r, "delta_pressure_percentile"),
            "tran_percentile": score(r, "wellconn_weighted_tran_h_percentile"),
            "perm_percentile": score(r, "mean_perm_h_percentile"),
            "poro_percentile": score(r, "mean_poro_percentile"),
        })

    summary = {c["cluster_label"]: c["count"] for c in clusters}

    clusters.sort(key=lambda c: -c["count"])

    return {
        "variable": variable,
        "wells": wells,
        "clusters": clusters,
        "summary": summary,
        "mode": "similarity_signature_clustering",
    }


def build_similarity_cluster_answer(payload: Dict[str, Any]) -> str:
    clusters = payload.get("clusters") or []
    variable = payload.get("variable")

    if not clusters:
        return "I could not identify diagnostic clusters from the available well-level features."

    largest = clusters[0]

    answer = (
        f"I grouped wells by diagnostic similarity, not just by score category. "
        f"The largest pattern is '{largest['cluster_label']}' with {largest['count']} wells. "
        f"Common evidence: {largest['common_evidence']}."
    )

    if len(clusters) > 1:
        second = clusters[1]
        answer += (
            f" A second pattern is '{second['cluster_label']}' with {second['count']} wells, "
            f"with evidence: {second['common_evidence']}."
        )

    answer += " This should help distinguish isolated well problems from repeated/systemic mismatch behavior."

    return answer



# ==========================================================
# WCT BIAS CLUSTERING V38
# Explicit functions for WCT / water-cut over/under-estimation maps.
# ==========================================================

def is_wct_bias_request(message: str) -> bool:
    q = str(message or "").lower()

    triggers = [
        "wct bias",
        "water cut bias",
        "watercut bias",
        "wct map",
        "water cut map",
        "watercut map",
        "wct direction",
        "water cut direction",
        "water mismatch direction",
        "overestimate water",
        "underestimate water",
        "overestimated water",
        "underestimated water",
        "overpredict water",
        "underpredict water",
        "overestimate wct",
        "underestimate wct",
        "overestimated wct",
        "underestimated wct",
        "overestimates wct",
        "underestimates wct",
        "overestimate water cut",
        "underestimate water cut",
        "overestimated water cut",
        "underestimated water cut",
        "overestimates water cut",
        "underestimates water cut",
        "model overestimates water",
        "model underestimates water",
        "model overestimates water cut",
        "model underestimates water cut",
        "simulated too high water",
        "simulated too low water",
        "sovrastima water",
        "sottostima water",
        "sovrastima acqua",
        "sottostima acqua",
    ]

    return any(t in q for t in triggers)


def _clean_flag_v38(value):
    return str(value or "").strip().replace("_", " ")


def _is_excluded_v38(row):
    if str(row.get("exclude_from_hm") or "").lower() in ["true", "1", "yes"]:
        return True
    if str(row.get("inactive_producer_zero_oil_history") or "").lower() in ["true", "1", "yes"]:
        return True
    if str(row.get("well_activity_status") or "").lower().startswith("inactive"):
        return True
    return False


def classify_wct_bias(row):
    """
    User-facing WCT bias classification.
    Direction is interpreted from model/simulation perspective:
    - simulated_too_low  => model underestimates WCT
    - simulated_too_high => model overestimates WCT
    """
    direction = str(
        row.get("water_direction") or
        row.get("water_final_direction") or
        row.get("water_recent_2yr_direction") or
        ""
    ).lower()

    timing = str(row.get("water_timing_issue") or "").lower()
    water_score = safe_float(row.get("water_hm_score"))

    negligible = (
        "negligible" in direction
        or str(row.get("water_negligible_match") or "").lower() in ["true", "1", "yes"]
        or str(row.get("water_status") or "").lower().startswith("not_evaluated")
    )

    if negligible:
        return "Negligible WCT / no material issue"

    if "simulated_too_low" in direction or "too low" in direction or "under" in direction:
        return "Model underestimates WCT"

    if "simulated_too_high" in direction or "too high" in direction or "over" in direction:
        return "Model overestimates WCT"

    if "early" in timing:
        return "Model overestimates WCT / early water"

    if "late" in timing or "no_breakthrough" in timing:
        return "Model underestimates WCT / late water"

    if water_score is None:
        return "WCT not evaluated"

    if water_score >= 75:
        return "Balanced WCT"

    return "Weak WCT match, direction unclear"


def wct_bias_code(label):
    order = {
        "Balanced WCT": 0,
        "Model underestimates WCT": 1,
        "Model underestimates WCT / late water": 1,
        "Model overestimates WCT": 2,
        "Model overestimates WCT / early water": 2,
        "Weak WCT match, direction unclear": 3,
        "Negligible WCT / no material issue": 4,
        "WCT not evaluated": 5,
        "Inactive / excluded": 6,
    }
    return order.get(label, 5)


def _first_float_v38(row, keys):
    for k in keys:
        v = safe_float(row.get(k))
        if v is not None:
            return v
    return None


def build_wct_bias_cluster_payload():
    rows = load_rows()
    wells = []

    for r in rows:
        i = safe_float(r.get("i"))
        j = safe_float(r.get("j"))

        if i is None or j is None:
            continue

        if _is_excluded_v38(r):
            bias = "Inactive / excluded"
        else:
            bias = classify_wct_bias(r)

        sim_wct = _first_float_v38(r, [
            "wct_override_max_sim_wct",
            "max_sim_wct_for_override",
            "wct_override_sim_wct",
            "water_max_sim_signal",
        ])

        obs_wct = _first_float_v38(r, [
            "wct_override_max_obs_wct",
            "max_obs_wct_for_override",
            "wct_override_obs_wct",
            "water_max_hist_signal",
        ])

        wells.append({
            "well": r.get("well"),
            "i": i,
            "j": j,
            "bias": bias,
            "bias_code": wct_bias_code(bias),
            "water_score": safe_float(r.get("water_hm_score")),
            "overall_score": safe_float(r.get("overall_hm_score")),
            "oil_score": safe_float(r.get("oil_hm_score")),
            "gas_score": safe_float(r.get("gas_hm_score")),
            "bhp_score": safe_float(r.get("bhp_hm_score")),
            "water_direction": _clean_flag_v38(r.get("water_direction") or r.get("water_final_direction")),
            "water_timing": _clean_flag_v38(r.get("water_timing_issue")),
            "sim_wct": sim_wct,
            "obs_wct": obs_wct,
            "delta_swat": safe_float(r.get("delta_swat")),
            "delta_swat_percentile": safe_float(r.get("delta_swat_percentile")),
            "mean_swat_eoh_percentile": safe_float(r.get("mean_swat_eoh_percentile")),
            "delta_pressure": safe_float(r.get("delta_pressure")),
            "delta_pressure_percentile": safe_float(r.get("delta_pressure_percentile")),
            "tran_percentile": safe_float(r.get("wellconn_weighted_tran_h_percentile")),
            "perm_percentile": safe_float(r.get("mean_perm_h_percentile")),
            "poro_percentile": safe_float(r.get("mean_poro_percentile")),
        })

    summary = {}
    for w in wells:
        summary[w["bias"]] = summary.get(w["bias"], 0) + 1

    bias_groups = []
    for bias, count in summary.items():
        pts = [w for w in wells if w["bias"] == bias]
        if not pts:
            continue

        bias_groups.append({
            "bias": bias,
            "count": count,
            "avg_i": avg([p["i"] for p in pts]),
            "avg_j": avg([p["j"] for p in pts]),
            "avg_water_score": avg([p["water_score"] for p in pts]),
            "avg_delta_swat_percentile": avg([p["delta_swat_percentile"] for p in pts]),
            "avg_tran_percentile": avg([p["tran_percentile"] for p in pts]),
            "avg_perm_percentile": avg([p["perm_percentile"] for p in pts]),
            "wells": [p["well"] for p in pts],
            "weakest_wells": [
                p["well"] for p in sorted(
                    pts,
                    key=lambda x: x["water_score"] if x["water_score"] is not None else 999
                )[:6]
            ],
        })

    bias_groups.sort(key=lambda x: -x["count"])

    under = (
        summary.get("Model underestimates WCT", 0)
        + summary.get("Model underestimates WCT / late water", 0)
    )
    over = (
        summary.get("Model overestimates WCT", 0)
        + summary.get("Model overestimates WCT / early water", 0)
    )

    if under > over and under > 0:
        interpretation = (
            f"The dominant WCT bias is underestimation: {under} wells show simulated WCT lower/later than observed. "
            "This points toward insufficient water movement or delayed water breakthrough in those areas."
        )
    elif over > under and over > 0:
        interpretation = (
            f"The dominant WCT bias is overestimation: {over} wells show simulated WCT higher/earlier than observed. "
            "This points toward too aggressive water movement or too strong local/regional connectivity in those areas."
        )
    elif under == over and under > 0:
        interpretation = (
            f"The field shows mixed WCT bias: {under} wells underestimating and {over} wells overestimating WCT. "
            "A single field-wide water-mobility correction may improve one area and damage another."
        )
    else:
        interpretation = (
            "No strong WCT bias family dominates the active wells. Many wells are balanced, negligible, or direction-unclear."
        )

    return {
        "mode": "wct_bias_cluster_map",
        "variable": "water",
        "wells": wells,
        "summary": summary,
        "bias_groups": bias_groups,
        "interpretation": interpretation,
    }


def answer_wct_bias_cluster_question(message: str):
    if not is_wct_bias_request(message):
        return None

    payload = build_wct_bias_cluster_payload()
    groups = payload.get("bias_groups") or []
    answer = payload.get("interpretation", "I built the WCT bias pattern map.")

    if groups:
        strongest = groups[0]
        weakest = ", ".join(str(x) for x in strongest.get("weakest_wells", [])[:6])
        answer += f" Largest group: '{strongest.get('bias')}' with {strongest.get('count')} wells."
        if weakest:
            answer += f" Weakest examples: {weakest}."

    return {
        "type": "visual_response",
        "answer": answer,
        "intent": "wct_bias_cluster_map",
        "ui_blocks": [
            {
                "type": "wct_bias_cluster_map",
                "title": "WCT Bias Pattern Map",
                "payload": payload,
            },
            {
                "type": "compact_table",
                "title": "WCT bias groups",
                "columns": [
                    "bias",
                    "count",
                    "avg_water_score",
                    "avg_delta_swat_percentile",
                    "avg_tran_percentile",
                    "weakest_wells",
                ],
                "rows": groups,
            },
            {
                "type": "suggestions",
                "title": "Suggested follow-up",
                "items": [
                    "Show WCT underestimated areas over delta SWAT",
                    "Show WCT overestimated areas over permeability",
                    "Analyze neighborhood around the weakest underestimated WCT well",
                    "Compare underestimating and overestimating WCT clusters",
                ],
            },
        ],
        "data": payload,
        "agent_trace": {
            "WCTBiasClusterAgentV38": {
                "summary": payload.get("summary"),
                "mode": "wct_bias_cluster_map",
            }
        },
    }
