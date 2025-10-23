import logging
import math
import statistics
import json
from typing import List
from kubernetes import client, config

logger = logging.getLogger(__name__)

def gather_cluster_measurements(release_names: List[str]=[]) -> dict:
    measurements = {}
    measurements["nodes"] = get_node_info()
    # TODO more node info
    measurements["distributions"] = {}
    for release_name in release_names:
        measurements["distributions"][release_name] = gather_pod_distribution_info(release_name, measurements["nodes"]["count"])
    return measurements

def get_node_info():
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

        return {
            "count": len(nodes.items),
            "eligible_count": len(eligible_nodes),
        }
    except client.exceptions.ApiException as e:
        handle_api_exception(e)

def handle_api_exception(e: client.exceptions.ApiException):
    if e.status == 401:
        logger.error("Not authorized. Check credentials.")
        raise Exception("kubernetes authentication error") from e
    else:
        logger.error(f"Error getting node count: {e}")
        raise Exception("kubernetes API error") from e

def gather_pod_distribution_info(namespace: str, cluster_node_count):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace)
    total_pod_count = len(pods.items)
    node_names = [pod.spec.node_name for pod in pods.items]

    node_names_set = set(node_names)
    node_count = len(node_names_set)
    logger.info(f"[{namespace}] {total_pod_count} pods spread across {node_count} nodes (out of {cluster_node_count})")
    logger.debug(f"[{namespace}] Node names: {node_names_set}")

    node_to_podcount = {}
    for node_name in node_names_set:
        node_to_podcount[node_name] = node_to_podcount.get(node_name, 0) + 1
    max_pods = max(node_to_podcount.values())
    min_pods = min(node_to_podcount.values())
    skew = max_pods - min_pods

    podcount_to_nodecount = {}
    for pod_count in node_to_podcount.values():
        podcount_to_nodecount[pod_count] = podcount_to_nodecount.get(pod_count, 0) + 1

    logger.info(f"[{namespace}] Node distribution:")
    for pod_count in sorted(podcount_to_nodecount.keys()):
        node_count = podcount_to_nodecount[pod_count]
        bar = "#" * node_count
        logger.info(f"[{namespace}]     {pod_count} pods: {bar} ({node_count} nodes)")

    logger.debug(f"[{namespace}] Max skew in pod distribution: {skew} (max: {max_pods}, min: {min_pods})")

    unused_nodes = cluster_node_count - len(node_to_podcount.keys())
    # TODO only include unused nodes if they have room for a pod
    # Add one zero if there are unused nodes we could've used.
    # Too many zeroes makes the stats less useful.
    pod_counts = list(node_to_podcount.values()) + ([0] if unused_nodes and pod_count > cluster_node_count else [])

    # Basic statistics
    mean_pods = statistics.mean(pod_counts)
    variance = statistics.variance(pod_counts)
    std_dev = statistics.stdev(pod_counts)
    cv = std_dev / mean_pods if mean_pods > 0 else 0

    # Gini coefficient
    gini = calculate_gini_coefficient(pod_counts)

    # Jain's fairness index
    jain_fairness = calculate_jain_fairness_index(pod_counts)

    # Entropy
    entropy = calculate_entropy(pod_counts)

    deployment_info = {
        'pod_count': total_pod_count,
        'nodes_used': node_count,
        'max_pods_percentage': round((max(pod_counts) / total_pod_count) * 100, 2),
        'max_pods': max(pod_counts),
        'min_pods': min(pod_counts),
        'skew': max(pod_counts) - min(pod_counts),
        #'mean_pods_per_node': round(mean_pods, 3),
        'coefficient_of_variation': round(cv, 3),
        'gini_coefficient': round(gini, 3),
        'jain_fairness_index': round(jain_fairness, 3),
        #'entropy': round(entropy, 3),
    }

    logger.debug(f"[{namespace}] Deployment info: {json.dumps(deployment_info, indent=4)}")
    return deployment_info

def calculate_gini_coefficient(values):
    """Calculate Gini coefficient for inequality measurement"""
    if not values:
        return 0
    sorted_values = sorted(values)
    n = len(sorted_values)

    cumsum = 0
    for i, value in enumerate(sorted_values):
        cumsum += (i + 1) * value

    return (2 * cumsum) / (n * sum(sorted_values)) - (n + 1) / n

def calculate_jain_fairness_index(values):
    """Calculate Jain's fairness index"""
    if not values or sum(values) == 0:
        return 0

    n = len(values)
    sum_squared = sum(x**2 for x in values)
    sum_values = sum(values)

    return (sum_values**2) / (n * sum_squared)

def calculate_entropy(values):
    """Calculate entropy of distribution"""
    total = sum(values)
    if total == 0:
        return 0

    entropy = 0
    for value in values:
        if value > 0:
            p = value / total
            entropy -= p * math.log2(p)
    return entropy
