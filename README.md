# 404 Reservoir Not Found

## Problem, Target User and Demo Video

Reservoir engineers often spend significant time comparing simulated and observed field behaviour, identifying mismatch drivers and deciding which variables to change in order to get a better 3D reservoir model calibration. This project addresses that workflow by turning preprocessed reservoir simulation results into an interactive AI copilot for history-match diagnosis.

The target user is a reservoir engineer reviewing a dynamic model. The system helps the engineer inspect oil, water, gas and BHP match quality, ask natural-language questions, generate visual evidence, compare hypotheses such as RelPerm versus TRAN/connectivity, and review the agent trace behind each answer.

Demo video:

	https://youtu.be/4mHldFevx20?si=p-xcf2QyDYfD4QMq

## Running the Project

The project can be run in two ways:

1. Locally with Python
2. Through Docker

For the competition review, the recommended starting point is the already imported demo dashboard, because the demo case already includes the generated diagnostic artifacts, example outputs and final logs.

Open:

    http://localhost:8000/demo-dashboard

The full landing page is available at:

    http://localhost:8000/

---

## Option A - Run Locally with Python

Create and activate a virtual environment:

    py -m venv .venv
    .\.venv\Scripts\Activate.ps1

Install dependencies:

    python -m pip install -r requirements.txt

Run the application:

    python run.py

Then open:

    http://localhost:8000/
    http://localhost:8000/demo-dashboard

Recommended Python version:

    Python 3.13 or higher

If using an older Python version, a different compatible resdata version may be required.

---

## Option B - Run with Docker

Docker is supported through the included Dockerfile.

Build the image:

    docker build -t 404-reservoir-not-found:latest .

Run the container without secrets:

    docker run --name 404-reservoir-not-found-demo -p 8000:8000 404-reservoir-not-found:latest

Then open:

    http://localhost:8000/
    http://localhost:8000/demo-dashboard

This mode is enough to inspect:

- the landing page;
- the demo dashboard;
- KPI cards;
- history-match maps;
- well-level diagnostics;
- recommendations;
- official examples;
- final logs.

To inspect Docker logs:

    docker logs 404-reservoir-not-found-demo --tail 200

To follow logs live:

    docker logs -f 404-reservoir-not-found-demo

To stop the container:

    docker stop 404-reservoir-not-found-demo

To remove and recreate the container:

    docker rm -f 404-reservoir-not-found-demo
    docker run --name 404-reservoir-not-found-demo -p 8000:8000 404-reservoir-not-found:latest

---

## Compass / LLM Chatbox Environment Variables

The repository intentionally does not include a local .env file.

This is required for security:

- .env may contain private API keys;
- .env is excluded by .gitignore;
- .env is excluded by .dockerignore;
- .env.example is included only as a safe template.

The dashboard demo can run without .env.

However, the AI chatbox / Compass LLM generation requires a Compass API key supplied at runtime.

Create a local .env file from the template:

    copy .env.example .env

Then edit .env and set:

    COMPASS_API_KEY=<your_compass_api_key>
    HOST=0.0.0.0
    PORT=8000

Run Docker with the environment file:

    docker rm -f 404-reservoir-not-found-demo
    docker run --name 404-reservoir-not-found-demo --env-file .env -p 8000:8000 404-reservoir-not-found:latest

Then open:

    http://localhost:8000/demo-dashboard

Important:

    If Docker is started without --env-file .env, the dashboard demo remains available, but Compass/LLM chat responses may be disabled or limited because no API key was supplied.

The API key is never stored in the repository or in the Docker image. It is provided only at runtime through:

    --env-file .env

---

## LLM Final Answer Writer

The Ask Reservoir AI workflow includes a final user-facing answer writer.

Specialist reservoir tools first collect structured evidence such as profile behaviour, WCT bias, pressure/BHP indicators, TRAN/connectivity evidence, property indicators and hypothesis scores. The final answer writer then synthesizes this evidence into a concise reservoir-engineering explanation.

This final writer is intentionally separate from the specialist tools:

- specialist tools generate evidence;
- the critic validates and ranks hypotheses;
- the final writer turns the validated evidence into clear user-facing language.

The final writer is designed to avoid raw tool narration such as:

    I built an interactive chart...
    I loaded the profile...
    This is a...

Instead, it produces a cleaner answer structure:

    1. Conclusion
    2. Key evidence
    3. Hypothesis ranking
    4. Recommended next checks

