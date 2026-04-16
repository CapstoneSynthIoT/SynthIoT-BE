import os
import time
import json
import re
import logging
from crewai import Agent, Crew, Process, Task, LLM
from dotenv import load_dotenv
from crewai_tools import SerperDevTool
from AI.tools import GenerationConfig
from pydantic import BaseModel
from typing import List, Optional

load_dotenv()

logger = logging.getLogger("SynthIoT")

# --- ANOMALY PLAN MODEL ---
class AnomalyPlan(BaseModel):
    inject_spike: bool = False
    spike_magnitude: float = 0.0       # degrees F above normal
    inject_dropout: bool = False
    dropout_duration_rows: int = 0
    inject_drift: bool = False
    drift_rate_per_row: float = 0.0    # gradual temp drift per row
    inject_frozen: bool = False
    frozen_duration_rows: int = 0
    reasoning: str = ""

# Check for keys to avoid silent crashes
if not os.getenv("SERPER_API_KEY"):
    raise ValueError("❌ SERPER_API_KEY not found in environment variables.")

# ---------------------------------------------------------------------------
# LLM FALLBACK CHAIN
# Primary: Groq (fast, free but low RPM limit)
# Fallback 1: Google Gemini Flash (very generous free tier: 15 RPM, 1M TPM)
# Fallback 2: Cerebras (ultra-fast inference, free tier)
# ---------------------------------------------------------------------------
llm_groq = LLM(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.getenv("GROQ_API_KEY")
)

# NOTE: Do NOT pass api_key explicitly for Gemini — LiteLLM reads GEMINI_API_KEY
# from the environment automatically. Passing it explicitly causes an import-time
# crash in CrewAI 1.10.1 / LiteLLM 1.83+ due to internal validation.
try:
    llm_gemini = LLM(
        model="gemini/gemini-2.5-flash"
    ) if os.getenv("GEMINI_API_KEY") else None
except Exception as _gemini_err:
    logger.warning(f"⚠️ Could not initialize Gemini LLM (will skip): {_gemini_err}")
    llm_gemini = None

try:
    llm_cerebras = LLM(
        model="cerebras/llama3.1-8b",
        api_key=os.getenv("CEREBRAS_API_KEY")
    ) if os.getenv("CEREBRAS_API_KEY") else None
except Exception as _cerebras_err:
    logger.warning(f"⚠️ Could not initialize Cerebras LLM (will skip): {_cerebras_err}")
    llm_cerebras = None

# Ordered fallback list — only include LLMs whose keys are configured
_LLM_FALLBACK_CHAIN = [llm for llm in [llm_groq, llm_gemini, llm_cerebras] if llm is not None]

search_tool = SerperDevTool()

# ---------------------------------------------------------------------------
# Agent factories — agents are built with the active LLM at call time.
# This lets the fallback chain swap the LLM without redefining global singletons.
# ---------------------------------------------------------------------------

def _make_agents(llm: LLM):
    """Build all agents using the specified LLM instance."""
    climate = Agent(
        role='Senior Meteorologist',
        goal='Provide accurate, physics-compliant climate parameters.',
        backstory=(
            "You are an expert Meteorologist. You use Search to find real weather data. "
            "You DO NOT worry about sensor limits—the system handles safety checks automatically."
        ),
        llm=llm,
        tools=[search_tool],
        verbose=False
    )
    prompt_interpreter = Agent(
        role='IoT Data Prompt Specialist',
        goal='Translate vague user prompts into concrete geographic, environmental, and time-range parameters.',
        backstory=(
            "You specialize in disambiguating vague requests like 'hot and humid' into "
            "specific cities, seasons, and parameter ranges. You also extract explicit time spans "
            "from the prompt (e.g. 'March month', 'last week', '7 days') and encode them as "
            "concrete start_time, end_time, and time_interval values. "
            "You output a refined, unambiguous prompt for the Meteorologist to act on."
        ),
        llm=llm,
        tools=[],
        verbose=False
    )
    unit_validator = Agent(
        role='Climatology Unit Validator',
        goal='Ensure all temperature values are correctly in Fahrenheit before data generation.',
        backstory=(
            "You are a precise unit conversion specialist. You receive climate parameters "
            "and verify they are physically realistic for the given location and season. "
            "You know that no inhabited city on Earth has average temps below 32°F except in polar/mountain extremes. "
            "You convert Celsius to Fahrenheit when needed: F = (C × 1.8) + 32."
        ),
        llm=llm,
        tools=[],
        verbose=False
    )
    config_critic = Agent(
        role='IoT Config Sanity Checker',
        goal='Flag and fix physically impossible GenerationConfig combinations before data is generated.',
        backstory=(
            "You review climate configs and catch nonsense combinations: humidity 95% in a desert, "
            "t_min > t_max, freezing temps labeled as Chennai summer, etc. "
            "You fix what you can and pass through what is valid."
        ),
        llm=llm,
        tools=[],
        verbose=False
    )
    return prompt_interpreter, climate, unit_validator, config_critic


