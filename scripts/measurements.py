import logging
import statistics
import json
from typing import List
from kubernetes import client, config

logger = logging.getLogger(__name__)

# While maximal spread is the ideal, for many of these tests it's not possible to use all nodes.
# It's also diffcult to filter out nodes that are not eligible to run pods due to taints or being fully committed already.
# So we can include it when we want to see, but for the most part we'll just ignore them and focus on the distribution
# among the nodes that got at least one pod.
INCLUDE_UNUSED_NODES = False

class ClusterNodeData:
    """Class representing cluster information."""
    def __init__(self, node_count: int, eligible_node_count: int):
        self.node_count = node_count
        self.eligible_node_count = eligible_node_count

    def __str__(self) -> str:
        """String representation of ClusterNodeData."""
        return json.dumps(
            self,
            default=vars,
            sort_keys=False,
            indent=4)

class DeploymentDistributionData:
    """Class representing deployment information and statistics."""

    def __init__(self, pod_counts: List[int]):
        """Initialize DeploymentDistributionData with all statistics.

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
        """Convert DeploymentDistributionData to dictionary format.

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
        """String representation of DeploymentDistributionData."""
        return json.dumps(self._to_dict(round_values=True))

def gather_cluster_measurements(release_names: List[str]=[]) -> dict:
    node_info = get_node_info()
    measurements = {
        "nodes": node_info,
        "deployments": {release_name: gather_deployment_distribution_data(release_name, node_info.node_count) for release_name in release_names},
    }
    return measurements

def get_node_info() -> ClusterNodeData:
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
            # Getting the unallocated cpu + memory for a node is nontrivial. Kubectl does it client-side when running describe node.
            #if free_cpu >= required_free_cpu and free_memory >= required_free_memory:
                eligible_nodes.append(node)

        cluster_node_info = ClusterNodeData(
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

def gather_deployment_distribution_data(deployment_name: str, cluster_node_count: int):
    """
    Gather data about a deployment's distribution across nodes.
    """
    logger.info(f"[{deployment_name}] Gathering deployment data")
    config.load_kube_config()
    v1 = client.CoreV1Api()
    # Assumes deployment is in its own namespace.
    # FUTURE: Support getting a specific deployment within a namespace that has other pods running
    pods = v1.list_namespaced_pod(deployment_name)
    total_pods = len(pods.items)

    node_to_podcount = {}
    for pod in pods.items:
        node_to_podcount[pod.spec.node_name] = node_to_podcount.get(pod.spec.node_name, 0) + 1

    nodes_used = len(node_to_podcount)
    logger.debug(f"[{deployment_name}] {total_pods} pods spread across {nodes_used} nodes")
    logger.debug(f"[{deployment_name}] Node names: {node_to_podcount.keys()}")

    unused_nodes = cluster_node_count - len(node_to_podcount.keys())
    # TODO only include unused nodes if they have room for a pod
    pod_counts = list(node_to_podcount.values()) + ([0] * unused_nodes if (INCLUDE_UNUSED_NODES and unused_nodes and max(node_to_podcount.values()) > 1) else [])

    distribution_info = DeploymentDistributionData(pod_counts)

    logger.debug(f"[{deployment_name}] Deployment distribution: {distribution_info}")
    return distribution_info

def print_measurements(measurements: dict):
    logger.info(f"Cluster info: {measurements['nodes']}")
    for deployment_name, distribution_info in measurements.get("deployments", {}).items():
        logger.info(f"[{deployment_name}] {distribution_info.total_pods} pods spread across {distribution_info.nodes_used} nodes")

        # Visualization of the deployment's distribution across nodes.
        # Each node is represented by a bar of the number of pods on the node.
        # We want to see even bars
        distribution_graph = []
        for node_index, pod_count in enumerate(sorted(distribution_info.pod_counts)):
            bar = "#" * pod_count
            distribution_graph.append(f"\tNode {node_index:02d}: {bar} ({pod_count} pods)")
        logger.info(f"[{deployment_name}] Pod distribution graph:\n" + "\n".join(distribution_graph))

        # Alternate visualization. Groups nodes by pod count to show how many nodes have that many pods.
        # The fewer the bars, and the more grouped together, the better. As that indicates a more even distribution.
        podcount_to_nodecount = {}
        for pod_count in distribution_info.pod_counts:
            podcount_to_nodecount[pod_count] = podcount_to_nodecount.get(pod_count, 0) + 1

        distribution_graph = []
        logger.info(f"[{deployment_name}] Node distribution:")
        for pod_count in sorted(podcount_to_nodecount.keys()):
            bar = "#" * podcount_to_nodecount[pod_count]
            distribution_graph.append(f"\t{pod_count:02d} pods: {bar} ({podcount_to_nodecount[pod_count]} nodes)")
        logger.info(f"[{deployment_name}] Nodes grouped by pod count:\n" + "\n".join(distribution_graph))
        logger.info(f"[{deployment_name}] Deployment data: {distribution_info}")
