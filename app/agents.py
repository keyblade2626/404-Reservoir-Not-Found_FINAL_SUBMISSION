import os
from typing import Any, Dict, List

from app.compass_client import call_compass_chat
from app.history_match import build_history_match_kpis


def is_sample_mode() -> bool:
    return os.getenv("SAMPLE_MODE", "false").lower() == "true"


class PlannerAgent:
    name = "PlannerAgent"

    def run(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        plan = {
            "objective": (
                "Read native reservoir simulation summary files, compare simulated and historical vectors, "
                "and generate well-level and model-level history-match KPIs."
            ),
            "query": query,
            "input_files": ["CASE.SMSPEC", "CASE.UNSMRY"],
            "focus_variables": ["oil", "watercut", "gor", "bhp_optional"],
            "focus_vectors": [
                "WOPR / WOPRH",
                "WOPT / WOPTH",
                "WWCT / WWCTH",
                "WGOR / WGORH",
                "WBHP / WBHPH if available"
            ],
            "steps": [
                "Load native SMSPEC/UNSMRY summary files.",
                "Inspect available simulated and historical vectors.",
                "Compare simulated and historical profiles at well level.",
                "Evaluate oil, water cut, GOR and pressure if historical pressure is available.",
                "Calculate full-history profile similarity.",
                "Calculate last-two-years profile similarity, or all available history if the well has less than two years.",
                "Calculate final cumulative or final value mismatch.",
                "Combine variable-level scores into well-level HM scores.",
                "Aggregate well-level HM scores into model-level HM score.",
                "Produce final structured JSON output."
            ],
            "success_criteria": [
                "Use native SMSPEC/UNSMRY data.",
                "Compare simulated and historical vectors when both are available.",
                "Evaluate oil, water cut, GOR and optionally BHP.",
                "Do not penalize pressure if historical BHP is unavailable.",
                "Give higher importance to profile trend similarity than final cumulative mismatch.",
                "Evaluate both full-history trend and last-two-years trend.",
                "Return well-level and model-level history-match KPIs.",
                "Clearly flag Good, Fair and Poor history-match wells."
            ],
            "scoring_logic": {
                "variable_score_components": {
                    "full_history_trend_similarity": 0.50,
                    "recent_two_year_trend_similarity": 0.30,
                    "final_cumulative_or_final_value_match": 0.20
                },
                "well_score_weights": {
                    "oil": 0.40,
                    "watercut": 0.30,
                    "gor": 0.20,
                    "bhp": 0.10
                },
                "classification": {
                    "Good": "score >= 80",
                    "Fair": "60 <= score < 80",
                    "Poor": "score < 60"
                }
            },
            "context": context,
        }

        if not is_sample_mode():
            prompt = f"""
Create a concise reservoir history-match diagnostic plan for this request:

{query}

The system reads native SMSPEC/UNSMRY summary files and compares simulated and historical vectors.
Focus on oil, water cut, GOR, and pressure only if observed pressure is available.
The score should prioritize profile similarity over final cumulative mismatch.
Return a compact plan with objective, variables, evidence checks, and expected outputs.
"""
            try:
                compass_plan = call_compass_chat(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a reservoir engineering planning agent specialized in history-match quality review."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        },
                    ],
                    max_tokens=600,
                )
                plan["compass_plan"] = compass_plan
            except Exception as exc:
                plan["compass_warning"] = (
                    f"Compass planning call failed, local plan used: {type(exc).__name__}"
                )

        return plan


class SummaryImportAgent:
    name = "SummaryImportAgent"

    def run(self) -> Dict[str, Any]:
        return build_history_match_kpis()


