#!/usr/bin/env python3
"""
Collects deployment distribution data for a list of namespaces within a cluster.

This is best for analyzing "real" deployments, as opposed to the synthetic ones used for testing.
"""

import argparse
import logging

from datetime import datetime, timedelta
from typing import Dict, Iterable
from kubernetes import client, config

from deploy import verify_cluster
from measurements import Measurements, ClusterNodeData, DeploymentDistributionData
from postprocess import PostprocessedData, ExperimentResult
from utils import setup_logging, OUTPUT_DIR
from scenarios import Scenario, Mechanism, parse_scenario

PROD_LIVE_MAIN_CONTEXT_NAME = "arn:aws:eks:us-east-1:906324658258:cluster/prod-live-main"
TEST_NAMESPACES = [
    "monolith"
]

# While maximal spread is the ideal, for many of these tests it's not possible to use all nodes.
# It's also diffcult to filter out nodes that are not eligible to run pods due to taints or being fully utilized.
# So we can include it when we want to see, but for the most part we'll just ignore them and focus on the distribution
# among the nodes that got at least one pod.
INCLUDE_UNUSED_NODES = False

logger = logging.getLogger(__name__)


def gather_cluster_measurements(namespaces: Iterable[str] = []) -> Measurements:
    node_info = get_node_info()
    deployments: Dict[str, DeploymentDistributionData] = {}
    for namespace in namespaces:
        deployments.update(gather_deployment_distribution_data(
            namespace, node_info.eligible_node_count))
    measurements = Measurements(
        cluster=node_info,
        deployments=deployments,
    )
    return measurements


def get_node_info() -> ClusterNodeData:  # pyright: ignore[reportReturnType]
    """Get the number of nodes in the cluster"""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        nodes = v1.list_node()
        eligible_nodes = []
        for node in nodes.items:
            # exclude fargate
            if not node.metadata.name.startswith('fargate-'):
                eligible_nodes.append(node)
            # TODO exclude full nodes
            # Getting the unallocated cpu + memory for a node is nontrivial.
            # Kubectl does it client-side when running describe node.
            # if free_cpu >= required_free_cpu and free_memory >= required_free_memory:
            # TODO exclude tainted nodes we don't tolerate
            # TODO anything else? Probably

        cluster_node_info = ClusterNodeData(
            node_count=len(nodes.items),
            eligible_node_count=len(eligible_nodes),
        )
        return cluster_node_info
    except client.ApiException as e:
        handle_api_exception(e)


def handle_api_exception(e: client.ApiException):
    if e.status == 401:
        logger.error("Not authorized. Check credentials.")
        raise Exception("kubernetes authentication error") from e
    else:
        logger.error(f"Error getting node count: {e}")
        raise Exception("kubernetes API error") from e


def gather_deployment_distribution_data(namespace: str, cluster_node_count: int) -> Dict[str, DeploymentDistributionData]:
    """
    Gather data about a deployment's distribution across nodes.

    Returns:
        Dictionary of deployment name to DeploymentDistributionData.
    """
    config.load_kube_config()
    core_v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    ddd = {}

    deployments = apps_v1.list_namespaced_deployment(namespace=namespace)
    for deployment in deployments.items:
        deployment_name = deployment.metadata.name

        logger.info(f"[{deployment_name}] Gathering deployment data")
        # Match the selector labels from the Helm chart template.
        deployment_spec = apps_v1.read_namespaced_deployment(
            deployment_name, namespace=namespace).spec  # pyright: ignore[reportAttributeAccessIssue, reportOptionalMemberAccess]

        if deployment_spec.replicas <= 1:
            # 0 or 1 replicas are not relevant and only make it harder to calculate statistics.
            logger.info(f"[{deployment_name}] Deployment has only {deployment_spec.replicas} replicas, skipping")
            continue

        label_selector = ",".join(
            [f"{key}={value}" for key, value in deployment_spec.selector.match_labels.items()])
        # Ignore anything not running. We should have verified this prior to gathering data.
        # Some terminating pods may still be in the API from prior runs/restarts, but we'll ignore them.
        field_selector = "status.phase=Running"
        pods = core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector,
            field_selector=field_selector,
        )
        total_pods = len(pods.items)

        node_to_podcount = {}
        for pod in pods.items:
            node_to_podcount[pod.spec.node_name] = node_to_podcount.get(
                pod.spec.node_name, 0) + 1

        nodes_used = len(node_to_podcount)
        logger.debug(
            f"[{deployment_name}] {total_pods} pods spread across {nodes_used} nodes")
        logger.debug(
            f"[{deployment_name}] Node names: {node_to_podcount.keys()}")

        unused_nodes = cluster_node_count - len(node_to_podcount.keys())
        # TODO only include unused nodes if they have room for a pod
        pod_counts = list(node_to_podcount.values()) + ([0] * unused_nodes if (
            INCLUDE_UNUSED_NODES and unused_nodes and max(node_to_podcount.values()) > 1) else [])

        distribution_info = DeploymentDistributionData(
            deployment_name, pod_counts)
        logger.debug(
            f"[{deployment_name}] Deployment distribution: {distribution_info}")
        ddd[deployment_name] = distribution_info
    return ddd


def main():
    setup_logging()
    args = parse_args()
    cluster_name = args.cluster_context.split("/")[-1]

    verify_cluster(args.cluster_context)

    timestamp = datetime.now()
    measurements = gather_cluster_measurements(args.namespaces)
    logger.debug(f"Measurements: {measurements}")

    postprocessed_data = PostprocessedData(None, measurements)

    experiment_result = ExperimentResult(args, cluster_name, timestamp, timedelta(0), postprocessed_data, [measurements])
    experiment_result.write_to_file(OUTPUT_DIR / cluster_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect cluster measurements")

    parser.add_argument("--cluster-context", type=str, required=False, default=PROD_LIVE_MAIN_CONTEXT_NAME)
    parser.add_argument("--namespaces", type=str, nargs="+", required=False, default=TEST_NAMESPACES)
    # We just use a dummy scenario name here to avoid having to pass it to the ExperimentResult constructor
    scenario = Scenario(
        name="DataCollection",
        description="Take measurements from existing deployments on a cluster",
        mechanism=Mechanism.NONE,
        workloads_per_nodepool=0,
        replicas=0,
    )
    parser.add_argument("--scenario", type=parse_scenario, required=False, default=scenario, help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    main()
