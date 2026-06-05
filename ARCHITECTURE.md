# Architecture - 404 Reservoir Not Found

## 1. Executive Overview

404 Reservoir Not Found is a reservoir-engineering AI copilot built for the G42 Agentathon. It combines a local demo dashboard, natural-language chat, specialist reservoir analysis tools, visual evidence generation, critic-based hypothesis ranking and runtime interaction traces.

The system is designed for reservoir history-match review and model diagnosis. It helps the user move from raw simulated-vs-observed results to structured technical interpretation.

The central architecture principle is:

    Simple questions should stay simple.
    Diagnostic questions should trigger deeper multi-agent reasoning.

Therefore, the system is not a fixed hardcoded pipeline. It dynamically routes each user request into the minimum reasoning workflow required:

- Direct answer mode for general or simple questions.
- Single specialist tool mode for simple visual requests.
- Multi-agent diagnostic mode for causal/root-cause questions.
- Guard mode for invalid or ambiguous requests.

The submitted demo case is preloaded. Judges do not need to manually import raw reservoir files in order to evaluate the dashboard.

---

## 2. Runtime Entry Points

Main local server command:

    python run.py

Landing page:

    http://127.0.0.1:8000

Direct dashboard:

    http://127.0.0.1:8000/demo-dashboard

### Recommended Judge Path

For contest review, the recommended path is to open the ready-to-use demo dashboard directly:

    http://127.0.0.1:8000/demo-dashboard

The landing page remains available for the full INTERSECT / IX workflow, where a user can prepare required files, run the simulator externally, import a completed run folder, activate the case and rebuild diagnostic artifacts. This full workflow is useful for real reservoir cases, but it is not required for judging the bundled demo.


Programmatic API endpoint:

    POST /run

CLI mode:

    python run.py --input input_examples/example_1.json --output output_examples/example_1_output.json

Expected API / CLI input:

    {
      "message": "Why is HW-28 water mismatch happening?"
    }

Expected output includes:

- status
- answer
- response type
- task type
- visual block types
- agent trace
- interaction edges
- collaboration summary
- raw response payload

---

## 3. High-Level System Flow

The high-level flow is:

    User question
      -> Web dashboard / CLI / API
      -> run.py
      -> FastAPI application
      -> Copilot orchestrator
      -> Routing decision
      -> Direct answer OR specialist tool OR multi-agent diagnosis
      -> Final answer synthesizer
      -> Final visual selector
      -> Dashboard response + logs

The copilot orchestrator decides how much reasoning is required. A simple plot request does not call all diagnostic agents. A causal question triggers evidence gathering from multiple specialist tools and critic-based synthesis.

---

## 4. Main Runtime Modes

### 4.1 Direct Answer Mode

Used for:

- General questions.
- Simple calculations.
- Conceptual explanations.
- Non-reservoir questions.

Examples:

    5+7
    Where is Rome?
    What is a reservoir?

Expected behaviour:

- No reservoir specialist tool is called.
- The system answers directly using the LLM when available or deterministic local fallback when applicable.
- The response contains only a light interaction trace.

---

### 4.2 Single Specialist Tool Mode

Used for simple reservoir visual or data requests.

Examples:

    Show me HW-25 oil production
    Plot gas cumulative for HW-25
    Show TRAN multiplier corridor for HW-28
    Show WCT bias cluster map

Expected behaviour:

- One specialist reservoir tool is selected.
- The response returns the requested visual evidence.
- No unnecessary multi-agent diagnosis is triggered.

This is intentional. A direct plot request should not produce a heavy diagnostic workflow.

---

### 4.3 Multi-Agent Diagnostic Mode

Used for causal, comparative or interpretive reservoir questions.

Examples:

    Why is HW-28 water mismatch happening?
    Is the HW-28 water issue more likely caused by connectivity or relative permeability?
    What model updates would you prioritize to improve the history match?
    Which wells have the weakest pressure match and what do they have in common?

Expected behaviour:

- The planner creates an evidence plan.
- Multiple specialist tools are called.
- Evidence is passed to a critic.
- Hypotheses are ranked.
- The final answer is synthesized in reservoir-engineering language.
- The most coherent visual evidence is selected for the dashboard.

This is the main agentic value of the system.

---

### 4.4 Guard / Clarification Mode

Used for:

- Invalid well names.
- Typo well names.
- Ambiguous prompts.
- Requests that cannot be safely answered from available data.

Examples:

    Show me HW-250 oil production
    Why is HWW-25 water mismatch happening?
    show me something interesting

Expected behaviour:

- The system does not silently substitute another well.
- It returns a guard response or clarification.
- Closest valid well suggestions may be returned when possible.

---

## 5. Web Dashboard Architecture

The dashboard provides the main user experience.

It contains:

- Landing / case import page.
- Direct demo access.
- Back to Case Import button.
- Reservoir map panel.
- Well Insight panel.
- Ask Reservoir AI chatbox.
- Quick action buttons.
- Chat answer panel.
- Visual / Evidence panel.
- Agent Collaboration Trace panel.

The dashboard route is:

    /demo-dashboard

The Back to Case Import button is a simple link to:

    /

The Ask Reservoir AI section uses:

    section.panel.ask-panel
    input#chatInput
    button#askBtn
    div#chatAnswer

The dashboard is designed to show both the final user-facing answer and the evidence that supports it.

---

## 6. Backend Application Layer

The backend is served by the local Python application.

Responsibilities:

- Load environment variables.
- Serve the local landing page and dashboard.
- Expose the /run endpoint.
- Support CLI input/output execution.
- Dispatch user messages to the copilot orchestrator.
- Return answer, UI blocks, trace and raw response payload.

Main command:

    python run.py

API endpoint:

    POST /run

CLI example:

    python run.py --input input_examples/example_1.json --output output_examples/example_1_output.json

---

## 7. Copilot Orchestrator

The copilot orchestrator is the central coordination layer.

Its responsibilities are:

- Interpret user intent.
- Detect reservoir-specific questions.
- Detect well names and variables.
- Validate well availability.
- Decide whether the request is direct, single-tool, diagnostic or guarded.
- Select specialist tools.
- Collect evidence.
- Pass evidence to the critic.
- Synthesize the final answer.
- Select final visual evidence.
- Record interaction edges and agent trace.

The orchestrator supports both LLM-planned routing and deterministic local fallback for key demo workflows.

---

## 8. Agentic Components

### 8.1 LLMCopilotBrainV800

Role:

- Semantic interpretation of the user question.
- General direct chat when appropriate.
- Reservoir intent planning.
- Tool-plan generation for model-specific questions.

This component helps avoid rigid keyword-only behaviour.

---

### 8.2 EvidencePlannerV800

Role:

- Converts reservoir questions into an evidence plan.
- Selects the specialist tools required for the specific question.
- Avoids over-calling tools when the request is simple.

Example:

    Show me HW-25 oil production

Expected plan:

    DynamicProfileAgentTool only

Example:

    Why is HW-28 water mismatch happening?

Expected plan:

    Integrated diagnosis
    Profile evidence
    WCT / water evidence
    TRAN / connectivity evidence
    Pressure / BHP indicators
    Critic synthesis

---

### 8.3 DynamicProfileAgentToolV800

Role:

- Generate simulated-vs-observed well profile evidence.
- Support oil, gas, water, WCT and BHP trends.
- Support cumulative profiles where applicable.

Used for:

- Simple profile plots.
- Evidence collection for mismatch diagnosis.
- Comparison of simulated and observed behaviour.

---

### 8.4 WCTBiasDiagnosticAgentToolV800

Role:

- Diagnose water-cut and water mismatch.
- Identify whether simulated water/WCT is above or below observed.
- Provide WCT bias and spatial water evidence.

Used when the question involves:

- Water mismatch.
- WCT behaviour.
- Breakthrough timing.
- Water underprediction or overprediction.

---

### 8.5 TRANCorridorVisualAgentToolV800

Role:

- Provide TRAN/connectivity corridor evidence.
- Support transmissibility multiplier reasoning.
- Help evaluate local connectivity hypotheses.

Used when the question involves:

- TRAN multiplier.
- Connectivity.
- Corridor testing.
- Local transmissibility uncertainty.

---

### 8.6 StreamlineTimesliceVisualAgentToolV800

Role:

- Provide streamline or communication evidence.
- Help interpret dynamic connectivity paths.
- Support connectivity-oriented questions.

---

### 8.7 IntegratedReservoirDiagnosisToolV800

Role:

- Combine profile, pressure, WCT and property indicators.
- Produce integrated diagnostic evidence.
- Provide structured hypothesis ranking where available.

Typical evidence includes:

- oil match score
- gas match score
- water/WCT score
- BHP/pressure score
- WCT bias direction
- pressure delta
- TRAN percentile
- PERM percentile
- PORO percentile
- Delta SWAT indicator
- recommended next checks

---

### 8.8 ReservoirCriticAgentV807

Role:

- Review evidence collected from specialist tools.
- Rank hypotheses.
- Resolve contradictions between narrative text and structured evidence.