class ReservoirDiagnosticAgent:
    name = "ReservoirDiagnosticAgent"

    def run(self, plan: Dict[str, Any], hm_payload: Dict[str, Any]) -> Dict[str, Any]:
        findings: List[Dict[str, Any]] = []

        well_results = hm_payload.get("well_results", {})

        for well, payload in well_results.items():
            hm_score = payload.get("hm_score")
            hm_class = payload.get("hm_class")
            variables = payload.get("variables", {})

            if hm_score is None:
                continue

            weak_variables = []
            medium_variables = []
            unavailable_variables = []
            evidence = []

            for variable_name, result in variables.items():
                score = result.get("score")
                status = result.get("status")

                if status != "evaluated":
                    unavailable_variables.append(
                        {
                            "variable": variable_name,
                            "reason": result.get("reason", "Not available")
                        }
                    )
                    continue

                components = result.get("components", {})

                if score is not None and score < 60:
                    weak_variables.append(variable_name)
                    evidence.append(
                        f"{variable_name} match is Poor: score={score}, "
                        f"full_history_trend={components.get('full_trend_score')}, "
                        f"recent_2yr_trend={components.get('recent_2yr_trend_score')}, "
                        f"final_or_cumulative_match={components.get('final_score')}."
                    )

                elif score is not None and score < 80:
                    medium_variables.append(variable_name)
                    evidence.append(
                        f"{variable_name} match is Fair: score={score}, "
                        f"full_history_trend={components.get('full_trend_score')}, "
                        f"recent_2yr_trend={components.get('recent_2yr_trend_score')}, "
                        f"final_or_cumulative_match={components.get('final_score')}."
                    )

            if hm_score < 80 or weak_variables or medium_variables:
                severity = "high" if hm_score < 60 or weak_variables else "medium"

                findings.append(
                    {
                        "well": well,
                        "issue": "Weak or uncertain history-match quality detected.",
                        "hm_score": hm_score,
                        "hm_class": hm_class,
                        "weak_variables": weak_variables,
                        "medium_variables": medium_variables,
                        "unavailable_variables": unavailable_variables,
                        "evidence": evidence,
                        "variable_scores": {
                            name: result.get("score")
                            for name, result in variables.items()
                        },
                        "variable_classes": {
                            name: result.get("class")
                            for name, result in variables.items()
                        },
                        "confidence": 0.85 if evidence else 0.65,
                        "severity": severity,
                    }
                )

        return {
            "analysis_type": "history_match_quality_diagnostics",
            "source_type": hm_payload.get("source_type"),
            "model_hm_score": hm_payload.get("model_hm_score"),
            "model_hm_class": hm_payload.get("model_hm_class"),
            "variable_availability": hm_payload.get("variable_availability"),
            "hm_summary": hm_payload.get("summary"),
            "well_results": hm_payload.get("well_results"),
            "findings": findings,
            "finding_count": len(findings),
            "revision_applied": False,
        }

    def revise(self, draft: Dict[str, Any], critique: Dict[str, Any]) -> Dict[str, Any]:
        revised = draft.copy()
        revised_findings = []

        for finding in draft.get("findings", []):
            updated = finding.copy()

            weak_variables = set(updated.get("weak_variables", []))
            medium_variables = set(updated.get("medium_variables", []))
            all_problem_variables = weak_variables.union(medium_variables)

            recommended_checks = []

            if "oil" in all_problem_variables:
                recommended_checks.extend(
                    [
                        "Check whether oil-rate mismatch is caused by well controls, constraints, shut-ins or actual reservoir behavior.",
                        "Compare final oil cumulative mismatch with the full oil-rate trend similarity.",
                        "Review local pressure depletion and completion status before modifying model properties."
                    ]
                )

            if "watercut" in all_problem_variables:
                recommended_checks.extend(
                    [
                        "Check simulated versus historical water breakthrough timing.",
                        "Review water-cut trend in the last two years of history match.",
                        "Add well connections and nearby PERMX/PERMY/TRANX context to explain excessive or delayed water movement.",
                        "Review injector-producer connectivity and possible high-permeability water channels."
                    ]
                )

            if "gor" in all_problem_variables:
                recommended_checks.extend(
                    [
                        "Check simulated versus historical GOR trend and gas rise timing.",
                        "Review possible gas-cap communication, gas mobility, completion intervals and drawdown strategy.",
                        "Check whether gas mismatch is local to the well or regional across nearby producers."
                    ]
                )

            if "bhp" in all_problem_variables:
                recommended_checks.extend(
                    [
                        "Check whether historical BHP data is reliable and consistently measured.",
                        "Compare BHP mismatch with nearby wells and pressure-support mechanisms.",
                        "Review transmissibility, aquifer support, injection support and well controls."
                    ]
                )

            if not recommended_checks:
                recommended_checks.append(
                    "Add observed data, well connections and property context before applying model-calibration changes."
                )

            updated["recommended_checks"] = recommended_checks
            updated["revision_reason"] = critique.get(
                "main_issue",
                "Evaluator requested stronger engineering recommendations and clearer next checks."
            )

            revised_findings.append(updated)

        revised["findings"] = revised_findings
        revised["revision_applied"] = True
        revised["revision_summary"] = (
            "Added variable-specific engineering checks for weak history-match wells."
        )

        return revised


