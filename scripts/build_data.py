import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIPELINES = ROOT / "pipelines"


def main() -> None:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(PIPELINES) + (
        os.pathsep + existing_pythonpath if existing_pythonpath else ""
    )

    commands = [
        [sys.executable, "-m", "ecometrix_pipeline.run"],
        [sys.executable, str(ROOT / "model" / "baseline_relationship.py")],
        [sys.executable, str(ROOT / "model" / "run_models.py")],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
