#!/bin/bash
# Quick installation script for Harvey OSINT

set -e

echo "======================================"
echo "Harvey OSINT Installation Script"
echo "======================================"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Found Python $PYTHON_VERSION"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "✗ pip3 not found. Please install pip3 first."
    exit 1
fi
echo "✓ pip3 is installed"

# Ask installation method
echo ""
echo "Choose installation method:"
echo "1) Install from PyPI (stable release)"
echo "2) Install from source (development)"
read -p "Enter choice [1-2]: " choice

case $choice in
    1)
        echo ""
        echo "Installing harvey-osint from PyPI..."
        pip3 install harvey-osint
        ;;
    2)
        echo ""
        echo "Installing from source..."
        if [ ! -f "setup.py" ]; then
            echo "✗ setup.py not found. Are you in the correct directory?"
            exit 1
        fi
        pip3 install -e .
        ;;
    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "======================================"
echo "✓ Installation complete!"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. Configure GitHub token (optional but recommended):"
echo "   $ harvey-config"
echo ""
echo "2. Start Harvey:"
echo "   $ harvey"
echo ""
echo "For help, visit: https://github.com/yourusername/harvey-osint"
echo ""