class EvaluatorAgent:
    name = "EvaluatorAgent"

    def run(
        self,
        plan: Dict[str, Any],
        analysis: Dict[str, Any],
        final_review: bool = False,
    ) -> Dict[str, Any]:
        findings = analysis.get("findings", [])
        variable_availability = analysis.get("variable_availability", {})

        if not findings:
            return {
                "approved": True,
                "quality_score": 0.78,
                "main_issue": None,
                "critique": (
                    "No weak history-match wells detected under current thresholds. "
                    "Review variable availability to confirm enough historical vectors were present."
                ),
                "requires_revision": False,
                "variable_availability": variable_availability,
            }

        missing_recommendations = [
            f["well"] for f in findings if not f.get("recommended_checks")
        ]

        if missing_recommendations and not final_review:
            return {
                "approved": False,
                "quality_score": 0.62,
                "main_issue": "Findings include HM evidence but lack actionable reservoir-engineering checks.",
                "critique": f"Add recommended checks for wells: {', '.join(missing_recommendations)}.",
                "requires_revision": True,
                "variable_availability": variable_availability,
            }

        weak_evidence = [
            f["well"] for f in findings if len(f.get("evidence", [])) < 1
        ]

        if weak_evidence:
            return {
                "approved": False,
                "quality_score": 0.55,
                "main_issue": "Some HM findings do not include enough evidence.",
                "critique": f"Strengthen evidence for wells: {', '.join(weak_evidence)}.",
                "requires_revision": True,
                "variable_availability": variable_availability,
            }

        return {
            "approved": True,
            "quality_score": 0.88,
            "main_issue": None,
            "critique": (
                "Findings include history-match scores, weak variables, evidence components "
                "and follow-up reservoir-engineering checks."
            ),
            "requires_revision": False,
            "variable_availability": variable_availability,
        }


class ReportWriterAgent:
    name = "ReportWriterAgent"

    def run(
        self,
        request_id: str,
        query: str,
        plan: Dict[str, Any],
        summary_payload: Dict[str, Any],
        analysis: Dict[str, Any],
        evaluation: Dict[str, Any],
        agents_used: List[str],
        trace_id: str,
    ) -> Dict[str, Any]:
        findings = analysis.get("findings", [])
        model_score = analysis.get("model_hm_score")
        model_class = analysis.get("model_hm_class")
        hm_summary = analysis.get("hm_summary", {})
        variable_availability = analysis.get("variable_availability", {})

        summary = (
            f"Native SMSPEC/UNSMRY history-match review completed. "
            f"Model HM score: {model_score} ({model_class}). "
            f"Good wells: {hm_summary.get('good_count', 0)}, "
            f"Fair wells: {hm_summary.get('fair_count', 0)}, "
            f"Poor wells: {hm_summary.get('poor_count', 0)}."
        )

        human_readable_report = [
            "Native SMSPEC/UNSMRY files were read successfully.",
            f"Model history-match score: {model_score} ({model_class}).",
            f"Good wells: {hm_summary.get('good_wells', [])}.",
            f"Fair wells: {hm_summary.get('fair_wells', [])}.",
            f"Poor wells: {hm_summary.get('poor_wells', [])}.",
            "Oil, water cut and GOR are evaluated when both simulated and historical vectors are available.",
            "BHP is evaluated only when historical pressure vectors are available; otherwise it is excluded from the HM score.",
            "Variable score logic: 50% full-history profile similarity, 30% recent two-year profile similarity, 20% final cumulative/final-value match."
        ]

        for variable_name, availability in variable_availability.items():
            human_readable_report.append(
                f"{variable_name}: evaluated for {availability.get('evaluated_well_count', 0)} wells; "
                f"unavailable for {availability.get('unavailable_well_count', 0)} wells."
            )

        for finding in findings[:10]:
            human_readable_report.append(
                f"{finding['well']}: HM score {finding['hm_score']} ({finding['hm_class']}), "
                f"weak variables: {finding.get('weak_variables', [])}, "
                f"fair variables: {finding.get('medium_variables', [])}."
            )

        return {
            "request_id": request_id,
            "trace_id": trace_id,
            "status": "success",
            "sample_mode": is_sample_mode(),
            "agents_used": agents_used,
            "result": {
                "project": "404 Reservoir Not Found",
                "summary": summary,
                "human_readable_report": human_readable_report,
                "objective": plan["objective"],
                "source_type": summary_payload.get("source_type"),
                "model_hm_score": model_score,
                "model_hm_class": model_class,
                "variable_availability": variable_availability,
                "hm_summary": hm_summary,
                "findings": findings,
                "well_results": analysis.get("well_results"),
                "evaluation": evaluation,
                "confidence": evaluation.get("quality_score", 0.0),
            },
            "collaboration": {
                "feedback_loop_completed": analysis.get("revision_applied", False),
                "revision_count": 1 if analysis.get("revision_applied", False) else 0,
                "evaluator_findings": [
                    evaluation.get("critique")
                ],
            },
            "log_path": "logs/agent_trace.jsonl",
        }
