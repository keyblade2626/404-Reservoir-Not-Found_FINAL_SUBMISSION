from typing import Dict, List


AGENTS = [
    {
        "name": "Data Ingestion Agent",
        "role": "Validate reservoir input files and prepare shared artifact memory.",
        "inputs": ["SMSPEC/UNSMRY", "GRDECL properties", "WELL_CONNECTIONS.IXF", "SLN streamlines"],
        "outputs": ["artifact availability report"],
        "tools": ["filesystem", "Python file discovery"],
        "handoff_to": "HM Scoring Agent",
    },
    {
        "name": "HM Scoring Agent",
        "role": "Compute history match quality for oil, water, gas and BHP.",
        "inputs": ["SMSPEC/UNSMRY", "well profiles"],
        "outputs": ["artifacts/diagnosis/well_property_driver_context.csv"],
        "tools": ["resdata", "Python scoring functions"],
        "handoff_to": "Profile Diagnostics Agent",
    },
    {
        "name": "Well Activity Classification Agent",
        "role": "Classify wells as active/inactive producers or injectors based on observed oil production and observed water/gas injection.",
        "inputs": ["SMSPEC/UNSMRY", "well_property_driver_context.csv"],
        "outputs": ["well_activity_classification.json", "well_activity_classification.csv", "updated well_property_driver_context.csv"],
        "tools": ["resdata", "Python activity classifier"],
        "handoff_to": "Profile Diagnostics Agent",
    },
    {
        "name": "Profile Diagnostics Agent",
        "role": "Classify oil, gas and BHP profile direction, timing and bias.",
        "inputs": ["well_property_driver_context.csv", "SMSPEC/UNSMRY"],
        "outputs": [
            "oil_profile_diagnostics.json",
            "gas_profile_diagnostics.json",
            "bhp_profile_diagnostics.json",
        ],
        "tools": ["resdata", "profile diagnostics"],
        "handoff_to": "Injection HM Agent",
    },
    {
        "name": "BHP Observed Data Filter Agent",
        "role": "Remove BHP from HM averaging when observed BHP data is missing.",
        "inputs": ["SMSPEC/UNSMRY", "well_property_driver_context.csv"],
        "outputs": ["bhp_observed_filter_report.json", "updated well_property_driver_context.csv"],
        "tools": ["resdata", "Python BHP availability filter"],
        "handoff_to": "Injection HM Agent",
    },
    {
        "name": "Injection HM Agent",
        "role": "Evaluate injector history match and injection mismatch direction.",
        "inputs": ["SMSPEC/UNSMRY", "injector profiles"],
        "outputs": ["artifacts/injection_hm/injection_hm_results.json"],
        "tools": ["Python injector scoring"],
        "handoff_to": "Streamline Alignment Agent",
    },
    {
        "name": "Streamline Alignment Agent",
        "role": "Parse, align and snap INIT/EOH streamlines to producer wells.",
        "inputs": ["STREAMLINES_INIT.SLN*", "STREAMLINES_EOH.SLN*", "well locations"],
        "outputs": ["cluster_snap_streamline_connections.json"],
        "tools": ["Fortran binary reader", "geometric alignment", "streamline snapping"],
        "handoff_to": "Injector-Producer Context Agent",
    },
    {
        "name": "Injector-Producer Context Agent",
        "role": "Connect producer mismatch with injector behavior and streamline support.",
        "inputs": ["streamline connections", "injection_hm_results.json", "well_property_driver_context.csv"],
        "outputs": ["producer_injector_water_context.json"],
        "tools": ["Python context builder"],
        "handoff_to": "Reservoir Diagnosis Agent",
    },
    {
        "name": "Reservoir Diagnosis Agent",
        "role": "Integrate HM scores, profile direction, properties, injection and streamlines into diagnosis.",
        "inputs": ["HM context", "profile diagnostics", "properties", "streamline context"],
        "outputs": ["final_hm_diagnosis.json", "final_oil_diagnosis.json", "final_gas_diagnosis.json"],
        "tools": ["rule-based reservoir reasoning", "property correlation"],
        "handoff_to": "Recommendation Agent",
    },
    {
        "name": "Recommendation Agent",
        "role": "Convert diagnosis into candidate reservoir engineering actions.",
        "inputs": ["final diagnosis", "streamline corridors", "TRAN/MULT properties"],
        "outputs": ["candidate_transmissibility_corridors.json", "candidate cells CSV"],
        "tools": ["corridor rasterization", "transmissibility screening"],
        "handoff_to": "Visualization Agent",
    },
    {
        "name": "Visualization Agent",
        "role": "Generate dashboard-ready maps, profile plots and visual evidence.",
        "inputs": ["diagnosis artifacts", "map payload", "profile series"],
        "outputs": ["HM map payload", "profile PNGs", "dashboard JSON"],
        "tools": ["Matplotlib", "SVG dashboard renderer", "Plotly optional"],
        "handoff_to": "Chat Copilot Agent",
    },
    {
        "name": "Chat Copilot Agent",
        "role": "Route natural-language reservoir questions to the right artifacts and visual evidence.",
        "inputs": ["user question", "shared artifact memory"],
        "outputs": ["answer", "evidence", "plot/map reference"],
        "tools": ["intent router", "artifact lookup", "Compass API when configured"],
        "handoff_to": None,
    },
]


def get_agent_flow() -> Dict:
    return {
        "agents": AGENTS,
        "interaction_model": (
            "Agents interact through shared artifact memory and explicit handoff logs. "
            "Each agent consumes prior artifacts, produces new evidence, and registers its handoff."
        ),
        "llm_policy": (
            "Deterministic reservoir calculations are performed by Python tools. "
            "Natural-language reasoning/summarization is routed through Compass API when configured."
        ),
    }


def get_agent_by_name(name: str):
    for agent in AGENTS:
        if agent["name"] == name:
            return agent
    return None
