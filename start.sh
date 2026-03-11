#!/bin/bash

# Quick Start Script for SynthIoT Backend
# Run this script to start the application

echo "🔍 Checking Python version..."
python --version

echo ""
echo "📦 Installing/Updating dependencies..."
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Dependencies installed successfully!"
    echo ""
    echo "🚀 Starting SynthIoT Backend..."
    echo "   API will be available at: http://localhost:8000"
    echo "   API docs at: http://localhost:8000/docs"
    echo ""
    python main.py
else
    echo ""
    echo "❌ Failed to install dependencies."
    echo "   Please make sure you're in the synthiot_env environment:"
    echo "   conda activate synthiot_env"
    exit 1
fi
