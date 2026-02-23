from fastapi import FastAPI, HTTPException
import logging

# Setup Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SynthIoT")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ValidationError
from AI.agents import run_crew_with_retry
from AI.tools import get_system_instance, GenerationConfig # Import the generator instance and config model
from AI.modify import ModifyRequest, process_modification_logic
from User.router import router as users_router
from User.auth_router import router as auth_router
import json
import io
import pandas as pd
from fastapi.concurrency import run_in_threadpool

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)

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
            "/modify": "POST - Fill a data gap with AI-generated, bridged sensor data",
            "/users/signup": "POST - Register a new user",
            "/users/{user_id}": "GET/PUT/DELETE - Read, update, or delete a user",
            "/users/": "GET - List all users (paginated)",
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
        crew_output = await run_in_threadpool(run_crew_with_retry, request.prompt)
        
        # [THE FIX] No more JSON parsing!
        # CrewAI automatically validated and parsed it into the Pydantic model.
        config = crew_output.pydantic
        
        if not config:
            raise ValueError("Agent failed to return a valid config object.")

        # [NEW FIX] Safety Net for Vague Prompts
        if not config.end_time and not config.row_count:
            logger.warning("⚠️ No duration specified by Agent. Defaulting to 100 rows.")
            config.row_count = 100

        # [NEW] Deterministic Row Count Logic
        if config.row_count and config.row_count > 0:
            # Convert '30s' or '1min' to a Pandas Timedelta
            try:
                dt = pd.to_timedelta(config.time_interval)
                start = pd.to_datetime(config.start_time)
                
                # Calculate Exact End Time: Start + ((N-1) * Interval)
                # We subtract 1 because date_range is inclusive of start and end
                end = start + (dt * (config.row_count - 1))
                
                # Update config
                config.end_time = end.strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"🧮 Calculated exact end_time: {config.end_time} for {config.row_count} rows.")
            except Exception as e:
                logger.warning(f"⚠️ Date Math Error: {e}. row_count logic failed.")

        # Generate the data using the main system instance
        # Generate the data using the main system instance
        logger.info(f"✅ Validated config: {config.model_dump()}")
        sys = get_system_instance()
        df = await run_in_threadpool(sys.generate, config)
        logger.info(f"✅ Generated {len(df)} data points")

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
        logger.error(f"❌ Server Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/modify")
async def modify_and_stream_data(request: ModifyRequest):
    """
    Fills a gap between two points with AI-generated, bridged data.
    Delegates logic to modify.py.
    """
    try:
        # 1. Call the logic module
        df = await process_modification_logic(request)

        # 2. Stream the result (Controller Responsibility)
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=modified_segment.csv"
        return response

    except ValueError as ve:
        # Business logic errors (e.g. bad dates) -> 400 Bad Request
        logger.warning(f"❌ Modification Validation Error: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # System errors -> 500 Internal Server Error
        logger.error(f"❌ Modification System Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