Important V807 behaviour:

When structured numeric hypothesis scores are available, the critic uses those numeric scores instead of keyword counting.

Example:

    RelPerm / endpoint saturation issue = 85
    Connectivity / TRAN issue = 46.7

Expected result:

    Leading hypothesis = RelPerm / water mobility
    Secondary check = connectivity / TRAN

This prevents the final answer from being biased by repeated words such as TRAN or connectivity in supporting text.

---

### 8.9 FinalAnswerSynthesizerV800

Role:

- Produce the final answer.
- Convert evidence into reservoir-engineering interpretation.
- Summarize recommended next checks.
- Keep the answer readable for end users.

---

### 8.10 UserFacingAnswerPolisherV803

Role:

- Improve user-facing wording.
- Replace internal tool names with readable labels.
- Keep technical agent names in trace/logs rather than the main answer.

Example:

    IntegratedReservoirDiagnosisToolV800

is presented to the user as:

    Integrated diagnosis

---

### 8.11 VisualEvidenceStabilizerV806

Role:

- Deduplicate visual evidence blocks.
- Avoid repeated or unstable visuals.
- Preserve technical evidence while improving dashboard usability.

---

### 8.12 FinalVisualSelectorV810

Role:

- Select the final visual evidence most coherent with the user question.

Examples:

| User request | Final visual |
|---|---|
| Show me HW-25 oil production | Profile plot |
| Show TRAN multiplier corridor for HW-28 | TRAN corridor map |
| Show WCT bias cluster map | WCT map |
| Is HW-28 more likely connectivity or RelPerm? | Evidence board and hypothesis ranking table |

This avoids misleading visual emphasis. A TRAN map should not dominate a RelPerm-vs-connectivity diagnosis if the structured hypothesis ranking supports RelPerm as the stronger hypothesis.

### 8.13 LLMFinalAnswerWriter

Role:

- Convert validated multi-agent evidence into a clean final user-facing answer.
- Remove raw tool narration from the final answer.
- Keep charts, evidence boards and structured traces separate from the written explanation.
- Improve readability without changing the underlying diagnostic evidence.

The final writer receives:

- user question
- raw tool-aggregated answer
- structured response payload
- visual/evidence metadata
- hypothesis ranking and critic output where available

It then produces a concise reservoir-engineering response with the following structure:

    1. Conclusion
    2. Key evidence
    3. Hypothesis ranking
    4. Recommended next checks

The final writer should not say that it created charts, maps or tables. Those visuals are already displayed in the dashboard evidence panel. The answer should focus on interpretation.

If a Compass/OpenAI-compatible model is configured, this step is LLM-backed. If no model endpoint is available, deterministic fallback behaviour preserves the original response without breaking the dashboard.

This component improves user-facing clarity while preserving technical traceability.

---

## 9. Interaction Edges

The system records interaction_edges for auditability.

Edges represent runtime interactions between:

- user
- copilot planner
- evidence planner
- specialist tools
- critic
- final synthesizer
- visual selector

Typical edge counts:

| Request type | Typical edges |
|---|---:|
| Direct answer | 2-3 |
| Single specialist visual | 5-7 |
| Multi-agent diagnosis | 12-27 |

The number of edges is not a quality metric by itself. The important behaviour is that simple requests stay simple, while diagnostic requests trigger deeper collaboration.

---

## 10. Visual Evidence Flow

Visual evidence flow:

    Specialist tool output
      -> UI block generation
      -> Visual evidence stabilizer
      -> Final visual selector
      -> Dashboard renderer

The system can produce:

- profile series
- cumulative profile charts
- compact tables
- WCT bias maps
- TRAN corridor maps
- streamline maps
- suggestions
- integrated evidence boards
- hypothesis ranking tables

The final visual selector chooses the visual that best matches the user intent.

---

## 11. Data Flow

The demo data is preloaded and used by local reservoir tools.

Data categories include:

- simulated rates
- observed rates
- cumulative profiles
- well names
- spatial grid information
- pressure indicators
- WCT indicators
- TRAN/connectivity proxies
- property indicators
- history-match scores
- integrated diagnostic indicators

The user does not need to import raw Petrel, Eclipse or simulator files to run the submitted demo.

---


## 11A. Imported Case Activation and Deterministic Diagnostics

For a full INTERSECT / IX workflow, the import step extracts raw simulation outputs into the local sample-model structure. When the user clicks Activate case, the application runs the deterministic diagnostics pipeline to rebuild the dashboard artifacts.

