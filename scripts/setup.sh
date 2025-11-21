#!/bin/bash
# Setup script for virtual environment
#
# To activate the venv (use this if it gets deactivated):
#   source scripts/setup.sh
#
# To create/update the venv and install dependencies:
#   ./scripts/setup.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$PROJECT_ROOT/.venv"

# Function to find and activate the venv
activate_venv() {
    # Check if venv exists in project root (most common case)
    local venv_path="$PROJECT_ROOT/.venv"
    if [ ! -d "$venv_path" ]; then
        # Fallback: check in scripts directory
        venv_path="$SCRIPT_DIR/.venv"
    fi

    if [ ! -d "$venv_path" ]; then
        echo "Error: Virtual environment not found."
        echo "Looked in: $PROJECT_ROOT/.venv and $SCRIPT_DIR/.venv"
        echo "Run ./scripts/setup.sh first to create it."
        return 1 2>/dev/null || exit 1
    fi

    # Ensure venv activation persists even if commands fail
    set +e
    source "$venv_path/bin/activate"
    set -e
    echo "✓ Virtual environment activated: $(which python)"
}

# If script is being sourced (not executed), just activate the venv
if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    activate_venv
    return 0
fi

# Otherwise, do full setup
echo "Setting up virtual environment..."

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment at $VENV_DIR..."
    python -m venv "$VENV_DIR"
else
    echo "Virtual environment already exists at $VENV_DIR"
fi

# Activate in this subshell for installation
VENV_ACTIVATE="$VENV_DIR/bin/activate"
if [ -f "$VENV_ACTIVATE" ]; then
    source "$VENV_ACTIVATE"
else
    VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"
    if [ -f "$VENV_ACTIVATE" ]; then
        source "$VENV_ACTIVATE"
    fi
fi

echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "✓ Setup complete!"
echo ""
echo "To activate the virtual environment in your current shell, run:"
echo "  source scripts/setup.sh"