def _make_support_agents(llm: LLM):
    """Build the realism auditor and anomaly injector agents."""
    realism = Agent(
        role='Synthetic Data Realism Auditor',
        goal='Verify that generated IoT data is statistically realistic for the given location and config.',
        backstory=(
            "You receive a sample of generated sensor data plus the config it was generated from. "
            "You check: does the mean temperature match the expected range? Is humidity physically "
            "correlated with temperature? Are there impossible values (negative humidity, 200°F)? "
            "You return a verdict: PASS or FAIL with specific reasons."
        ),
        llm=llm,
        tools=[],
        verbose=False
    )
    anomaly = Agent(
        role='IoT Anomaly Injection Specialist',
        goal='Decide what realistic anomalies to inject based on user intent.',
        backstory=(
            "You read the user's prompt and decide what faults make sense: sensor spike, dropout, "
            "gradual drift, or frozen value. You output a structured anomaly plan "
            "that the system will physically apply to the generated data."
        ),
        llm=llm,
        tools=[],
        verbose=False
    )
    return realism, anomaly


# Convenience accessors used by main.py imports (built with primary LLM)
# These are rebuilt per-request when fallback is active.
def _get_primary_llm() -> LLM:
    return _LLM_FALLBACK_CHAIN[0]

try:
    _primary_realism, _primary_anomaly = _make_support_agents(_get_primary_llm())
    data_realism_agent = _primary_realism
    anomaly_injector_agent = _primary_anomaly
except Exception as _agent_init_err:
    logger.warning(f"⚠️ Could not pre-build support agents at import time: {_agent_init_err}")
    data_realism_agent = None
    anomaly_injector_agent = None


