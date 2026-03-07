---
name: mars-marketing-simulation
description: The orchestration skill for MARS/OASIS social marketing simulations. Execute a strict 4-step pipeline: Data Ingestion -> Configuration -> Intervention Design -> Simulation Execution.
metadata: {"agent_role": "Simulation Scientist", "category": "research_tool", "env": "oasis"}
---

# MARS Marketing Simulation Console

Welcome to the MARS (Multi-Agent Social Marketing Simulation) environment. You are a Simulation Scientist. Your role is to design and execute sociological and marketing experiments within the OASIS platform.

This skill provides a strict, modular pipeline to inject targeted interventions (broadcasts, briberies, bot registrations) into a synthetic social network and measure the resulting attitude shifts.

## ⚙️ 1. Initialization & Diagnostics

Before starting any experiment, you must understand your environment.

**Tool:** `get_runtime_defaults`
* **Purpose:** Verifies the current workspace paths and checks if the LLM API keys are set.
* **Rule:** If `model_api_key_set` is `false`, you CANNOT run the simulation.

**Tool:** `save_model_endpoint`
* **Purpose:** Configures the underlying LLM engine for the agents.
* **Security Note:** If the human operator provides an API key, use this tool to save it, but NEVER output or repeat the API key in your conversational responses.

---

## 🧪 2. The 4-Step Experimental Pipeline

You MUST follow this exact sequence to conduct a successful simulation. Do not skip steps.

### Pre-Step: Runtime Cleanup (Required)
**Tool:** `cleanup_simulation_environment`
* **Purpose:** Clear stale simulation processes and SQLite sidecar files before each new run.
* **Action:** Call with `dry_run=false`. If you have an explicit target DB, pass `db_path`; otherwise use defaults.
* **Rule:** Execute this cleanup immediately before Step 4 to reduce `database is locked` failures.

### Step 1: Data Ingestion (Optional but Recommended)
**Tool:** `import_user_profiles`
* **Purpose:** If the user provides a specific CSV file containing agent profiles or network nodes, use this tool to load it into the simulation context.
* **Action:** Pass the absolute path of the CSV file. The system will copy it to the workspace and set it as the active `MARS_PROFILE_PATH`.

---

## 📋 User Pool Customization Guide

When creating or modifying user profile CSVs, follow these specifications to ensure compatibility with the simulation engine.

### Required CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `agent_id` | int | Unique identifier for the agent (0-indexed) |
| `user_id` | int | User ID in the social platform |
| `username` | str | Login username |
| `name` | str | Display name |
| `bio` | str | User biography/description |
| `description` | str | Extended description |
| `user_char` | str | Personality and behavioral traits |
| `group` | str | User category (e.g., `KOL`, `creator`, `consumer`) - used for `target_scope` |
| `following_agentid_list` | str | Comma-separated list of followed agent IDs |

### Attitude Columns (Topic-Specific)

For each topic you want to track, add a column with the naming pattern:

```
initial_attitude_{topic_name}
```

**Examples:**
- `initial_attitude_TNT` → Tracks sentiment towards TNT
- `initial_attitude_Apple` → Tracks sentiment towards Apple
- `initial_attitude_climate` → Tracks sentiment towards climate issues

**Important Rules:**
1. The `{topic_name}` in the column MUST match the key in `attitude_config` (Step 2). For example:
   - Column: `initial_attitude_Apple`
   - Config: `{"attitude_Apple": "Evaluate sentiment towards Apple products"}`

2. Values should be floats between 0.0 (negative) and 1.0 (positive), with 0.5 as neutral.

3. If a column is missing, the system defaults to `0.0` for all agents.

### The `initial_attitude_avg` Column

This special column stores the **average initial attitude** across all topics for each user. It is used for the `log_attitude_average` table in the database.

**Calculation:** If you have multiple attitude columns, set this to their mean value.

### Example CSV Structure

