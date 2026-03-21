#!/bin/sh

SESSION="seer-ai"

tmux new-session -d -s "$SESSION"

tmux split-window -h -t "$SESSION":0

tmux send-keys -t "$SESSION":0.0 'cd ./backend && source ./.venv/bin/activate.fish && uv run python main.py' C-m
tmux send-keys -t "$SESSION":0.1 'cd ./frontend && npm run dev' C-m

tmux select-layout -t "$SESSION":0 tiled

tmux attach -t "$SESSION"