def run_crew_logic(user_prompt: str, llm: LLM = None):
    """Run the 4-agent config generation pipeline using the specified LLM."""
    if llm is None:
        llm = _get_primary_llm()

    prompt_interpreter_agent, climate_agent, unit_validator_agent, config_critic_agent = _make_agents(llm)

    # TASK 1: Prompt Interpreter — clarify location AND extract duration
    t0 = Task(
        description=f"""
        The user said: '{user_prompt}'

        Your job has TWO parts:

        PART A — Clarify location/environment:
        If the prompt is vague ("hot and humid", "tropical weather"), map it to a real city and season.
        If it's already specific (e.g. "Chennai"), keep it.

        PART B — Extract duration and compute the right time_interval:

        STEP 1 — Does the user explicitly mention an interval?
        If the user says things like "30-second data", "daily readings", "hourly data", "1-minute intervals":
        → Use that interval exactly. Skip the formula below.

        STEP 2 — Extract the total duration from the prompt:
        Examples:
        - "March month" / "for March"       → duration = 31 days  = 2,678,400 seconds
        - "last 3 months"                   → duration = 90 days  = 7,776,000 seconds
        - "for a week" / "7 days"           → duration = 7 days   = 604,800 seconds
        - "for a day" / "24 hours"          → duration = 1 day    = 86,400 seconds
        - "annual" / "whole year"           → duration = 365 days = 31,536,000 seconds
        - "N rows" / "N data points"        → set row_count = N, time_interval = "30s", skip formula
        - No duration mentioned             → leave start_time, end_time, row_count empty

        STEP 3 — Compute time_interval using the formula:
        raw_interval_seconds = total_duration_seconds / 750

        Ladder values in seconds (pick the one that keeps row count between 500–1000):
        | Label  | Seconds |
        |--------|---------|
        | 30s    | 30      |
        | 1min   | 60      |
        | 2min   | 120     |
        | 5min   | 300     |
        | 10min  | 600     |
        | 15min  | 900     |
        | 30min  | 1800    |
        | 1h     | 3600    |
        | 2h     | 7200    |
        | 6h     | 21600   |
        | 12h    | 43200   |
        | 1D     | 86400   |

        Pick the largest interval where floor(total_duration_seconds / interval_seconds) >= 500.
        This guarantees row count stays between 500 and 1000.

        Examples:
        - 1 day   (86,400s)    → 86400/750 = 115s   → use "2min"  → 86400/120  = 720 rows  ✓
        - 1 week  (604,800s)   → 604800/750 = 806s  → use "15min" → 604800/900 = 672 rows  ✓
        - 1 month (2,678,400s) → 2678400/750 = 3571s → use "1h"   → 2678400/3600 = 744 rows ✓
        - 3 months(8,035,200s) → 8035200/750 = 10714s → use "2h"  → 8035200/7200 = 1116 rows → try "6h" = 1116 → use "6h" = 372... → use "2h" (closest >=500)
        - 1 year  (31,536,000s)→ 31536000/750 = 42048s → use "12h" → 31536000/43200 = 730 rows ✓

        CRITICAL — time_interval format rules:
        ALWAYS write time_interval using ONLY these exact strings: "30s", "1min", "2min", "5min",
        "10min", "15min", "30min", "1h", "2h", "6h", "12h", "1D"
        NEVER use ISO 8601 format like "PT1H", "PT30M", "P1D" — these will break the system.

        STEP 4 — Set start_time and end_time based on the duration:
        Use 2023 as the default year if no year is mentioned.
        For "March month": start_time = "2023-03-01 00:00:00", end_time = "2023-03-31 23:00:00"

        IMPORTANT: NEVER use "30s" for any duration longer than 1 hour.
        That would generate hundreds of thousands of rows and crash the system.

        Output: A single refined prompt string that includes the location, climate context,
        AND the explicit time parameters. Example:
        "Chennai, India during March 2023. start_time: 2023-03-01 00:00:00, end_time: 2023-03-31 23:00:00, time_interval: 1h"

        Output ONLY the refined prompt string. Nothing else.
        """,
        agent=prompt_interpreter_agent,
        expected_output="A refined prompt string with location, climate context, and explicit time range"
    )

    # TASK 2: Meteorologist — research and fill config
    t1 = Task(
        description=f"""Analyze the refined prompt from the previous task.

        1. ONLY search weather if City/Country mentioned AND no temps given.
        2. IF specific environment ("Oven", "Freezer"), use physics.
        3. Convert ALL Celsius to Fahrenheit: F = (C * 1.8) + 32.
        4. DEFAULTS: IF vague, use t_min: 68.0, t_max: 78.0, humidity_base: 60.0.
        5. IF user asks for N rows, set row_count = N.
        6. MAX TEMP LIMIT: clamp t_max to 176 F.
        7. IF user mentions 'faults', 'anomalies', 'errors', 'spikes', 'dropout',
           'sensor failure', or 'realistic noise', set 'sensor_faults': true.
        8. CRITICAL — time fields: Copy start_time, end_time, and time_interval
           EXACTLY as specified in the refined prompt. Do NOT change or invent them.

        OUTPUT: A single JSON **object** (NOT an array, NOT a list) matching the GenerationConfig schema exactly.
        Example of CORRECT output: {{"location": "Chennai, India", "t_min": 75.2, "t_max": 95.0, "humidity_base": 75.0, "start_time": "2023-03-01 00:00:00", "end_time": "2023-03-31 23:00:00", "time_interval": "1h"}}
        Example of WRONG output:   [{{"t_min": 75.2, ...}}]   <-- never wrap in an array
        Do NOT add a 'unit' field — it is not in the schema.
        """,
        agent=climate_agent,
        expected_output="A single JSON object with climate and time parameters matching GenerationConfig",
        context=[t0]
    )

    # TASK 3: Unit Validator — fix Celsius/Fahrenheit issues
    t2 = Task(
        description="""
        You receive climate parameters from the Meteorologist.
        1. If t_min and t_max are both below 45, they are almost certainly Celsius — convert: F = (C × 1.8) + 32.
        2. If t_max > 45, trust the values as already Fahrenheit.
        3. After conversion, verify values make sense for the location.
        4. Preserve start_time, end_time, time_interval, and row_count EXACTLY — do not change them.
        OUTPUT: A single JSON **object** (NOT an array) with temperatures guaranteed in Fahrenheit.
        """,
        agent=unit_validator_agent,
        expected_output="A single JSON object with all temperatures confirmed in Fahrenheit",
        context=[t1]
    )

    # TASK 4: Config Critic — final sanity check, output Pydantic
    t3 = Task(
        description="""
        You receive a validated JSON config. Do a final sanity check:
        1. t_min must be < t_max. If not, swap them.
        2. humidity_base must be between 10 and 100. Fix if not.
        3. If rain_status is True, humidity_base should be >= 80.
        4. If ac_status is True and t_max > 85°F, that's fine — AC is fighting the heat.
        5. Preserve start_time, end_time, time_interval, and row_count EXACTLY — do not change them.
        6. Flag any other physically impossible combinations and fix them.
        OUTPUT: A single JSON **object** (NOT an array) matching the GenerationConfig schema exactly.
        CRITICAL: Output ONLY the JSON object. Do NOT write any text, explanation, or comments
        before or after the JSON. The response must start with { and end with } and nothing else.
        """,
        agent=config_critic_agent,
        output_pydantic=GenerationConfig,
        expected_output="Valid Pydantic GenerationConfig object, nothing else",
        context=[t2],
        result_as_answer=True
    )

    crew = Crew(
        agents=[prompt_interpreter_agent, climate_agent, unit_validator_agent, config_critic_agent],
        tasks=[t0, t1, t2, t3],
        process=Process.sequential
    )
    result = crew.kickoff()

    # Safety net: Groq sometimes wraps output in an array, or appends trailing text after }.
    # If CrewAI couldn't parse it into a Pydantic model, try to repair it here.
    if result.pydantic is None and result.raw:
        try:
            raw = result.raw.strip()
            # Strip markdown fences
            raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'```\s*$', '', raw, flags=re.MULTILINE).strip()
            # Extract ONLY the first {...} block — discard any trailing text after it
            match = re.search(r'\{.*?\}(?=\s*$|\s*[^,\[\{])', raw, re.DOTALL)
            if match:
                raw = match.group(0)
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) > 0:
                parsed = parsed[0]
            if isinstance(parsed, dict):
                result._pydantic = GenerationConfig(**parsed)
        except Exception as repair_err:
            import logging
            logging.getLogger("SynthIoT").warning(f"⚠️ JSON repair failed: {repair_err}")

    return result


