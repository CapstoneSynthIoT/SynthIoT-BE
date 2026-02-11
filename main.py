from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from agents import run_crew
from tools import sys_instance, GenerationConfig # Import the generator instance and config model
import json
import io
from fastapi.concurrency import run_in_threadpool

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class PromptRequest(BaseModel):
    prompt: str

@app.get("/")
async def health_check():
    """Health check endpoint to verify the system is running."""
    return {
        "status": "healthy",
        "message": "SynthIoT API is running",
        "endpoints": {
            "/generate": "POST - Generate synthetic IoT sensor data from natural language prompts",
            "/docs": "GET - Interactive API documentation"
        }
    }

@app.post("/generate")
async def generate_and_stream_data(request: PromptRequest):
    """
    Generates synthetic data based on a prompt and streams it back as a CSV file.
    This is a stateless endpoint that performs all actions in a single request.
    """
    try:
        # The AI Crew's job is to return a validated JSON string.
        # This is a CPU/IO-bound task, so we run it in a thread pool to not block the server.
        crew_output = await run_in_threadpool(run_crew, request.prompt)
        
        # Extract the raw string from CrewOutput object
        # CrewAI returns a CrewOutput object, we need to get the raw output
        raw_output = str(crew_output.raw)
        
        # The output might be wrapped in markdown code blocks like ```json ... ```
        # Extract just the JSON content
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw_output, re.DOTALL)
        if json_match:
            validated_json_string = json_match.group(1)
        else:
            # If no code blocks, assume the whole output is JSON
            validated_json_string = raw_output.strip()
        
        # Parse the configuration from the AI's output
        raw_config = json.loads(validated_json_string)

        # Validate and structure the config using Pydantic
        try:
            config = GenerationConfig.model_validate(raw_config)
        except ValidationError as e:
            # If the LLM output is malformed, return a helpful error
            print(f"❌ LLM output validation error: {e}")
            print(f"Raw config received: {raw_config}")
            raise HTTPException(
                status_code=422, # Unprocessable Entity
                detail=f"Could not process the generated parameters. Validation failed: {e}"
            )

        # Generate the data using the main system instance
        print(f"✅ Validated config: {config.model_dump()}")
        df = await run_in_threadpool(sys_instance.generate, config)
        print(f"✅ Generated {len(df)} data points")

        # Stream the response
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=synthetic_data.csv"
        return response

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Print error to terminal for debugging
        print(f"❌ Server Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
