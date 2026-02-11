#!/bin/bash

# SynthIoT Backend Setup Script
# This script sets up the Python environment and installs dependencies

echo "🚀 SynthIoT Backend Setup"
echo "=========================="

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "❌ Error: conda not found. Please install Miniconda or Anaconda first."
    exit 1
fi

# Check if synthiot_env exists
if conda env list | grep -q "synthiot_env"; then
    echo "✅ Environment 'synthiot_env' already exists"
else
    echo "📦 Creating new conda environment with Python 3.11..."
    conda create -n synthiot_env python=3.11 -y
fi

echo ""
echo "🔄 Activating environment..."
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate synthiot_env

echo ""
echo "📥 Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the application:"
echo "  1. conda activate synthiot_env"
echo "  2. python main.py"
echo ""
echo "The API will be available at: http://localhost:8000"
echo "API docs will be at: http://localhost:8000/docs"
