#!/bin/bash
# Run tests for git-data-distiller

echo "Running tests for git-data-distiller..."
echo "======================================="

# Run pytest with coverage
pytest tests/ -v

# Run flake8 to check code quality
echo ""
echo "Running flake8 code quality checks..."
echo "======================================="
flake8 src/ --count --statistics

echo ""
echo "Testing complete!"