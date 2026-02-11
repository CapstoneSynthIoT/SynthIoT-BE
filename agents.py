import os
from crewai import Agent, Crew, Process, Task, LLM
from dotenv import load_dotenv

load_dotenv()

# --- CONFIG ---
# Configure Groq LLM for CrewAI
# Using llama-3.3-70b-versatile (current supported model)
llm_groq = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

# --- AGENTS ---

climate_agent = Agent(
    role='Climate Context Specialist',
    goal='Extract environmental parameters from natural language',
    backstory='Meteorologist who converts descriptions to physics parameters.',
    llm=llm_groq,
    verbose=True
)

# FREE VERSION: Logic is hardcoded, no PDF tool needed
sensor_agent = Agent(
    role='Sensor Safety Engineer',
    goal='Validate parameters against AM2320 limits',
    backstory=(
        "You are a Hardware Engineer. You know the AM2320 Sensor specs by heart: "
        "Max Temperature: 80C (176F). "
        "Max Humidity: 99.9%. "
        "Min Temperature: -40C. "
        "If the requested t_max is above 176F, you MUST clamp it to 176F."
    ),
    llm=llm_groq,
    verbose=True
)

# --- WORKFLOW ---
def run_crew(user_prompt: str):
    # Task 1: Extraction
    t1 = Task(
        description=f"""Analyze: '{user_prompt}'. Extract to JSON with these exact fields:
        - location: string (city name)
        - t_min: number (minimum temperature in Fahrenheit)
        - t_max: number (maximum temperature in Fahrenheit)
        - humidity_base: number (base humidity as PERCENTAGE 0-100, e.g., 80 for 80% humidity)
        - inertia: number (1-4, thermal inertia factor, default 2)
        - noise_scale: number (0.1-2.0, noise amplitude, default 1.0)
        - ac_status: boolean (true if AC is on, false otherwise)
        - fan_status: boolean (true if fan is on, false otherwise)
        - rain_status: boolean (true if raining, false otherwise)
        - indoor_status: boolean (true if indoor, false if outdoor)
        - start_time: string (YYYY-MM-DD HH:MM:SS format)
        - end_time: string (YYYY-MM-DD HH:MM:SS format)
        
        CRITICAL: humidity_base must be 0-100 (e.g., 80 for 80% humidity, NOT 0.8).
        Default to today 08:00-18:00 if time is missing.""",
        agent=climate_agent,
        expected_output="Valid JSON string with all required fields in correct formats."
    )

    # Task 2: Validation (Rule Based)
    t2 = Task(
        description="""Review the JSON from the previous task. The AM2320 sensor has a maximum temperature limit of 176°F (80°C).
        
        Check if t_max > 176:
        - If YES: Modify the JSON to set t_max = 176 (sensor safety limit)
        - If NO: Return the JSON exactly as received, unchanged
        
        CRITICAL: Only modify t_max if it exceeds 176°F. Otherwise, preserve the original value.""",
        agent=sensor_agent,
        expected_output="JSON string with t_max validated against sensor limits (176°F max)."
    )

    # The crew's job is now to produce the final, validated JSON config.
    crew = Crew(agents=[climate_agent, sensor_agent], tasks=[t1, t2], process=Process.sequential)
    return crew.kickoff()