The diagnostic pipeline reads the imported raw files and writes the derived evidence under:

    artifacts/diagnosis/

Important generated artifacts include:

    well_property_driver_context.csv
    water_driver_diagnosis.json
    driver_diagnosis_summary.json
    oil_profile_diagnostics.json
    gas_profile_diagnostics.json
    bhp_profile_diagnostics.json
    bhp_observed_filter_report.json
    well_activity_classification.json
    well_activity_classification.csv
    smart_well_recommendations.json
    smart_well_recommendations.csv

These artifacts are generated by deterministic reservoir scripts, not by the LLM. The LLM and specialist agents then use these auditable artifacts as evidence for dashboard explanations and Ask Reservoir AI responses.

The bundled demo already includes the required prepared artifacts, so judges can use the direct dashboard immediately.

## 12. LLM and Compass Integration

The system supports Compass/Core42 or OpenAI-compatible APIs.

Important environment variables:

    COMPASS_API_KEY
    COMPASS_API_BASE_URL
    COMPASS_BASE_URL
    OPENAI_API_KEY
    OPENAI_BASE_URL
    COMPASS_MODEL
    CHAT_MODEL
    REASONING_MODEL
    EMBEDDING_MODEL
    SAMPLE_MODE
    HOST
    PORT

When LLM access is available:

- The system also uses a final LLM answer writer to polish validated reservoir evidence into concise user-facing language.

- General chat works naturally.
- Reservoir planning is semantic.
- Tool plans are dynamically generated.
- Model-specific questions are routed to specialist tools.

When LLM access is not available:

- Simple local calculations can still work.
- Reservoir demo workflows remain available where local tools/data are present.
- Arbitrary general knowledge is not fabricated.

This behaviour is intentional and avoids pretending to answer general questions without a valid model call.

---

## 13. Official Input / Output Examples

Required folders:

    input_examples/
    output_examples/

The final official examples are:

    input_examples/example_1.json
    input_examples/example_2.json
    input_examples/example_3.json
    input_examples/example_4.json

    output_examples/example_1_output.json
    output_examples/example_2_output.json
    output_examples/example_3_output.json
    output_examples/example_4_output.json

The current official examples are intentionally diagnostic, multi-agent and guard-oriented:

1. Integrated HW-28 water mismatch root-cause diagnosis.
2. Ranked model-update action plan across the demo case.
3. Integrated pressure/BHP weakness diagnosis.
4. Invalid well guard and safe fallback behaviour.

Regenerate examples 1-3:

    python scripts/create_stronger_official_examples.py

Example 4 is the invalid-well guard/fallback validation. It demonstrates that the system blocks `HW-250`, avoids silently substituting another well and suggests valid alternatives.

Expected final official summary:

    Passed: 4
    Failed: 0

---

## 14. Final Logs

The final logs folder should remain clean and focused.

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

The `trace-example-*.jsonl` files satisfy the required Agentathon JSONL trace format:

    logs/trace-<run_id>.jsonl

Each JSONL line contains:

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

These logs demonstrate:

- which agents were invoked
- what each agent was asked to do
- agent-to-agent handoffs
- delegation decisions
- critic / validation steps
- guard and fallback behaviour
- final output synthesis

Large debug traces, old server stdout/stderr logs and temporary stress-test files are not required in the final submission.

---

## 15. Stress-Test Architecture

Stress-test script:

    python scripts/v800_agent_interaction_stress_test.py

It evaluates:

- direct general chat
- conceptual explanations
- single reservoir visuals
- multi-agent reservoir diagnosis
- invalid well guards
- ambiguous prompts

Expected pattern:

| Prompt | Expected behaviour |
|---|---|
| 5+7 | Direct |
| where is Rome? | Direct |
| Show me HW-25 oil production | Single specialist |
| Show TRAN multiplier corridor for HW-28 | Single specialist |
| Why is HW-28 water mismatch happening? | Multi-agent diagnosis |
| Show me HW-250 oil production | Guard |

The stress test is not only checking whether an answer exists. It checks whether the correct routing mode was selected.

---

## 16. Validation

Required files:

    run.py
    metadata.json
    .env.example
    README.md
    ARCHITECTURE.md
    input_examples/
    output_examples/
    logs/

Validation command:

    python scripts/validate_submission_files.py

Recommended syntax checks:

    python -m py_compile app/main.py
    python -m py_compile app/langgraph_universal_orchestrator_v501.py
    python -m py_compile app/universal_reservoir_orchestrator_v500.py
    python -m py_compile app/hm_report_v600.py
    python -m py_compile run.py

