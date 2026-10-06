#!/bin/sh
# Open in macOS Terminal for a hidden check-code prompt.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/creator5-probe ]; then
    echo "Set up the Python environment using README.md first."
else
    .venv/bin/creator5-probe
fi
printf '\nPress Return to close. '
read -r answer
