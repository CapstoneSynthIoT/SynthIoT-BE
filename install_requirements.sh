#!/bin/bash

# Installation script for SynthIoT backend dependencies
# This script installs packages in the correct order to avoid conflicts

set -e  # Exit on error

echo "🔧 Step 1: Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel

echo ""
echo "📦 Step 2: Installing core dependencies (numpy, pandas)..."
pip install numpy==1.23.5 pandas==1.5.3

echo ""
echo "🤖 Step 3: Installing TensorFlow and Keras..."
pip install tensorflow==2.12.0 keras==2.12.0

echo ""
echo "🧬 Step 4: Installing ydata-synthetic and ML tools..."
pip install ydata-synthetic==1.4.0 scikit-learn==1.3.2 joblib

echo ""
echo "🌐 Step 5: Installing web framework..."
pip install fastapi uvicorn[standard]

echo ""
echo "⚙️  Step 6: Installing configuration and environment tools..."
pip install python-dotenv pydantic-settings

echo ""
echo "🤖 Step 7: Installing AI/LLM frameworks..."
pip install langchain-groq crewai

echo ""
echo "🔍 Step 8: Installing additional tools..."
pip install python-json-logger pytest pytest-asyncio httpx

echo ""
echo "✅ All dependencies installed successfully!"
echo ""
echo "To verify the installation, run:"
echo "  python -c 'import tensorflow; import ydata_synthetic; import crewai; print(\"All imports successful!\")'"
