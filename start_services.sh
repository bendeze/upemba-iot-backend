#!/bin/bash

# Exit if any command fails
set -e

# Ensure we are in the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR/backend"

SESSION_NAME="upemba"

# Check if session already exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo "Session $SESSION_NAME already exists. Attaching to it..."
    tmux attach-session -t $SESSION_NAME
    exit 0
fi

echo "Starting Upemba IoT Backend Services..."

# Create a new tmux session detached (-d)
tmux new-session -d -s $SESSION_NAME

# Pane 0 (Left): Django Web Server (API)
tmux send-keys -t $SESSION_NAME "source .venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME "python manage.py runserver 0.0.0.0:8000" C-m

# Split the window horizontally (Side-by-side)
tmux split-window -h -t $SESSION_NAME

# Pane 1 (Top Right): MQTT Listener
tmux send-keys -t $SESSION_NAME "source .venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME "python manage.py mqtt_listener" C-m

# Split the right pane vertically (Top & Bottom on the right)
tmux split-window -v -t $SESSION_NAME

# Pane 2 (Bottom Right): Machine Learning Worker (Django Q)
tmux send-keys -t $SESSION_NAME "source .venv/bin/activate" C-m
tmux send-keys -t $SESSION_NAME "python manage.py qcluster" C-m

# Arrange the panes nicely
tmux select-layout -t $SESSION_NAME main-vertical

echo "All services started!"
echo "Attaching to tmux session. Press Ctrl+B, then D to detach and leave them running."
sleep 2

# Attach to the session so the user can see the logs
tmux attach-session -t $SESSION_NAME