When a Compass/OpenAI-compatible LLM key is available, the final writer uses the configured LLM endpoint to polish the final response. If no LLM key is available, the app falls back safely without breaking the dashboard.

This language-cleanup layer does not modify the underlying diagnostic evidence, visual panels, logs or agent traces. It only improves the final user-facing answer.

## Suggested Reviewer Workflow

For a fast review:

    docker build -t 404-reservoir-not-found:latest .
    docker run --name 404-reservoir-not-found-demo -p 8000:8000 404-reservoir-not-found:latest

Open:

    http://localhost:8000/demo-dashboard

For full Compass/LLM chatbox testing:

    copy .env.example .env

Add a valid COMPASS_API_KEY to .env, then run:

    docker rm -f 404-reservoir-not-found-demo
    docker run --name 404-reservoir-not-found-demo --env-file .env -p 8000:8000 404-reservoir-not-found:latest

Open:

    http://localhost:8000/demo-dashboard

---

## Reservoir AI Copilot for History-Match Diagnosis and Interactive Reservoir Model Review

404 Reservoir Not Found is an interactive reservoir-engineering copilot built for the G42 Agentathon. It helps a reservoir engineer move from raw simulation results to structured history-match interpretation.

The system allows the user to:

- inspect a preloaded reservoir demo case;
- review oil, water, gas and bottom-hole pressure history-match KPIs;
- identify critical wells and mismatch drivers;
- ask natural-language technical questions;
- generate maps, plots and visual evidence;
- understand which agents/tools were involved in the answer;
- generate candidate simulation input updates for selected model properties.

The main idea is simple:

> Simple questions should stay simple. Diagnostic reservoir questions should trigger deeper multi-agent reasoning.

The copilot does not force every request through the same fixed pipeline. It dynamically selects direct answer mode, single-tool mode or multi-agent diagnostic mode depending on the question.

---

## 1. Installation

Python 3.13 or higher is recommended.

From the repository root, create and activate a virtual environment if desired, then install the required packages:

```bash
pip install -r requirements.txt
```

Important note about `resdata`:

```text
The submitted environment was tested with Python 3.13 or higher.
If using an older Python version, the dependency resdata==6.2.9 may require a different compatible version depending on local wheels and operating system support.
```

If installation fails specifically on `resdata`, check the local Python version first and then adjust the `resdata` version only if needed.

---

## 2. Recommended Quick Start for Judges

For this competition, judges are strongly encouraged to use the already prepared demo workflow.

From the repository root:

```bash
python run.py
```

Then open the landing page:

```text
http://localhost:8000/
```

or open the demo dashboard directly:

```text
http://localhost:8000/demo-dashboard
```

The submitted demo case has already completed the import and diagnostic post-processing workflow. Therefore, judges do not need to manually import a reservoir simulation folder in order to evaluate the dashboard, the KPIs, the Ask Reservoir AI copilot, the visual outputs or the agent traces.

Recommended judge flow:

1. Start the server with `python run.py`.
2. Open `http://localhost:8000/demo-dashboard`.
3. Explore the KPI cards, well map and well insight panel.
4. Click wells on the map to inspect well-level diagnostics.
5. Use the `Ask Reservoir AI` chatbox to ask technical questions.
6. Scroll down to inspect the agent collaboration trace.

If you click `Back to Case Import` from the dashboard, you will return to the landing page. To go back to the demo dashboard, simply click `Open Dashboard` again, or use the direct demo dashboard link above.

---

## 3. Full Reservoir Simulation Workflow

The project also supports a complete workflow for users who have access to a reservoir model simulated with INTERSECT / IX.

This full workflow is available from the landing page:

```text
http://localhost:8000/
```

The intended process is:

1. Open the landing page.
2. Use the case import workflow to prepare the required output configuration before running the simulation.
3. Run the reservoir simulation externally.
4. Upload the completed simulation result folder.
5. The application parses the simulation outputs automatically.
6. The system extracts the relevant raw files, including summary vectors and grid/property outputs.
7. The case is activated.
8. The deterministic diagnostic pipeline rebuilds the derived KPI and diagnosis files.
9. The dashboard becomes available with maps, KPIs, well diagnostics, recommendations, chat and agent traces.

The import and parsing workflow can take a few minutes. Runtime depends on the model size and the amount of simulation output. Several local tests showed typical completion times ranging from a few minutes up to approximately 5-6 minutes.

For this Agentathon submission, the recommended evaluation path is still the preloaded demo case because it has already completed the import, parsing and diagnostic generation process.

