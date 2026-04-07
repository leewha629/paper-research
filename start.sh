#!/bin/bash
set -e
echo "=== Paper Research App ==="

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate
echo "Installing Python dependencies..."
pip install -r requirements.txt -q

if [ ! -d "frontend/node_modules" ]; then
  echo "Installing frontend dependencies..."
  cd frontend && npm install && cd ..
fi
echo "Building frontend..."
cd frontend && npm run build && cd ..

mkdir -p data/pdfs

echo "Starting server at http://localhost:7010"
cd backend && uvicorn main:app --host 0.0.0.0 --port 7010 --reload
