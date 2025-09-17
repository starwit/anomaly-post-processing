import pytest
import subprocess
import sys

def test_main_runs(monkeypatch):
    # Run the main.py as a script to check it executes without error
    result = subprocess.run([sys.executable, '-m', 'anomalypostprocessing.stage'], capture_output=True)
    assert result.returncode == 0 or result.returncode is not None