---

## 4. What Happens During Case Import and Activation

The completed-run import extracts and prepares the raw reservoir files used by the dashboard and tools, such as:

```text
CASE.SMSPEC
CASE.UNSMRY
PORO.GRDECL
PERM_X.GRDECL
PERM_Y.GRDECL
PERM_Z.GRDECL
PRESSURE_INIT.GRDECL
PRESSURE_EOH.GRDECL
SWAT_INIT.GRDECL
SWAT_EOH.GRDECL
SOIL_INIT.GRDECL
SOIL_EOH.GRDECL
TRANX.GRDECL
TRANY.GRDECL
TRANZ.GRDECL
WELL_CONNECTIONS.ixf
```

After `Activate case`, the application runs the existing deterministic diagnostic post-processing pipeline. This rebuilds the derived diagnosis artifacts used by the dashboard and specialist agents:

```text
artifacts/diagnosis/well_property_driver_context.csv
artifacts/diagnosis/water_driver_diagnosis.json
artifacts/diagnosis/driver_diagnosis_summary.json
artifacts/diagnosis/oil_profile_diagnostics.json
artifacts/diagnosis/gas_profile_diagnostics.json
artifacts/diagnosis/bhp_profile_diagnostics.json
artifacts/diagnosis/bhp_observed_filter_report.json
artifacts/diagnosis/well_activity_classification.json
artifacts/diagnosis/well_activity_classification.csv
artifacts/diagnosis/smart_well_recommendations.json
artifacts/diagnosis/smart_well_recommendations.csv
```

These files are generated by deterministic reservoir scripts. They are not fabricated by the LLM.

The pipeline includes:

```text
app.driver_diagnosis
app.export_oil_profile_diagnostics
app.export_gas_profile_diagnostics
app.export_bhp_profile_diagnostics
app.bhp_observed_filter
app.well_activity_classifier
app.smart_well_recommendation_agent
```

While activation is running, the landing page displays a loading message because this process may take a few minutes.

---

## 5. Dashboard Guide

Once the dashboard is open, the user has access to several reservoir-engineering views.

### Top KPI section

The top section contains calculated history-match KPIs for the main reservoir variables:

```text
Oil
Water
Gas
Bottom-hole pressure / BHP
```

These KPI cards summarize the overall quality of the history match and help identify which variable is driving the mismatch.

### Interactive well map

The map uses colors to highlight which wells are more critical in terms of mismatch.

Clicking a well opens well-level diagnostics, including:

- well-level KPI indicators;
- phase-specific mismatch quality;
- criticality interpretation;
- relevant local evidence;
- recommended technical checks.

### Well Insight panel

The `Well Insight` panel provides detailed information for the selected well. It is intended to help the reservoir engineer quickly understand which phase or variable is problematic and whether the mismatch is material.

### Recommendations and model update actions

Below the well insight section, the dashboard provides recommendations and the reasoning path used to arrive at those recommendations.

This section includes action buttons that can generate new candidate simulation input files. These files are intended to test targeted model updates, for example changes to selected properties that may improve the history match.

The tool does not blindly modify properties. It evaluates whether the available evidence supports changing a given property before suggesting or generating a candidate update.

### Ask Reservoir AI chatbox

The `Ask Reservoir AI` chatbox is the core of the project.

It allows the user to ask questions such as:

```text
Why is HW-28 water mismatch happening?
Which wells have the weakest pressure match and what do they have in common?
Show TRAN multiplier corridor for HW-28.
Show me HW-25 oil production.
Is HW-6 really a water mismatch or is water negligible?
What model updates would you prioritize to improve the history match?
```

The chatbox can:

- explain criticalities on specific wells;
- plot maps and profiles;
- compare simulated-vs-observed behaviour;
- investigate water, gas, oil or pressure mismatch;
- check connectivity and TRAN evidence;
- help the reservoir engineer understand what is wrong in the model history match;
- provide integrated root-cause diagnosis;
- support model update prioritization.

### Agent collaboration trace

At the bottom of the dashboard, an agent trace section shows which agents/tools were involved in answering a question.

This makes the reasoning path more transparent and auditable. For simple questions, only a small number of steps should appear. For causal reservoir diagnosis, more specialist agents and interaction edges are expected.

---

## 6. Local URLs

After starting the app:

```bash
python run.py
```

use:

```text
http://localhost:8000/
```

Direct dashboard:

