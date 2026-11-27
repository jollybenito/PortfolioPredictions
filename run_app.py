"""Start Streamlit and the lightweight in-process market updater."""

import os
import signal
import subprocess
import sys

from daily_market_scheduler import start_scheduler


def main() -> int:
    start_scheduler()
    port = os.getenv("PORT", "8080")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            f"--server.port={port}",
            "--server.address=0.0.0.0",
        ]
    )

    def stop_streamlit(_signum, _frame):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop_streamlit)
    signal.signal(signal.SIGINT, stop_streamlit)
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
