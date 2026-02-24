#!/bin/bash

# Installation script for SynthIoT backend dependencies
# This script installs packages in the correct order to avoid conflicts

set -e  # Exit on error

echo "🔧 Step 1: Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel build

echo ""
echo "📦 Step 2: Installing core scientific stack (numpy, pandas, scipy)..."
pip install numpy==1.26.4 pandas==1.5.3 scipy==1.15.3

echo ""
echo "🤖 Step 3: Installing TensorFlow, Keras, and related ML libraries..."
pip install tensorflow==2.15.1 keras==2.15.0 tensorflow-estimator==2.15.0 \
    tensorflow-probability==0.23.0 tensorboard==2.15.2 tensorboard-data-server==0.7.2

echo ""
echo "🧬 Step 4: Installing ydata-synthetic and ML tools..."
pip install ydata-synthetic==1.4.0 scikit-learn==1.3.2 joblib==1.5.3 \
    jax==0.4.30 jaxlib==0.4.30

echo ""
echo "🌐 Step 5: Installing web framework and HTTP tools..."
pip install fastapi==0.128.6 uvicorn==0.40.0 uvloop==0.22.1 \
    httptools==0.7.1 python-multipart==0.0.22 sse-starlette==3.2.0 \
    starlette==0.52.1 websockets==16.0

echo ""
echo "⚙️  Step 6: Installing configuration and environment tools..."
pip install python-dotenv==1.1.1 pydantic==2.11.10 pydantic-settings==2.10.1 \
    pydantic_core==2.33.2

echo ""
echo "🗄️  Step 7: Installing database and ORM tools..."
pip install SQLAlchemy==2.0.46 alembic==1.18.4 psycopg2-binary==2.9.11 \
    aiosqlite==0.21.0 greenlet==3.3.2

echo ""
echo "🔐 Step 8: Installing authentication and security tools..."
pip install bcrypt==5.0.0 PyJWT==2.11.0 cryptography==46.0.4

echo ""
echo "🤖 Step 9: Installing AI/LLM frameworks..."
pip install langchain-core==1.2.9 langchain-groq==1.1.2 langsmith==0.7.0 \
    crewai==1.9.3 crewai-tools==1.9.3 groq==0.37.1 openai==1.83.0 \
    litellm==1.81.9 instructor==1.12.0 tiktoken==0.8.0

echo ""
echo "🧠 Step 10: Installing vector DB and embeddings tools..."
pip install chromadb==1.1.1 lancedb==0.5.7 huggingface_hub==0.36.2 \
    tokenizers==0.20.3 onnxruntime==1.24.1

echo ""
echo "🔍 Step 11: Installing document parsing tools..."
pip install beautifulsoup4==4.13.5 pdfminer.six==20251230 pdfplumber==0.11.9 \
    PyMuPDF==1.26.7 python-docx==1.2.0 lxml==6.0.2 openpyxl==3.1.5

echo ""
echo "📊 Step 12: Installing data and serialization tools..."
pip install pyarrow==23.0.0 orjson==3.11.7 PyYAML==6.0.3 \
    matplotlib==3.10.8 pillow==12.1.0

echo ""
echo "🔬 Step 13: Installing testing and logging tools..."
pip install pytest==9.0.2 pytest-asyncio==1.3.0 httpx==0.28.1 \
    python-json-logger==4.0.0

echo ""
echo "🧰 Step 14: Installing miscellaneous utilities..."
pip install requests==2.32.5 tenacity==9.1.4 backoff==2.2.1 \
    rich==14.3.2 typer==0.21.1 tqdm==4.67.3 python-dateutil==2.9.0.post0 \
    pytz==2025.2 semver==3.0.4 diskcache==5.6.3 posthog==5.4.0 \
    mcp==1.23.3 portalocker==2.7.0

echo ""
echo "✅ All dependencies installed successfully!"
echo ""
echo "To verify the installation, run:"
echo "  python -c 'import tensorflow; import ydata_synthetic; import crewai; import sqlalchemy; import chromadb; print(\"All imports successful!\")'"
