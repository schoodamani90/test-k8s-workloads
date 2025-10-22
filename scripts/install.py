#!/usr/bin/env python3

import argparse
import glob
import json
import logging
import os
import subprocess
import sys
from typing import List

from kubernetes import client, config

RELEASE_PREFIX = "bw-"
COSMOS_DEV_COSMOS_CONTEXT_NAME = "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos"
VALUES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/values"
TEMPLATES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/templates"

def setup_logging() -> logging.Logger:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s'))
    logger.addHandler(handler)
    return logger

logger = setup_logging()

def parse_args():
    parser = argparse.ArgumentParser(description="Install a scenario")
    parser.add_argument("scenario", type=str, help="The name of the scenario to install", choices=get_scenarios())
    parser.add_argument("--uninstall", action="store_true", help="Uninstall the scenario instead of installing it")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    return parser.parse_args()

def main():

    args = parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    scenario_name = args.scenario

    logger.info(f"{'Uninstalling' if args.uninstall else 'Installing'} {scenario_name}")

    scenario_dir = f"{VALUES_DIR}/{scenario_name}"
    if not os.path.exists(scenario_dir):
        logger.error(f"Scenario directory '{scenario_dir}' does not exist")
        sys.exit(1)

    config.load_kube_config()
    # Safety check we're on the right cluster
    _, active_context = config.list_kube_config_contexts()
    current_context = active_context['name']
    expected_context = COSMOS_DEV_COSMOS_CONTEXT_NAME
    if current_context != expected_context:
        logger.error("Not using the expected context. scc to cosmos-dev-cosmos")
        sys.exit(1)

    logger.info(f"Cluster measurements before: {gather_cluster_measurements()}")

    # Process each values file
    values_pattern = f"{VALUES_DIR}/{scenario_name}/*.yaml"
    values_files = glob.glob(values_pattern)

    if not values_files:
        logger.error(f"No .yaml files found in {scenario_dir}")
        sys.exit(1)

    if args.uninstall:
        uninstall_scenario(values_files)
    else:
        install_scenario(values_files, args.debug)


    logger.info(f"Cluster measurements after: {gather_cluster_measurements()}")

def run_command(cmd, check=True, capture_output=True, text=True):
    """Run a shell command and return the result"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=capture_output, text=text)
        return result
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running command '{cmd}': {e}")
        sys.exit(1)

def get_scenarios():
    try:
        return sorted(os.listdir("build/values/"))
    except FileNotFoundError:
        logger.error("No scenarios found")
        sys.exit(1)

def install_scenario(values_files: List[str], render_locally: bool=False) -> List[str]:
    release_names = []
    for values_file in values_files:

        filename = os.path.basename(values_file)
        install_id = filename.replace("values-", "").replace(".yaml", "")
        release_name = f"{RELEASE_PREFIX}{install_id}"
        release_names.append(release_name)

        if render_locally:
            render_templates(release_name, values_file)

        # Install/upgrade the release
        install_cmd = f"helm upgrade --install {release_name} ./busybox-chart -f {values_file} --namespace {release_name} --create-namespace --wait --timeout 5m"
        logger.info(f"Installing {release_name} with {values_file}")
        run_command(install_cmd, capture_output=False)

    for release_name in release_names:
        gather_pod_distribution_info(release_name)

    return release_names

def uninstall_scenario(values_files: List[str]):
    for values_file in values_files:
        filename = os.path.basename(values_file)
        install_id = filename.replace("values-", "").replace(".yaml", "")
        release_name = f"{RELEASE_PREFIX}{install_id}"

        uninstall_cmd = f"helm uninstall {release_name} --namespace {release_name} --ignore-not-found --wait --timeout 5m"
        logger.info(f"Uninstalling {release_name}")
        run_command(uninstall_cmd, capture_output=False)


def render_templates(release_name: str, values_file: str):
    # Create output directory
    output_dir = f"{TEMPLATES_DIR}/{release_name}"
    os.makedirs(output_dir, exist_ok=True)

    # Render template for reference
    template_cmd = f"helm template {release_name} ./busybox-chart -f {values_file} --namespace {release_name} --create-namespace --output-dir {output_dir} --debug"
    logger.debug(f"Rendering templates for {release_name}...")
    run_command(template_cmd, capture_output=False)

def gather_cluster_measurements() -> dict:
    measurements = {}
    measurements["node_count"] = get_node_count()
    # TODO more
    return measurements

def gather_pod_distribution_info(namespace: str):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)
    pod_count = len(pods.items)
    logger.debug(f"Found {pod_count} pods in {namespace}")
    logger.debug(f"Pods: {pods.items}")
    node_names = [pod.spec.node_name for pod in pods.items]
    node_names_set = set(node_names)
    node_count = len(node_names_set)
    logger.info(f"{pod_count} pods in {namespace} are spread across {node_count} nodes")
    if node_count !=  pod_count:
        logger.warning("At least two pods are sharing a node")
    # TODO more info

def get_node_count():
    """Get the number of nodes in the cluster"""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        nodes = v1.list_node()
        return len(nodes.items)
    except client.exceptions.ApiException as e:
        handle_api_exception(e)

def handle_api_exception(e: client.exceptions.ApiException):
    if e.status == 401:
        print("Not authorized to access the cluster")
        sys.exit(1)
    else:
        print(f"Error getting node count: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
