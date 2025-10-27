#!/usr/bin/env python3

import argparse
import concurrent
import glob
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta
from typing import Dict, List

from kubernetes import config
from measurements import gather_cluster_measurements
from postprocess import PostprocessedData

RELEASE_PREFIX = "bw-"
COSMOS_DEV_COSMOS_CONTEXT_NAME = "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos"
VALUES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/values"
TEMPLATES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/templates"
MEASUREMENTS_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/output"

MAX_WORKERS = 10

def setup_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logger = logging.getLogger(__name__)
    return logger

logger = setup_logging()

def parse_args():
    parser = argparse.ArgumentParser(description="Install a scenario")
    parser.add_argument("scenario", type=str, help="The name of the scenario to install", choices=get_scenarios(parser))
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")
    parser.add_argument("--dry-run", action="store_true", help="Do a dry run")
    parser.add_argument("--render-locally", action="store_true", help="Render the templates locally")
    install_group = parser.add_mutually_exclusive_group(required=False)
    install_group.add_argument("--uninstall", "-u", action="store_true", help="Uninstall the scenario instead of installing it")
    install_group.add_argument("--skip-install", "-s", action="store_true", help="Take measurements without performing the install")
    install_group.add_argument("--no-print", "-np", action="store_true", help="Do not print to console")

    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # kubernetes is WAY too verbose in debug mode
        logging.getLogger("kubernetes").setLevel(logging.INFO)
    scenario_dir = f"{VALUES_DIR}/{args.scenario}"
    if not os.path.exists(scenario_dir):
        parser.error(f"Scenario directory '{scenario_dir}' does not exist")

    values_pattern = f"{VALUES_DIR}/{args.scenario}/*.yaml"
    values_files = glob.glob(values_pattern)

    if not values_files:
        parser.error(f"No .yaml files found in {scenario_dir}")

    release_to_values_path = {}
    release_names = []
    for values_file in values_files:
        values_path = Path(values_file)
        install_id = values_path.name.replace("values-", "").replace(".yaml", "")
        release_name = f"{RELEASE_PREFIX}{install_id}"
        release_names.append(release_name)
        release_to_values_path[release_name] = values_path

    return args, release_to_values_path

def get_scenarios(parser: argparse.ArgumentParser):
    try:
        return sorted(os.listdir(VALUES_DIR))
    except FileNotFoundError:
        parser.error(f"No scenarios found in {VALUES_DIR}")

def main():
    try:
        args, release_to_values = parse_args()

        logger.info(f"Scenario {args.scenario} loaded. {len(release_to_values)} releases")
        logger.debug(f"Release names: {release_to_values.keys()}")

        verify_cluster()

        measurements_pre = None
        if (not args.no_print) and (not args.skip_install):
            # Do not collect release info since that will be done after install
            measurements_pre = gather_cluster_measurements()
            logger.info(f"Pre-install measurements:")
            measurements_pre.print()

        if args.render_locally:
            logger.info(f"Rendering templates locally for {args.scenario}")
            for release_name, values_path in release_to_values.items():
                render_templates(release_name, values_path, debug=args.debug)

        install_time = None
        if not args.skip_install:
            start_time = datetime.now()
            if args.uninstall:
                logger.info(f"Uninstalling {args.scenario}")
                uninstall_scenario(release_to_values.keys(), dry_run=args.dry_run, debug=args.debug)
            else:
                logger.info(f"Installing {args.scenario}")
                install_scenario(release_to_values, dry_run=args.dry_run, debug=args.debug)
            end_time = datetime.now()
            install_time = timedelta(seconds=round((end_time - start_time).total_seconds()))
            logger.info(f"{'Uninstall' if args.uninstall else 'Install'} time: {install_time}s")

        if not args.uninstall:
            measurements_post = gather_cluster_measurements(release_to_values.keys())

            if not args.no_print:
                logger.info(f"Post-install measurements:")
                measurements_post.print()

            postprocessed_data = PostprocessedData(measurements_pre, measurements_post).to_dict()
            if not args.no_print:
                logger.info(f"Postprocessed data: {postprocessed_data}")

            timestamp = datetime.now().isoformat(timespec='seconds')
            measurements_file = f"{MEASUREMENTS_DIR}/{args.scenario}/{args.scenario}-{timestamp}.json"
            logger.info(f"Saving measurements to {measurements_file}")
            os.makedirs(f"{MEASUREMENTS_DIR}/{args.scenario}", exist_ok=True)
            with open(measurements_file, 'w') as f:
                data = {
                    "args": vars(args),
                    "timestamp": timestamp,
                    "install_time": str(install_time),
                    "postprocessed": postprocessed_data,
                    "measurements_pre": measurements_pre.to_dict(),
                    "measurements_post": measurements_post.to_dict(),
                }
                json.dump(data, f, indent=4)

        logger.info("Done")
    except Exception:
        logger.exception(f"Error running scenario {args.scenario}")
        sys.exit(1)

def verify_cluster():
    """Verify we're on the right cluster
    FUTURE: Allow specifying other clusters
    """
    config.load_kube_config()
    # Safety check we're on the right cluster
    _, active_context = config.list_kube_config_contexts()
    current_context = active_context['name']
    expected_context = COSMOS_DEV_COSMOS_CONTEXT_NAME
    if current_context != expected_context:
        raise Exception("Not using the expected context. scc to cosmos-dev-cosmos")

def install_scenario(release_to_values: Dict[str, Path], dry_run: bool=False, debug: bool=False) -> List[str]:
    install_cmds = []
    for release_name, values_path in release_to_values.items():
        # Install/upgrade the release
        install_cmd = f"helm upgrade --install {release_name} ./busybox-chart -f {values_path} --namespace {release_name} --create-namespace --wait --timeout 5m {'--debug' if debug else ''}{' --dry-run' if dry_run else ''}"
        logger.info(f"Installing {release_name} with {values_path.name}")
        install_cmds.append(install_cmd)
    run_commands(install_cmds, capture_output=not debug)

def uninstall_scenario(release_names: List[str], dry_run: bool=False, debug: bool=False):
    uninstall_cmds = []
    for release_name in release_names:
        uninstall_cmd = f"helm uninstall {release_name} --namespace {release_name} --ignore-not-found --wait --timeout 5m {'--debug' if debug else ''}{' --dry-run' if dry_run else ''}"
        logger.info(f"Uninstalling {release_name}")
        uninstall_cmds.append(uninstall_cmd)
    run_commands(uninstall_cmds, capture_output=not debug)

def render_templates(release_name: str, values_path: Path, debug: bool=False):
    # Create output directory
    output_dir = f"{TEMPLATES_DIR}/{release_name}"
    os.makedirs(output_dir, exist_ok=True)

    # Render template for reference
    template_cmd = f"helm template {release_name} ./busybox-chart -f {values_path} --namespace {release_name} --create-namespace --output-dir {output_dir} {'--debug' if debug else ''}"
    logger.debug(f"Rendering templates for {release_name}")
    run_command(template_cmd, capture_output=False)

def run_commands(cmds: List[str], capture_output: bool=True):
    """
    Run a list of shell commands in parallel and wait for all to complete
    """
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(run_command, cmd, capture_output=capture_output)
            for cmd in cmds
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    return results

def run_command(cmd, check=True, capture_output=True, text=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=text)
        return result
    except subprocess.CalledProcessError as e:
        raise Exception(f"Error running command '{cmd}'") from e

if __name__ == "__main__":
    main()