Recommended final example regeneration:

    python scripts/create_stronger_official_examples.py

---

## 17. Failure and Fallback Behaviour

### LLM unavailable

If the LLM endpoint is unavailable:

- General arbitrary chat may return a clear configuration message.
- Reservoir demo tools can still handle local model-specific workflows.
- The system avoids fabricating general knowledge.

### Invalid well

If a well is invalid:

- The system should not silently substitute another well.
- It should return a guard message and possible suggestions.

### Diagnostic visual ambiguity

If the question is diagnostic, the final visual should support the decision, not distract from it.

Example:

    Connectivity vs RelPerm?

Expected visual:

    Evidence board and hypothesis ranking table

not necessarily:

    TRAN map

unless the user explicitly asks for a TRAN map.

---

## 18. Design Principles

1. Dynamic routing over fixed pipeline.
   The system adapts to the question.

2. Single-tool simplicity for simple requests.
   A plot request should remain a plot request.

3. Multi-agent reasoning for causal questions.
   Why/how questions should gather evidence from multiple specialists.

4. Structured evidence over keyword bias.
   Numeric hypothesis scores should drive final ranking when available.

5. User-facing clarity.
   Internal agent names should remain in trace/logs, not dominate the main answer.

6. Visual intent matters.
   Show a map when the user asks for a map. Show a decision table when the user asks for a causal decision.

7. Guard invalid inputs.
   Invalid wells should not produce misleading visuals.

8. Preserve good matches.
   Model updates should improve weak dimensions without breaking already good oil/gas matches.

---

## 19. Example End-to-End Diagnostic Flow

User:

    Is the HW-28 water issue more likely caused by connectivity or relative permeability?

Expected flow:

    User message
      -> LLM Copilot Planner
      -> Evidence plan
      -> Integrated diagnosis tool
      -> Profile evidence
      -> WCT / water evidence
      -> TRAN / connectivity evidence
      -> Critic using structured hypothesis scores
      -> Final answer synthesizer
      -> Final visual selector
      -> Dashboard response

Expected final interpretation:

    The leading hypothesis is selected from structured evidence scores.
    If RelPerm / endpoint saturation has the highest score, the answer identifies RelPerm / water mobility as the leading explanation.
    Connectivity remains a secondary check if it has supporting but lower-ranked evidence.

Expected visual:

    Integrated evidence board
    Hypothesis ranking table
    Recommended next checks

---

## 20. Why The Architecture Is Agentic but Controlled

The system is not a fully autonomous group of free-form agents negotiating without structure.

It is also not a fixed static pipeline.

It is a controlled agentic architecture:

    semantic planner
    + specialist reservoir tools
    + critic-based hypothesis ranking
    + final synthesis
    + visual evidence selection
    + interaction logging

This is appropriate for a reservoir-engineering decision-support workflow because it balances:

- flexibility
- traceability
- domain-specific reliability
- clear user-facing output
- auditable reasoning path

---

## 21. Submission Summary

404 Reservoir Not Found provides an interactive, auditable and reservoir-focused AI copilot.

It helps answer:

- What is matching?
- What is not matching?
- Which phase is responsible?
- Which wells are critical?
- Is the issue more likely connectivity, RelPerm, pressure support or controls?
- Which model update should be tested first?
- What evidence supports that decision?

The system provides both readable engineering interpretation and machine-readable interaction traces, making the reasoning path visible, testable and auditable.


---

## Compass Endpoint Note

Compass endpoint note:
- The official Agentathon checklist references https://compass.core42.ai/v1.
- During local testing, that endpoint returned HTTP 405 for generation calls.
- The project therefore reads the Compass/OpenAI-compatible base URL from environment variables and supports the working Compass-compatible gateway https://api.core42.ai/v1 when provided by the evaluator or local .env.

---

## Compass Endpoint and Runtime Configuration

The system uses Compass through OpenAI-compatible environment variables.

The official Agentathon checklist references:

    OPENAI_BASE_URL=https://compass.core42.ai/v1

During local testing, generation calls against that endpoint returned HTTP 405 Not Allowed, while the Compass-compatible API gateway worked for generation requests:

    OPENAI_BASE_URL=https://api.core42.ai/v1

The application therefore does not hardcode the endpoint. It reads the runtime endpoint from:

    OPENAI_BASE_URL
    COMPASS_BASE_URL
    COMPASS_API_BASE_URL

This keeps the architecture compatible with the official Compass requirement while allowing the evaluator or runtime environment to inject the active Compass gateway for the assigned tenant.

No API key is hardcoded. Credentials must be provided only through environment variables.