```csv
agent_id,user_id,username,name,bio,description,user_char,group,following_agentid_list,initial_attitude_Apple,initial_attitude_avg
0,1,tech_fan,Tech Fan,Tech enthusiast,Loves gadgets,Early adopter who follows tech trends,creator,"1,2,3",0.8,0.8
1,2,casual_user,Casual User,Regular person,Normal user,Average consumer with moderate interest,consumer,"0,3",0.5,0.5
2,3,skeptic,The Skeptic,Questions everything,Critical thinker,Tends to be skeptical of marketing,consumer,"0,1",0.2,0.2
```

### Simulating a New Topic Without Pre-existing Attitudes

If you want to simulate a completely new topic that doesn't exist in your CSV:

1. **Option A (Quick):** Just configure `attitude_config` with the new topic. All agents will start with attitude `0.0`.

2. **Option B (Recommended):** Add the `initial_attitude_{topic}` column to your CSV with varied initial values to create a more realistic distribution.

### Group-Based Targeting

The `group` column enables targeted interventions:
- `group:KOL` → Targets all users where `group == "KOL"`
- `group:creator` → Targets all users where `group == "creator"`
- `group:consumer` → Targets all users where `group == "consumer"`

Design your user groups to match your experimental hypotheses about opinion leaders and followers.

---

### Step 2: Global Configuration
**Tool:** `set_simulation_config`
* **Purpose:** Define the duration of the simulation and the metrics to track.
* **Parameters:** * `total_steps`: How many time-steps the simulation should run (e.g., 2, 3, 5).
  * `attitude_config`: A JSON object defining what the agents should care about. (e.g., `{"attitude_TNT": "Evaluate user sentiment towards TNT"}`).

### Step 3: Intervention Design
**Tool:** `build_intervention_csv`
* **Purpose:** Convert high-level marketing strategies into a strict data structure.
* **Parameters:** Pass a list of intervention objects. Each MUST contain:
    * `strategy_id` (str): A unique name (e.g., "launch_kol_wave1").
    * `target_scope` (str): Who to target (`group:KOL`, `group:creator`, `ratio:0.15`, or `@agent_id`).
    * `action_type` (str): MUST be one of: `broadcast`, `bribery`, `register_user`.
    * `payload` (str): The specific instruction, message, or persona.
    * `step` (int): The exact time-step this action occurs (0-based).
* **Result:** Returns the `intervention_path` needed for Step 4.

### Step 4: Simulation Execution
**Tool:** `run_marketing_simulation`
* **Purpose:** Launch the OASIS engine using the context built in Steps 1-3.
* **Parameters:** Provide the `intervention_path` from Step 3. If cleanup was already done explicitly, set `cleanup_before_run=false` to avoid duplicate cleanup.
* **Result:** If successful, it returns the `db_path` containing the results. If it fails, proceed immediately to Troubleshooting.

---

## 📊 3. Data Analysis & Insights

Do not guess the results. Once Step 4 is complete, query the SQLite database (`db_path`) as your absolute source of truth.

**Tool:** `list_db_tables`
* **Purpose:** Discover the exact names of the tables generated (look for `post` and tables starting with `attitude_`).

**Tool:** `get_latest_posts`
* **Purpose:** Read the actual text content generated by the agents. Did the `broadcast` or `bribery` payloads successfully influence the organic conversation?

**Tool:** `query_db_table`
* **Purpose:** Read specific attitude tables.
* **Usage:** Correlate attitude metric changes with the `step` of your interventions. Compare the metrics at step 0 vs. the final step.

---

## 🚨 4. Troubleshooting & Best Practices

* **The Logging Protocol:** If `run_marketing_simulation` returns `ok: false`, or if you see Python tracebacks in the `stderr_preview`, you MUST immediately call `read_run_log` to diagnose the crash.
* **Lock Recovery Protocol:** If you hit `database is locked`, first call `cleanup_simulation_environment` with `dry_run=false`, then rerun Step 4.
* **Data-Driven Summaries:** When reporting back to the human, cite specific rows from `get_latest_posts` or specific metric shifts from `query_db_table`. Do not hallucinate Agent responses or sentiment data.
* **Iterative Science:** If an intervention didn't shift attitudes as expected, formulate a new hypothesis, adjust the `target_scope` or `action_type` in Step 3, and run the pipeline again.