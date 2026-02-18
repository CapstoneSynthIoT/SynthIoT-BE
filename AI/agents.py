import os
import time
from crewai import Agent, Crew, Process, Task, LLM
from dotenv import load_dotenv
from crewai_tools import SerperDevTool
from functools import lru_cache
from AI.tools import GenerationConfig

load_dotenv()

# Check for keys to avoid silent crashes
if not os.getenv("SERPER_API_KEY"):
    raise ValueError("❌ SERPER_API_KEY not found in environment variables.")

llm_groq = LLM(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=os.getenv("GROQ_API_KEY")
)

search_tool = SerperDevTool()

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
    verbose=False  # <--- CHANGED to False
)

def run_crew_logic(user_prompt: str):
    t1 = Task(
        description=f"""Analyze: '{user_prompt}'.
        
        1. **USER INTENT & OVERRIDES**:
           - IF user asks for "N rows", extract 'row_count'.
           - IF specific environment ("Oven", "Freezer"), use physics.
           - ONLY search weather if City/Country mentioned AND no temps given.
        
        2. **SAFETY & PHYSICS (CRITICAL)**: 
           - **MAX TEMP LIMIT**: The sensor fails above 176 F (80 C).
           - IF user asks for > 176 F, you MUST clamp 't_max' to 176.
           - Convert ALL Celsius to Fahrenheit: F = (C * 1.8) + 32.
        
        3. **DEFAULTS & FALLBACKS (CRITICAL)**: 
           - FIRST: Use scientific domain knowledge. NEVER allow (t_max - t_min) to be less than 5.0 F (unless it is a strict cleanroom or oven).
           - IF environment is vague: Use a MINIMUM 10.0 F range (e.g., t_min: 68.0, t_max: 78.0).
           - IF completely generic ("sensor data"): Fallback to Chennai Context -> Location: 'Chennai', t_min: 78.0, t_max: 88.0, humidity_base: 70.0.
           - 'noise_scale': 1.0 (normal), 0.1 (strict/museum), 2.0 (chaos).
           - IF query mentions "rain", "storm", "wet", set 'rain_status': true.

        OUTPUT: A single JSON object matching the GenerationConfig schema.
        """,
        agent=climate_agent,
        output_pydantic=GenerationConfig,
        expected_output="Valid Pydantic Object"
    )

    crew = Crew(agents=[climate_agent], tasks=[t1], process=Process.sequential)
    return crew.kickoff()
# [NEW] Retry Wrapper
@lru_cache(maxsize=50)  # Increased from 20 to protect against rate limits
def run_crew_with_retry(user_prompt: str):
    max_retries = 3
    delay = 30 # Groq usually asks for ~20-25s
    
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