def run_crew_with_retry(user_prompt: str):
    """
    Runs the crew with automatic LLM fallback on rate-limit errors.

    Strategy:
      1. Try the primary LLM (Groq) up to 2 times with exponential backoff.
      2. On continued 429s, switch to the next LLM in the fallback chain
         (Gemini Flash, then Cerebras) without waiting.
      3. Non-rate-limit errors always raise immediately.
    """
    is_rate_limit = lambda e: "rate_limit" in str(e).lower() or "429" in str(e).lower() or "rate limit" in str(e).lower()

    for llm_idx, llm in enumerate(_LLM_FALLBACK_CHAIN):
        llm_name = llm.model
        max_attempts = 2  # 2 attempts per LLM before falling back
        base_delay = 30

        for attempt in range(max_attempts):
            try:
                logger.info(f"🤖 Using LLM: {llm_name} (attempt {attempt + 1}/{max_attempts})")
                return run_crew_logic(user_prompt, llm=llm)
            except Exception as e:
                error_str = str(e).lower()
                if "413" in error_str or "payload" in error_str:
                    logger.warning("⚠️ Payload too large. Retrying with shortened prompt...")
                    return run_crew_logic(user_prompt[:50], llm=llm)
                elif is_rate_limit(e):
                    if attempt < max_attempts - 1:
                        # Still have attempts left on this LLM — wait and retry
                        delay = base_delay * (2 ** attempt)  # 30s, 60s
                        logger.warning(f"⚠️ Rate limit on {llm_name}. Waiting {delay}s before retry...")
                        time.sleep(delay)
                    else:
                        # All attempts exhausted on this LLM — try the next one
                        next_llm = _LLM_FALLBACK_CHAIN[llm_idx + 1].model if llm_idx + 1 < len(_LLM_FALLBACK_CHAIN) else None
                        if next_llm:
                            logger.warning(f"🔄 {llm_name} rate-limited. Falling back to {next_llm}...")
                        break  # break inner loop to advance to next LLM
                else:
                    raise  # Non-rate-limit error: fail immediately

    raise Exception(
        "All LLMs in the fallback chain are rate-limited. "
        "Please wait 1–2 minutes and try again."
    )