```text
http://localhost:8000/demo-dashboard
```

API endpoint:

```text
POST http://localhost:8000/run
```

Equivalent local loopback URLs may also work:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/demo-dashboard
```

---

## 7. CLI Usage

The project also supports file-based CLI execution.

Example:

```bash
python run.py --input input_examples/example_1.json --output output_examples/example_1_output.json
```

Expected input format:

```json
{
  "message": "Why is HW-28 water mismatch happening?"
}
```

The output includes:

- status;
- answer;
- response type;
- task type;
- visual block types;
- agent trace;
- interaction edges;
- collaboration summary;
- raw response.

---

## 8. API Behaviour

The local `/run` endpoint accepts a JSON payload.

Example:

```json
{
  "message": "Give me an executive summary of the history match quality."
}
```

Expected behaviour:

- The server returns a successful JSON response.
- Reservoir-specific requests are routed to specialist tools.
- Multi-agent diagnostic requests include interaction edges.
- Visual requests return UI blocks for dashboard rendering.
- Invalid wells are guarded and should not silently fall back to unrelated wells.

---

## 9. Environment Variables

The repository includes:

```text
.env.example
```

Do not commit real API keys.

The system supports Compass/Core42 or OpenAI-compatible API routing.

Recommended local configuration for generation testing:

```text
SAMPLE_MODE=false

COMPASS_API_KEY=your-compass-api-key-here
COMPASS_API_BASE_URL=https://api.core42.ai/v1
COMPASS_BASE_URL=https://api.core42.ai/v1

OPENAI_API_KEY=your-compass-api-key-here
OPENAI_BASE_URL=https://api.core42.ai/v1

COMPASS_MODEL=gpt-4.1
COMPASS_REASONING_MODEL=gpt-5.1
CHAT_MODEL=gpt-4.1
REASONING_MODEL=gpt-5.1
EMBEDDING_MODEL=text-embedding-3-large

HOST=0.0.0.0
PORT=8000
```

The official Agentathon checklist may reference:

```text
OPENAI_BASE_URL=https://compass.core42.ai/v1
```

During local testing, the working Compass-compatible generation gateway observed for generation requests was:

```text
https://api.core42.ai/v1
```

For this reason, the submitted application does not hardcode the endpoint. It reads the base URL from environment variables.

Important:

- No API key is hardcoded in the repository.
- The local `.env` file must not be committed.
- `.env.example` contains placeholders only.
- The application fails gracefully if the LLM endpoint is unavailable.
- Reservoir-specific local demo workflows remain available, but full general chat and LLM planning require a working Compass/OpenAI-compatible generation endpoint.

---

## 10. Architecture Summary

High-level flow:

```text
User question
  -> Web dashboard / CLI / API
  -> Copilot orchestrator
  -> Direct answer OR specialist tool plan OR multi-agent diagnosis
  -> Specialist reservoir tools
  -> Critic / hypothesis ranking
  -> Final answer synthesizer
  -> Final visual selector
  -> Dashboard response + logs
```

The system dynamically chooses one of several modes:

1. Direct answer mode.
2. Single specialist tool mode.
3. Multi-agent diagnostic mode.
4. Guard / clarification mode.

---

## 11. Why This Is Not a Fixed Pipeline

The system does not call all agents for every request.

Example:

```text
5+7
```

Expected behaviour:

```text
Direct answer.
No reservoir tools.
```

Example:

```text
Show me HW-25 oil production
```

Expected behaviour:

```text
Copilot -> profile specialist -> profile visual.
```

Example:

```text
Is the HW-28 water issue more likely caused by connectivity or relative permeability?
```

Expected behaviour:

```text
Copilot planner
  -> integrated diagnosis
  -> profile evidence
  -> WCT / water evidence
  -> TRAN / connectivity evidence
  -> pressure / BHP indicators
  -> critic ranking
  -> final synthesis
  -> final visual evidence
