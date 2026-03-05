import os
import time
from crewai import Agent, Crew, Process, Task, LLM
from dotenv import load_dotenv
from crewai_tools import SerperDevTool
from functools import lru_cache
from AI.tools import GenerationConfig
from pydantic import BaseModel
from typing import List, Optional

load_dotenv()

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

llm_groq = LLM(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.getenv("GROQ_API_KEY")
)

search_tool = SerperDevTool()

# --- AGENT 1: Meteorologist (original) ---
# [OPTIMIZATION] Disable verbose logging to save tokens
climate_agent = Agent(
    role='Senior Meteorologist',
    goal='Provide accurate, physics-compliant climate parameters.',
    backstory=(
        "You are an expert Meteorologist. You use Search to find real weather data. "
        "You DO NOT worry about sensor limits—the system handles safety checks automatically."
    ),
    llm=llm_groq,
    tools=[search_tool],
    verbose=False
)

# --- AGENT 2: Prompt Interpreter ---
prompt_interpreter_agent = Agent(
    role='IoT Data Prompt Specialist',
    goal='Translate vague user prompts into concrete geographic and environmental parameters.',
    backstory=(
        "You specialize in disambiguating vague requests like 'hot and humid' into "
        "specific cities, seasons, and parameter ranges. You output a refined, unambiguous "
        "prompt for the Meteorologist to act on."
    ),
    llm=llm_groq,
    tools=[],
    verbose=False
)

# --- AGENT 3: Unit Validator ---
unit_validator_agent = Agent(
    role='Climatology Unit Validator',
    goal='Ensure all temperature values are correctly in Fahrenheit before data generation.',
    backstory=(
        "You are a precise unit conversion specialist. You receive climate parameters "
        "and verify they are physically realistic for the given location and season. "
        "You know that no inhabited city on Earth has average temps below 32°F except in polar/mountain extremes. "
        "You convert Celsius to Fahrenheit when needed: F = (C × 1.8) + 32."
    ),
    llm=llm_groq,
    tools=[],
    verbose=False
)

# --- AGENT 4: Config Critic ---
config_critic_agent = Agent(
    role='IoT Config Sanity Checker',
    goal='Flag and fix physically impossible GenerationConfig combinations before data is generated.',
    backstory=(
        "You review climate configs and catch nonsense combinations: humidity 95% in a desert, "
        "t_min > t_max, freezing temps labeled as Chennai summer, etc. "
        "You fix what you can and pass through what is valid."
    ),
    llm=llm_groq,
    tools=[],
    verbose=False
)

# --- AGENT 5: Data Realism Agent (post-generation, called separately in main.py) ---
data_realism_agent = Agent(
    role='Synthetic Data Realism Auditor',
    goal='Verify that generated IoT data is statistically realistic for the given location and config.',
    backstory=(
        "You receive a sample of generated sensor data plus the config it was generated from. "
        "You check: does the mean temperature match the expected range? Is humidity physically "
        "correlated with temperature? Are there impossible values (negative humidity, 200°F)? "
        "You return a verdict: PASS or FAIL with specific reasons."
    ),
    llm=llm_groq,
    tools=[],
    verbose=False
)

# --- AGENT 6: Anomaly Injector ---
anomaly_injector_agent = Agent(
    role='IoT Anomaly Injection Specialist',
    goal='Decide what realistic anomalies to inject based on user intent.',
    backstory=(
        "You read the user's prompt and decide what faults make sense: sensor spike, dropout, "
        "gradual drift, or frozen value. You output a structured anomaly plan "
        "that the system will physically apply to the generated data."
    ),
    llm=llm_groq,
    tools=[],
    verbose=False
)


def run_crew_logic(user_prompt: str):

    # TASK 1: Prompt Interpreter — clarify vague prompts
    t0 = Task(
        description=f"""
        The user said: '{user_prompt}'
        Your job: If the prompt is vague ("hot and humid", "tropical weather"), 
        map it to a real city and season. If it's already specific, pass it through unchanged.
        Output: A single refined prompt string. Nothing else.
        """,
        agent=prompt_interpreter_agent,
        expected_output="A refined, specific prompt string"
    )

    # TASK 2: Meteorologist — research and fill config
    t1 = Task(
        description=f"""Analyze the refined prompt from the previous task.
        
        1. ONLY search weather if City/Country mentioned AND no temps given.
        2. IF specific environment ("Oven", "Freezer"), use physics.
        3. Convert ALL Celsius to Fahrenheit: F = (C * 1.8) + 32.
        4. DEFAULTS: IF vague, use t_min: 68.0, t_max: 78.0, humidity_base: 60.0.
        5. IF user asks for N rows, extract row_count.
        6. MAX TEMP LIMIT: clamp t_max to 176 F.
        7. IF user mentions 'faults', 'anomalies', 'errors', 'spikes', 'dropout',
           'sensor failure', or 'realistic noise', set 'sensor_faults': true.

        OUTPUT: A single JSON object matching the GenerationConfig schema.
        State what unit system you found the data in via a 'unit' field: 'C' or 'F'.
        """,
        agent=climate_agent,
        expected_output="A JSON object with climate parameters and a 'unit' field",
        context=[t0]
    )

    # TASK 3: Unit Validator — fix Celsius/Fahrenheit issues
    t2 = Task(
        description="""
        You receive climate parameters from the Meteorologist.
        1. Check the 'unit' field. If 'C', convert t_min and t_max: F = (C × 1.8) + 32.
        2. GEOGRAPHIC SANITY CHECK: If unit is unclear:
           - If t_min and t_max are both below 45, they are almost certainly Celsius. Convert.
           - If t_max > 45, trust the values.
        3. After conversion, verify values make sense for the location.
        OUTPUT: Updated JSON with temperatures guaranteed in Fahrenheit.
        """,
        agent=unit_validator_agent,
        expected_output="JSON with all temperatures confirmed in Fahrenheit",
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
        5. Flag any other physically impossible combinations and fix them.
        OUTPUT: Final validated GenerationConfig Pydantic object.
        """,
        agent=config_critic_agent,
        output_pydantic=GenerationConfig,
        expected_output="Valid Pydantic GenerationConfig object",
        context=[t2]
    )

    crew = Crew(
        agents=[prompt_interpreter_agent, climate_agent, unit_validator_agent, config_critic_agent],
        tasks=[t0, t1, t2, t3],
        process=Process.sequential
    )
    return crew.kickoff()


# [NEW] Retry Wrapper
@lru_cache(maxsize=50)  # Increased from 20 to protect against rate limits
def run_crew_with_retry(user_prompt: str):
    max_retries = 3
    delay = 30  # Groq usually asks for ~20-25s

    for attempt in range(max_retries):
        try:
            return run_crew_logic(user_prompt)
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "429" in error_str:
                print(f"⚠️ Rate Limit Hit. Waiting {delay}s before retry {attempt+1}/{max_retries}...")
                time.sleep(delay)
            elif "413" in error_str or "payload" in error_str:
                print("⚠️ Payload too large. Retrying with shortened prompt...")
                # Try with a truncated prompt to reduce context
                return run_crew_logic(user_prompt[:50])
            else:
                raise e
    raise Exception("Max retries exceeded")
