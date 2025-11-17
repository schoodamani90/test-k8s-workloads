import concurrent.futures
import logging
import subprocess

from typing import List
from pathlib import Path

MAX_WORKERS = 10

SCRIPT_DIR = Path(__file__).parent.parent
VALUES_DIR = SCRIPT_DIR / "build" / "values"
TEMPLATES_DIR = SCRIPT_DIR / "build" / "templates"
OUTPUT_DIR = SCRIPT_DIR / "output"

logger = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')


def run_commands(cmds: List[str], dry_run: bool = False, capture_output: bool = True):
    """
    Run a list of shell commands in parallel and wait for all to complete
    """
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(run_command, cmd, dry_run=dry_run, capture_output=capture_output)
            for cmd in cmds
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results


def run_command(cmd, dry_run: bool = False, check=True, capture_output=True, text=True):
    """Run a shell command and return the result"""
    try:
        if dry_run:
            cmd = f"echo [DRY-RUN] '{cmd}'"
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=text)
        return result
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error running command '{cmd}'") from e