```

This distinction is intentional. More agents are used only when they add diagnostic value.

---

## 12. Agentic Components

Important components include:

### LLMCopilotBrainV800

Semantic planner for general chat, reservoir routing and tool-plan generation.

### EvidencePlannerV800

Builds the reservoir evidence plan for specialist tools.

### DynamicProfileAgentToolV800

Generates simulated-vs-observed profile evidence for oil, gas, water, WCT and pressure.

### WCTBiasDiagnosticAgentToolV800

Analyses water-cut bias, water mismatch and spatial water behaviour.

### TRANCorridorVisualAgentToolV800

Provides TRAN/connectivity corridor evidence and supports transmissibility multiplier reasoning.

### StreamlineTimesliceVisualAgentToolV800

Provides streamline and communication evidence.

### IntegratedReservoirDiagnosisToolV800

Combines profile, WCT, pressure and property indicators into integrated diagnosis.

### ReservoirCriticAgentV807

Ranks hypotheses. When structured numeric hypothesis scores are available, it uses those scores instead of keyword counting.

### FinalAnswerSynthesizerV800

Produces the final user-facing reservoir-engineering explanation.

### UserFacingAnswerPolisherV803

Removes internal tool names from the main answer while preserving traceability in logs.

### VisualEvidenceStabilizerV806

Deduplicates and stabilizes visual evidence blocks.

### FinalVisualSelectorV810

Selects the most appropriate final visual evidence for the question.

---

## 13. Final Visual Selection Logic

The dashboard does not simply show every possible visual block. The final visual evidence is selected according to the question.

| User request | Final visual |
|---|---|
| Show me HW-25 oil production | Profile plot |
| Show TRAN multiplier corridor for HW-28 | TRAN corridor map |
| Show WCT bias cluster map | WCT map |
| Is HW-28 more likely connectivity or RelPerm? | Evidence board and hypothesis ranking table |

This avoids misleading visual emphasis. A TRAN map should not dominate a RelPerm-vs-connectivity diagnosis if the structured hypothesis ranking supports RelPerm as the stronger hypothesis.

---

## 14. Interaction Edges

Each response can expose `interaction_edges`.

These represent runtime interactions between:

- user;
- copilot planner;
- evidence planner;
- specialist tools;
- critic;
- final synthesizer;
- visual selector.

Typical edge counts:

| Request type | Typical edges |
|---|---:|
| Direct answer | 2-3 |
| Single specialist visual | 5-7 |
| Multi-agent diagnosis | 12-27 |

The number of edges is not a quality metric by itself. The important behaviour is that simple requests stay simple, while diagnostic requests trigger deeper collaboration.

---

## 15. Suggested Live Demo Questions

### General / direct

```text
5+7
Where is Rome?
What is a reservoir?
Explain transmissibility in reservoir simulation.
```

### Profiles

```text
Show me HW-25 oil production.
Plot gas cumulative for HW-25.
Plot oil, gas and water for HW-25 together.
```

### History-match summary

```text
Give me an executive summary of the history match quality.
```

### Water and WCT diagnosis

```text
Why is HW-28 water mismatch happening?
Explain HW-6 water mismatch using profile, pressure, TRAN and WCT evidence.
Is HW-6 really a water mismatch or is water negligible?
Check if WCT mismatch aligns spatially with TRAN/PERM corridors.
```

### Connectivity and TRAN

```text
Show TRAN multiplier corridor for HW-28.
Show streamlines and explain connectivity.
Where would you test a transmissibility multiplier and why?
```

### Pressure

```text
Which wells have the weakest pressure match and what do they have in common?
Show the same analysis for pressure.
```

### Model update prioritization

```text
What model updates would you prioritize to improve the history match?
Is the HW-28 water issue more likely caused by connectivity or relative permeability?
```

### Guard tests

```text
Show me HW-250 oil production.
Why is HWW-25 water mismatch happening?
```

Expected guard behaviour:

- Invalid well names should not silently fall back to another well.
- The system should return closest available suggestions when possible.

---

## 16. Official Input / Output Examples

Required folders:

```text
input_examples/
output_examples/
```

The repository contains four official examples:

```text
input_examples/example_1.json
input_examples/example_2.json
input_examples/example_3.json
input_examples/example_4.json

