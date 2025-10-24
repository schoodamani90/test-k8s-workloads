import logging
import math
import statistics
import json
from typing import List
from kubernetes import client, config

logger = logging.getLogger(__name__)

class ClusterNodeInfo:
    """Class representing cluster information."""
    def __init__(self, node_count: int, eligible_node_count: int):
        self.node_count = node_count
        self.eligible_node_count = eligible_node_count

    def __str__(self) -> str:
        """String representation of ClusterNodeInfo."""
        return json.dumps(
            self,
            default=vars,
            sort_keys=False,
            indent=4)

class DeploymentDistributionInfo:
    """Class representing deployment information and statistics."""

    def __init__(self, pod_counts: List[int]):
        """Initialize DeploymentDistributionInfo with all statistics.

        Args:
            pod_counts: List of pod counts per node
        """
        self.total_pods = sum(pod_counts)
        self.pod_counts = pod_counts
        self.nodes_used = len(pod_counts)
        self.max_pods = max(pod_counts)
        self.min_pods = min(pod_counts)
        self.node_skew = self.max_pods - self.min_pods
        self.mean_pods = statistics.mean(pod_counts)
        self.median_pods = statistics.median(pod_counts)
        self.coefficient_of_variation = self._calculate_coefficient_of_variation(pod_counts)
        self.gini_coefficient = self._calculate_gini_coefficient(pod_counts)
        self.jain_fairness_index = self._calculate_jain_fairness_index(pod_counts)

    def _calculate_coefficient_of_variation(self, values: List[int]):
        """Calculate Coefficient of Variation

        <0.1: Very low variation
        0.1-0.3: Low variation
        0.3-0.5: Moderate variation
        >0.5: High variation
        """
        return statistics.stdev(values) / statistics.mean(values) if statistics.mean(values) > 0 else 0

    def _calculate_gini_coefficient(self, values: List[int]):
        """Calculate Gini Coefficient for inequality measurement

        0.0-0.2: Very balanced
        0.2-0.4: Moderately balanced
        0.4-0.6: Somewhat unbalanced
        0.6+: Highly unbalanced
        """
        if not values:
            return 0
        sorted_values = sorted(values)
        n = len(sorted_values)

        cumsum = 0
        for i, value in enumerate(sorted_values):
            cumsum += (i + 1) * value

        return (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n

    def _calculate_jain_fairness_index(self, values: List[int]):
        """Calculate Jain's Fairness Index

        0.9-1.0: Excellent fairness
        0.8-0.9: Good fairness
        0.7-0.8: Fair
        <0.7: Poor fairness
        """
        if not values or sum(values) == 0:
            return 0

        n = len(values)
        sum_squared = sum(x**2 for x in values)
        sum_values = sum(values)

        return (sum_values**2) / (n * sum_squared)

    def _to_dict(self, round_values=False) -> dict:
        """Convert DeploymentDistributionInfo to dictionary format.

        Returns:
            Dictionary representation of the deployment info.
        """
        return {
            'total_pods': self.total_pods,
            'pod_counts': self.pod_counts,
            'nodes_used': self.nodes_used,
            'max_pods': self.max_pods,
            'min_pods': self.min_pods,
            'node_skew': self.node_skew,
            'mean_pods': round(self.mean_pods, 3) if round_values else self.mean_pods,
            'median_pods': round(self.median_pods, 3) if round_values else self.median_pods,
            'coefficient_of_variation': round(self.coefficient_of_variation, 3) if round_values else self.coefficient_of_variation,
            'gini_coefficient': round(self.gini_coefficient, 3) if round_values else self.gini_coefficient,
            'jain_fairness_index': round(self.jain_fairness_index, 3) if round_values else self.jain_fairness_index,
        }

    def __str__(self) -> str:
        """String representation of DeploymentInfo."""
        return json.dumps(self._to_dict(round_values=True), separators=(',', ':'))

def gather_cluster_measurements(release_names: List[str]=[]) -> dict:
    node_info = get_node_info()
    measurements = {
        "nodes": node_info,
        "distributions": {release_name: gather_deployment_distribution_info(release_name, node_info.node_count) for release_name in release_names},
    }
    return measurements

def get_node_info() -> ClusterNodeInfo:
    """Get the number of nodes in the cluster"""
    try:
        config.load_kube_config()
        v1 = client.CoreV1Api()
        nodes = v1.list_node()
        # get information on the default nodepool
        # filter nodes by unreserved cpu and memory
        required_free_cpu = 256 # mCPU
        required_free_memory = 256 # MiB
        eligible_nodes = []
        for node in nodes.items:
            # need to do unit conversion
            #free_cpu = node.status.capacity['cpu'] - node.status.allocatable['cpu']
            #free_memory = node.status.capacity['memory'] - node.status.allocatable['memory']
            #if free_cpu >= required_free_cpu and free_memory >= required_free_memory:
                eligible_nodes.append(node)

        cluster_node_info = ClusterNodeInfo(
            node_count=len(nodes.items),
            eligible_node_count=len(eligible_nodes),
        )
        return cluster_node_info
    except client.exceptions.ApiException as e:
        handle_api_exception(e)

def handle_api_exception(e: client.exceptions.ApiException):
    if e.status == 401:
        logger.error("Not authorized. Check credentials.")
        raise Exception("kubernetes authentication error") from e
    else:
        logger.error(f"Error getting node count: {e}")
        raise Exception("kubernetes API error") from e

def gather_deployment_distribution_info(deployment_name: str, cluster_node_count: int):
    """
    Assumes deployment is in its own namespace.
    """
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(deployment_name)
    total_pods = len(pods.items)

    node_to_podcount = {}
    for pod in pods.items:
        node_to_podcount[pod.spec.node_name] = node_to_podcount.get(pod.spec.node_name, 0) + 1

    nodes_used = len(node_to_podcount)
    logger.info(f"[{deployment_name}] {total_pods} pods spread across {nodes_used} nodes")
    logger.debug(f"[{deployment_name}] Node names: {node_to_podcount.keys()}")

    unused_nodes = cluster_node_count - len(node_to_podcount.keys())
    # TODO only include unused nodes if they have room for a pod
    # Add one zero if there are unused nodes we could've used.
    # Too many zeroes makes the stats less useful.
    pod_counts = list(node_to_podcount.values()) + ([0] if unused_nodes and total_pods > cluster_node_count else [])

    distribution_info = DeploymentDistributionInfo(pod_counts)

    logger.debug(f"[{deployment_name}] Deployment distribution: {distribution_info}")
    return distribution_info

def print_measurements(measurements: dict):
    logger.info(f"Cluster info: {measurements['nodes']}")
    for deployment_name, distribution_info in measurements.get("distributions", {}).items():
        logger.info(f"[{deployment_name}] Deployment distribution: {distribution_info}")

        logger.info(f"[{deployment_name}] Pod distribution graph:")
        for node_index, pod_count in enumerate(sorted(distribution_info.pod_counts)):
            bar = "#" * pod_count
            logger.info(f"[{deployment_name}]\tNode {node_index:02d}: {bar} ({pod_count} pods)")

        # Alternate visualization
        # podcount_to_nodecount = {}
        # for pod_count in node_to_podcount.values():
        #     podcount_to_nodecount[pod_count] = podcount_to_nodecount.get(pod_count, 0) + 1

        # logger.info(f"[{namespace}] Node distribution:")
        # for pod_count in sorted(podcount_to_nodecount.keys()):
        #     bar = "#" * podcount_to_nodecount[pod_count]
        #     logger.info(f"[{namespace}]\t{pod_count:02d} pods: {bar} ({podcount_to_nodecount[pod_count]} nodes)")
