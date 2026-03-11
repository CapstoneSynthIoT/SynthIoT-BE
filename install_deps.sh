#!/bin/bash

echo "🔧 SynthIoT Backend - Dependency Installation Fix"
echo "=================================================="
echo ""

# Get conda base path
CONDA_BASE=$(conda info --base)
echo "📍 Conda base: $CONDA_BASE"

# Source conda
source "$CONDA_BASE/etc/profile.d/conda.sh"

# Deactivate any active environment
conda deactivate 2>/dev/null || true

# Activate synthiot_env
echo "🔄 Activating synthiot_env..."
conda activate synthiot_env

# Verify Python version
echo ""
echo "✅ Python version check:"
python --version
which python

# Check if we're using Python 3.11
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$PYTHON_VERSION" != "3.11" ]; then
    echo ""
    echo "❌ ERROR: Wrong Python version detected: $PYTHON_VERSION"
    echo "   Expected: 3.11"
    echo ""
    echo "Please run these commands manually:"
    echo "   source $(conda info --base)/etc/profile.d/conda.sh"
    echo "   conda deactivate"
    echo "   conda activate synthiot_env"
    echo "   python --version  # Should show Python 3.11.x"
    exit 1
fi

echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation successful!"
    echo ""
    echo "🚀 To run the application:"
    echo "   python main.py"
else
    echo ""
    echo "❌ Installation failed. Please check the error messages above."
    exit 1
fi