output_examples/example_1_output.json
output_examples/example_2_output.json
output_examples/example_3_output.json
output_examples/example_4_output.json
```

The current official examples are designed to demonstrate:

1. Integrated HW-28 water mismatch root-cause diagnosis.
2. Ranked model-update action plan across the demo case.
3. Integrated pressure/BHP weakness diagnosis.
4. Invalid well guard and safe fallback behaviour.

These examples are intentionally diagnostic and multi-agent, not simple single-tool plot requests.


Example 4 demonstrates the invalid-well guard. It verifies that a request for `HW-250` does not silently fall back to another well. The system validates the well name, blocks the unsafe substitution, suggests valid alternatives and returns a guarded response.


Regenerate official examples:

```bash
python scripts/create_stronger_official_examples.py
```

---

## 17. Final Logs

The final `logs/` folder should remain clean and focused.

Expected final logs:

    logs/submission_agent_interaction_summary.md
    logs/official_examples_interaction_summary.json
    logs/v700_official_examples_summary.json
    logs/example_1_agent_trace.json
    logs/example_2_agent_trace.json
    logs/example_3_agent_trace.json
    logs/example_4_agent_trace.json
    logs/trace-example-001.jsonl
    logs/trace-example-002.jsonl
    logs/trace-example-003.jsonl
    logs/trace-example-004.jsonl

The `example_*_agent_trace.json` files provide rich runtime traces for each official example.

The `trace-example-*.jsonl` files satisfy the required Agentathon trace format:

    logs/trace-<run_id>.jsonl

Each JSONL line contains the required fields:

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

The logs demonstrate:

- routing mode;
- selected tools;
- agent trace;
- interaction edges;
- delegation decisions;
- critic / validation steps;
- guard and fallback behaviour;
- visual block types;
- collaboration summary;
- answer preview.

Large debug traces and temporary server logs are not required in the final submission.

---

## 18. Required File Checklist

The repository should contain:

```text
run.py
metadata.json
.env.example
README.md
ARCHITECTURE.md
input_examples/
output_examples/
logs/
```

Validation command:

```bash
python scripts/validate_submission_files.py
```

Expected result:

```text
All required submission files look present and valid.
```

---

## 19. Final Submission Checks

Recommended checks before submission:

```bash
python -m py_compile app/main.py
python -m py_compile app/final_answer_synthesizer_llm.py
python -m py_compile app/diagnostics_pipeline.py
python -m py_compile app/langgraph_universal_orchestrator_v501.py
python -m py_compile app/universal_reservoir_orchestrator_v500.py
python -m py_compile app/hm_report_v600.py
python -m py_compile run.py

python scripts/validate_submission_files.py
python scripts/create_stronger_official_examples.py
```

Then run:

```bash
python run.py
```

Open:

```text
http://localhost:8000/
http://localhost:8000/demo-dashboard
```

---

## 20. Troubleshooting

### Dashboard does not load

Run:

```bash
python run.py
```

Open:

```text
http://localhost:8000/
```

or:

```text
http://localhost:8000/demo-dashboard
```

### After clicking Back to Case Import, how do I return to the dashboard?

From the landing page, click:

```text
Open Dashboard
```

or use:

```text
http://localhost:8000/demo-dashboard
```

### Activation appears to take time

This is expected for a full imported IX case. The system activates the raw model files and rebuilds diagnostic artifacts.

The landing page shows:

```text
Activating case and rebuilding diagnostics...
This may take a few minutes. Please keep this page open.
```

### General chat does not answer questions like "where is Rome?"

Check `.env` and LLM connectivity.

Required:

```text
COMPASS_API_KEY
COMPASS_BASE_URL or COMPASS_API_BASE_URL
COMPASS_MODEL or CHAT_MODEL
```

or:

```text
OPENAI_API_KEY
OPENAI_BASE_URL
```

### Playwright / PDF export fails

The dashboard itself does not require PDF export. If local PDF export is used, Playwright/Chromium may require local installation and valid certificates. This is optional for the main demo.

### Invalid well returns a profile

This should not happen. Test:

```text
Show me HW-250 oil production.
Why is HWW-25 water mismatch happening?
```

Expected:

```text
Invalid well guard with closest available suggestions.
```

---

## 21. Design Principles

1. Dynamic routing over fixed pipeline.
2. Single-tool simplicity for simple requests.
3. Multi-agent reasoning for causal questions.
4. Structured evidence over keyword bias.
5. User-facing clarity.
6. Visual intent matters.
7. Guard invalid inputs.
8. Preserve good matches.
9. Keep raw simulation parsing deterministic.
10. Keep diagnosis artifacts auditable.

---

## 22. Submission Summary

404 Reservoir Not Found is a reservoir-engineering copilot that combines natural-language chat, specialist reservoir tools, visual evidence, deterministic simulation post-processing and critic-based diagnostic synthesis.

It is intended to help a reservoir engineer move from raw history-match results to structured technical interpretation:

```text
What is matching?
What is not matching?
Which phase is responsible?
Which wells or areas are critical?
Which model update should be tested first?
What evidence supports that decision?
```

The system provides both user-facing explanations and machine-readable interaction traces so that the reasoning path is visible, testable and auditable.


