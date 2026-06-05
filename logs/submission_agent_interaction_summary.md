# Official Examples - Agent Interaction Summary

These logs were regenerated after enabling the LLM Final Answer Writer.

The final writer polishes validated specialist evidence into clearer reservoir-engineering language while preserving visual evidence and machine-readable traces.

- Passed: **4**
- Failed: **0**

| Example | Purpose | Pass | Task | Tools | Edges | Visuals |
|---|---|---:|---|---:|---:|---|
| `example_1` | Integrated HW-28 water mismatch root-cause diagnosis | yes | `v800_llm_planned_reservoir_multi_agent` | 11 | 17 | compact_table, compact_table |
| `example_2` | Ranked model-update action plan across the demo case | yes | `v804_model_update_action_plan` | 11 | 27 | compact_table, compact_table, compact_table, compact_table, wct_bias_cluster_map |
| `example_3` | Integrated pressure/BHP weakness diagnosis | yes | `v800_llm_planned_reservoir_multi_agent` | 11 | 12 | compact_table, plotly_chart |
| `example_4` | Invalid well guard and safe fallback behaviour | yes | `invalid_well_name_final_v601` | 6 | 7 | suggestions |

## Required JSONL trace files

- `logs/trace-example-001.jsonl`
- `logs/trace-example-002.jsonl`
- `logs/trace-example-003.jsonl`
- `logs/trace-example-004.jsonl`

Each JSONL line contains the required fields:

```text
timestamp
run_id
agent_name
action
input_summary
output_summary
target_agent
confidence
retry_count
status
```

## Example answer previews

### example_1 - Integrated HW-28 water mismatch root-cause diagnosis

```text
This is a model-specific reservoir diagnosis. I compared the available profile, WCT-bias, TRAN/connectivity and property evidence before ranking the most likely causes. Main evidence: - Integrated diagnosis: For HW-28, the strongest current hypothesis is **RelPerm / endpoint saturation issue** (score 85.0). The second hypothesis is **Connectivity / TRAN issue** (score 46.7). Evidence summary: oil score 100.0, water/WCT score 20.23, gas score 98.45, BHP score 70.69. WCT pattern: Model underestimates WCT; timing/direction: breakthrough timing close / simulated too low. Profile evidence override: water-profile totals sim=6.2e+04, obs=6.96e+05. This is a... - Water-cut / spatial bias evidence: I built an interactive WCT profile for HW-28. WCT is computed as water rate divided by oil plus water rate. - Profile evidence: I loaded the relative permeability and capillary-pressure curves for HW-28 in relperm model Model_04. Select the curve group to inspect. A Krw water-mobility sensitivity is available for this well; use the Evaluate/Export button if you want to generate the modified curve candidate. Reservoir Technical review review: HW-28 also has TRAN / connectivity evidence in the smart recommendation. Do not apply a RelPerm curve change blindly if the main issue may be ... Hypothesis ranking: - Relative permeability / water mobility: support score 85.0 — oil match is good while...
```

### example_2 - Ranked model-update action plan across the demo case

```text
Recommended model-update priorities based on the integrated evidence: 1. **Start with water/WCT behaviour**, because oil and gas matches are generally strong while water/WCT is the weakest dimension. This points to water movement, breakthrough timing, water mobility or local connectivity rather than a field-wide hydrocarbon volumetric issue. 2. **Separate connectivity/TRAN candidates from RelPerm/water-mobility candidates.** Wells where TRAN/PERM/corridor evidence is material should be tested with transmissibility or connectivity sensitivities before applying RelPerm-only tuning. 3. **Use pressure/BHP as a consistency check.** If water mismatch and BHP mismatch appear together, connectivity, pressure support or boundary/aquifer representation should be reviewed before changing only saturation functions. 4. **Prioritize local, evidence-backed edits.** Avoid broad global multipliers unless the mismatch is clearly systematic across the field. The safest workflow is to test targeted TRAN/corridor edits and RelPerm sensitivities separately, then compare impact on water, BHP, oil and gas. 5. **Preserve the good oil/gas match.** Any update that improves water but degrades oil or gas should be rejected or constrained. Supporting integrated evidence is summarized below. This is a model-specific reservoir diagnosis. I compared the available profile, WCT-bias, TRAN/connectivity and pro...
```

### example_3 - Integrated pressure/BHP weakness diagnosis

```text
This is a model-specific reservoir diagnosis. I compared the available profile, WCT-bias, TRAN/connectivity and property evidence before ranking the most likely causes. Main evidence: - History-match summary evidence: Created interactive distribution plot for PRESSURE from 34390 map-cell values. - Integrated diagnosis: I ranked the top 5 wells requiring model review using integrated water/WCT, BHP/pressure, gas/GOR and oil evidence. Hypothesis ranking: - profile level / timing mismatch: support score 2 — Supported by direct simulated-vs-observed water/WCT profile evidence. - pressure / BHP support or connectivity: support score 2 — Supported when BHP/pressure evidence is part of the mismatch. - local connectivity / TRAN: support score 0 — Supported when TRAN/connectivity/corridor evidence is present. - relative permeability / water mobility: support score 0 — Supported when timing/shape suggest mobility/endpoints rather than only connectivity. Most likely explanation: profile level / timing mismatch.
```

### example_4 - Invalid well guard and safe fallback behaviour

```text
I found an explicit well name that is invalid or ambiguous for the active reservoir. I did not run the request on another well or on a default well because that would be misleading. HW-250 is not a valid well in the active dataset. Well not found in active reservoir well registry. Closest available wells: HW-25, HW-5, HW-32, HW-30, HW-29, HW-28.
```
