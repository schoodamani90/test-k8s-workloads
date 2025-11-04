import logging
import os
import time

from typing import Dict, List
from pathlib import Path

from kubernetes import client, config

from utils import run_command, run_commands

logger = logging.getLogger(__name__)

VERIFICATION_ATTEMPTS = 5
VERIFICATION_RETRY_DELAY = 10


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

def verify_install(release_names: List[str]) -> bool:
    """
    Verify that all releases have successfully started
    We install with --wait, so this should be somewhat redundant, but want to
    confirm.
    """
    logger.info(f"Verifying install")
    install_verified = False
    attempt = 0
    while (not install_verified) and (attempt < VERIFICATION_ATTEMPTS):
        attempt += 1
        install_verified = all(verify_release(release_name) for release_name in release_names)
        if not install_verified:
            logger.info(f"Install verification failed. Retrying...")
            time.sleep(VERIFICATION_RETRY_DELAY)
    if not install_verified:
        raise Exception("Install verification failed")
    logger.info(f"Install verified")

def verify_release(release_name: str) -> bool:
    """
    Verify that all pods from the given release names have successfully started
    """
    logger.debug(f"Verifying install of {release_name}")
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace=release_name, label_selector=f"app.kubernetes.io/name=busybox-chart,app.kubernetes.io/instance={release_name}")
    # TODO: Confirm pod count matches the desired count
    if len(pods.items) == 0:
        logger.error(f"No pods found in namespace {release_name}")
        return False
    not_running_count = 0
    for pod in pods.items:
        if pod.status.phase != "Running":
            logger.debug(f"Pod {pod.metadata.name} in namespace {release_name} is not running: {pod.status.phase}")
            not_running_count += 1
    if not_running_count > 0:
        logger.error(f"Found {not_running_count} pods in namespace {release_name} that are not running")
        return False
    logger.debug(f"All pods in namespace {release_name} are running")
    return True

def verify_cluster(cluster_context_name: str):
    """Verify we're on the right cluster
    FUTURE: Allow specifying other clusters
    """
    config.load_kube_config()
    # Safety check we're on the right cluster
    _, active_context = config.list_kube_config_contexts()
    current_context = active_context['name']
    expected_context = cluster_context_name
    if current_context != expected_context:
        raise Exception("Not using the expected context. scc to cosmos-dev-cosmos")

def render_templates(release_name: str, values_path: Path, output_dir: Path, debug: bool=False):
    """
    Render the templates for a given release and values path.
    Thse are used for reference only.
    """
    # Create output directory
    output_dir = f"{output_dir}/{release_name}"
    os.makedirs(output_dir, exist_ok=True)

    # Render template for reference
    template_cmd = f"helm template {release_name} ./busybox-chart -f {values_path} --namespace {release_name} --create-namespace --output-dir {output_dir} {'--debug' if debug else ''}"
    logger.debug(f"Rendering templates for {release_name}")
    run_command(template_cmd, capture_output=not debug)

def restart_deployments(release_names: List[str], debug: bool=False):
    """
    Restart the deployments for the given release names
    """
    restart_cmds = []
    for release_name in release_names:
        restart_cmd = f"kubectl rollout restart deployment {release_name} --namespace {release_name}"
        restart_cmds.append(restart_cmd)
    run_commands(restart_cmds, capture_output=not debug)
