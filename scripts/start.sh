#!/bin/bash
# Start script for voice AI bot

set -e

echo "=========================================="
echo "Starting Voice AI Bot"
echo "=========================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p debug_audio
mkdir -p knowledge

# Run the application
echo "Starting application..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
