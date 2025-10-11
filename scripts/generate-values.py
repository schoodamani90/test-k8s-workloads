#! /usr/bin/env python3

from enum import Enum
import logging
import os
import yaml

logger = logging.getLogger(__name__)

NODEPOOL_LABEL = "workload-isolation-test-nodepool"
NODEPOOL_VALUE_PREFIX = "workload-isolation-test-nodepool-"

VALUES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/values"
if not os.path.exists(VALUES_DIR):
    os.makedirs(VALUES_DIR)

class Mechanism(Enum):
    NODE_SELECTOR = "nodeSelector"
    AFFINITY = "affinity"
    ANTI_AFFINITY = "antiAffinity"

class Scenario:
    """
    Holds the parameters for our test scenarios as called out in https://docs.google.com/document/d/1ABx52N-S7Oji2xwaI5I7l_CRB3oMLvMnrEbjSUqlExY/edit?tab=t.0#heading=h.5kjqx4qz5vzr
    """
    def __init__(self, name, mechanism,nodepool_count_min, nodepool_count_max, workloads_per_nodepool_min, workloads_per_nodepool_max, pods_per_workload_min, pods_per_workload_max):
        self.name = name
        self.mechanism = mechanism
        self.nodepool_count_min = nodepool_count_min
        self.nodepool_count_max = nodepool_count_max
        self.workloads_per_nodepool_min = workloads_per_nodepool_min
        self.workloads_per_nodepool_max = workloads_per_nodepool_max
        self.pods_per_workload_min = pods_per_workload_min
        self.pods_per_workload_max = pods_per_workload_max


scenarios = [
    Scenario(
        name="A1",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count_min=2,
        nodepool_count_max=2,
        workloads_per_nodepool_min=1,
        workloads_per_nodepool_max=1,
        pods_per_workload_min=2,
        pods_per_workload_max=20,
    ),
    Scenario(
        name="A2",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count_min=2,
        nodepool_count_max=2,
        workloads_per_nodepool_min=2,
        workloads_per_nodepool_max=10,
        pods_per_workload_min=2,
        pods_per_workload_max=50,
    ),
    Scenario(
        name="A3",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count_min=2,
        nodepool_count_max=15,
        workloads_per_nodepool_min=2,
        workloads_per_nodepool_max=10,
        pods_per_workload_min=2,
        pods_per_workload_max=50,
    ),
]

def main():
    default_values = yaml.safe_load(open("busybox-chart/values.yaml"))

    for scenario in scenarios:
        nodepools = [x for x in range(scenario.nodepool_count_max)]

        # Generate pod_counts evenly distributed from min to max
        # Each pod_count represents a different workload
        num_workloads = scenario.workloads_per_nodepool_max
        if scenario.pods_per_workload_max == scenario.pods_per_workload_min:
            pod_counts = [scenario.pods_per_workload_min]
        else:
            if num_workloads == 1:
                pod_counts = [scenario.pods_per_workload_min, scenario.pods_per_workload_max]
            else:
                step = (scenario.pods_per_workload_max - scenario.pods_per_workload_min) / (num_workloads - 1)
                pod_counts = []
                for i in range(num_workloads):
                    pod_counts.append(int(scenario.pods_per_workload_min + i * step))

        logger.info(f"Scenario: {scenario.name}, Workloads per nodepool: {num_workloads}")
        logger.info(f"Scenario: {scenario.name}, Pod counts: {pod_counts}")
        logger.info(f"Scenario: {scenario.name}, Nodepools: {len(nodepools)}")

        for nodepool_index in nodepools:
                for pod_count_index, pod_count in enumerate(pod_counts):
                    values = default_values.copy()
                    nodepool_name = f"{NODEPOOL_VALUE_PREFIX}{nodepool_index}"
                    values['replicaCount'] = int(pod_count)

                    if scenario.mechanism == Mechanism.NODE_SELECTOR:
                        values['nodeSelector'] = {
                            NODEPOOL_LABEL: nodepool_name
                        }
                    elif scenario.mechanism == Mechanism.AFFINITY:
                        raise NotImplementedError("Affinity is not implemented yet")
                    elif scenario.mechanism == Mechanism.ANTI_AFFINITY:
                        raise NotImplementedError("Anti-affinity is not implemented yet")
                    else:
                        raise ValueError(f"Invalid mechanism: {scenario.mechanism.value}")

                    os.makedirs(f"{VALUES_DIR}/{scenario.name}/{scenario.mechanism.value}", exist_ok=True)
                    yaml.dump(values, open(f"{VALUES_DIR}/{scenario.name}/{scenario.mechanism.value}/values-{nodepool_index}-{pod_count_index}.yaml", "w"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
