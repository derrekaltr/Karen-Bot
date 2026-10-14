"""The simulated end-to-end case flow must pass, start to finish."""

import os
import subprocess
import sys


def test_demo_e2e_resolves_case(tmp_path):
    env = {
        **os.environ,
        "KARENBOT_DATABASE_URL": f"sqlite:///{tmp_path}/demo.db",
        "KARENBOT_LLM_PROVIDER": "scripted",
    }
    result = subprocess.run(
        [sys.executable, "-m", "karenbot.demo.e2e"],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert result.returncode == 0, f"demo failed:\n{result.stdout}\n{result.stderr}"
    assert "case status: RESOLVED" in result.stdout
    assert "Demo complete" in result.stdout
