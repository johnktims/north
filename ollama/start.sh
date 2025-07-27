#!/bin/bash
set -e

# Default model is smollm2:135m if not provided
MODEL=${1:-smollm2:135m}

echo "Starting Ollama server..."
# Start Ollama server in the background
ollama serve &
SERVER_PID=$!

# Wait for Ollama server to be ready
echo "Waiting for Ollama server to be ready..."
wait-for-it -t 60 localhost:11434 -- echo "Ollama server is ready"

# Pull and run the specified model
echo "Running model: $MODEL"
ollama run $MODEL

# Keep the container running
wait $SERVER_PID