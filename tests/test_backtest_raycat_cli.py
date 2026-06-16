import subprocess
import sys
from pathlib import Path


def test_raycat_help_does_not_run_backtest():
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "backtest_raycat.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "raycat.substack.com 股票推荐回测" in result.stdout or "raycat.substack.com 股票推荐回测" in result.stderr
