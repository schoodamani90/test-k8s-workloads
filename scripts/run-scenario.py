#!/usr/bin/env python3

import argparse
import concurrent
import glob
import json
import logging
import os
import subprocess
import sys
import time
from typing import List

from kubernetes import client, config
from measurements import gather_cluster_measurements, print_measurements

RELEASE_PREFIX = "bw-"
COSMOS_DEV_COSMOS_CONTEXT_NAME = "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos"
VALUES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/values"
TEMPLATES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/templates"

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
    install_group.add_argument("--print", "-p", action="store_true", default=True, help="Print collected data")

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

    return args, values_files

def get_scenarios(parser: argparse.ArgumentParser):
    try:
        return sorted(os.listdir(VALUES_DIR))
    except FileNotFoundError:
        parser.error(f"No scenarios found in {VALUES_DIR}")

def main():
    args, values_files = parse_args()
    logger.info(f"{'Uninstalling' if args.uninstall else 'Installing'} {args.scenario}")

    config.load_kube_config()
    # Safety check we're on the right cluster
    _, active_context = config.list_kube_config_contexts()
    current_context = active_context['name']
    expected_context = COSMOS_DEV_COSMOS_CONTEXT_NAME
    if current_context != expected_context:
        logger.error("Not using the expected context. scc to cosmos-dev-cosmos")
        sys.exit(1)

    if args.uninstall:
        uninstall_scenario(values_files, dry_run=args.dry_run, debug=args.debug)
    else:
        install_scenario(values_files, skip_install=args.skip_install, dry_run=args.dry_run, render_locally=args.render_locally, debug=args.debug, print=args.print)

def install_scenario(values_files: List[str], skip_install: bool=False, dry_run: bool=False, render_locally: bool=False, debug: bool=False, print: bool=True) -> List[str]:

    release_names = []
    install_cmds = []
    for values_file in values_files:
        filename = os.path.basename(values_file)
        install_id = filename.replace("values-", "").replace(".yaml", "")
        release_name = f"{RELEASE_PREFIX}{install_id}"
        release_names.append(release_name)

        if render_locally:
            render_templates(release_name, values_file, debug=debug)

        if not skip_install:
            # Install/upgrade the release
            install_cmd = f"helm upgrade --install {release_name} ./busybox-chart -f {values_file} --namespace {release_name} --create-namespace --wait --timeout 5m {'--debug' if debug else ''}{' --dry-run' if dry_run else ''}"
            logger.info(f"Installing {release_name} with {values_file}")
            install_cmds.append(install_cmd)

    if print:
        # Do not collect release info since that will be done after install
        measurements = gather_cluster_measurements()
        logger.info(f"Cluster measurements before:")
        print_measurements(measurements)

    if not skip_install:
        results = []
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(run_command, install_cmd, capture_output=debug)
                for install_cmd in install_cmds
            ]
            # Wait for all installs to complete
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
        end_time = time.time()
        logger.info(f"Installation and startup time: {end_time - start_time:.2f}s")

    if print:
        measurements = gather_cluster_measurements(release_names)
        logger.info(f"Cluster measurements after:")
        print_measurements(measurements)

    return release_names

def uninstall_scenario(values_files: List[str], dry_run: bool=False, debug: bool=False):
    uninstall_cmds = []
    for values_file in values_files:
        filename = os.path.basename(values_file)
        install_id = filename.replace("values-", "").replace(".yaml", "")
        release_name = f"{RELEASE_PREFIX}{install_id}"

        uninstall_cmd = f"helm uninstall {release_name} --namespace {release_name} --ignore-not-found --wait --timeout 5m {'--debug' if debug else ''}{' --dry-run' if dry_run else ''}"
        logger.info(f"Uninstalling {release_name}")
        uninstall_cmds.append(uninstall_cmd)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(run_command, uninstall_cmd, capture_output=debug)
            for uninstall_cmd in uninstall_cmds
        ]

        # Wait for all uninstalls to complete
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())


def render_templates(release_name: str, values_file: str, debug: bool=False):
    # Create output directory
    output_dir = f"{TEMPLATES_DIR}/{release_name}"
    os.makedirs(output_dir, exist_ok=True)

    # Render template for reference
    template_cmd = f"helm template {release_name} ./busybox-chart -f {values_file} --namespace {release_name} --create-namespace --output-dir {output_dir} {'--debug' if debug else ''}"
    logger.debug(f"Rendering templates for {release_name}")
    run_command(template_cmd, capture_output=False)


def run_command(cmd, check=True, capture_output=True, text=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=text)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running command '{cmd}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
