#! /usr/bin/env python3

from enum import Enum
import logging
import os
from typing import List
import yaml

logger = logging.getLogger(__name__)

NODEPOOL_LABEL = "workload-isolation-test-nodepool"
NODEPOOL_VALUE_PREFIX = "workload-isolation-test-nodepool-"

VALUES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/values"
if not os.path.exists(VALUES_DIR):
    os.makedirs(VALUES_DIR)

class Mechanism(Enum):
    NONE = "none"
    NODE_SELECTOR = "nodeSelector"
    NODE_AFFINITY = "nodeAffinity"
    NODE_ANTI_AFFINITY = "nodeAntiAffinity"
    POD_ANTI_AFFINITY = "podAntiAffinity"

class Scenario:
    """
    Holds the parameters for our test scenarios as called out in
    https://docs.google.com/document/d/1ABx52N-S7Oji2xwaI5I7l_CRB3oMLvMnrEbjSUqlExY/edit?tab=t.0#heading=h.5kjqx4qz5vzr
    """
    def __init__(self, name: str, mechanism: Mechanism,
                 nodepool_count: int,
                 workloads_per_nodepool: List[int],
                 replicas_min: int, replicas_max: int):
        self.name = name
        self.mechanism = mechanism
        self.nodepool_count = nodepool_count
        self.workloads_per_nodepool = workloads_per_nodepool
        self.replicas_min = replicas_min
        self.replicas_max = replicas_max


SCENARIOS = [
    Scenario(
        name="C1",
        mechanism=Mechanism.NONE,
        nodepool_count=1,
        workloads_per_nodepool=[10],
        replicas_min=2,
        replicas_max=50,
    ),
    Scenario(
        name="NS1",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count=2,
        workloads_per_nodepool=[1],
        replicas_min=2,
        replicas_max=20,
    ),
    Scenario(
        name="NS2.i",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count=2,
        workloads_per_nodepool=[2, 10],
        replicas_min=2,
        replicas_max=50,
    ),
    Scenario(
        name="NS2.ii",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count=2,
        workloads_per_nodepool=[5, 10],
        replicas_min=2,
        replicas_max=50,
    ),
    Scenario(
        name="NS3.i",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count=2,
        workloads_per_nodepool=[2, 5, 10],
        replicas_min=2,
        replicas_max=50,
    ),
    Scenario(
        name="NS3.ii",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count=5,
        workloads_per_nodepool=[2, 5, 10],
        replicas_min=2,
        replicas_max=50,
    ),
    Scenario(
        name="NS3.iii",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepool_count=10,
        workloads_per_nodepool=[2, 5, 10],
        replicas_min=2,
        replicas_max=50,
    ),
    Scenario(
        name="P1.i",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        nodepool_count=1,
        workloads_per_nodepool=[1],
        replicas_min=2,
        replicas_max=2,
    ),
    Scenario(
        name="P1.ii",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        nodepool_count=1,
        workloads_per_nodepool=[10],
        replicas_min=2,
        replicas_max=2,
    ),
    Scenario(
        name="P1.iii",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        nodepool_count=1,
        workloads_per_nodepool=[10],
        replicas_min=2,
        replicas_max=10,
    ),
    Scenario(
        name="P1.iv",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        nodepool_count=1,
        workloads_per_nodepool=[10],
        replicas_min=2,
        replicas_max=50,
    ),
]

def main():
    for scenario in SCENARIOS:
        generate_values(scenario)

def generate_values(scenario):

    default_values = yaml.safe_load(open("busybox-chart/values.yaml"))

    for nodepool_index in range(scenario.nodepool_count):
        replica_counts = determine_replica_counts_for_nodepool(scenario, nodepool_index)
        for workload_id in range(scenario.workloads_per_nodepool[nodepool_index % len(scenario.workloads_per_nodepool)]):
            replica_count = replica_counts[workload_id % len(replica_counts)]

            values = default_values.copy()

            nodepool_name = f"{NODEPOOL_VALUE_PREFIX}{nodepool_index}"
            values['replicaCount'] = replica_count

            if scenario.mechanism == Mechanism.NONE:
                pass
            elif scenario.mechanism == Mechanism.NODE_SELECTOR:
                values['nodeSelector'] = {
                    NODEPOOL_LABEL: nodepool_name
                }
                values['tolerations'] = [
                    {
                        'key': 'system-tests/dedicated',
                        'operator': 'Equal',
                        'value': 'workload-isolation',
                        'effect': 'NoExecute'
                    }
                ]
            elif scenario.mechanism == Mechanism.NODE_AFFINITY:
                pass
            elif scenario.mechanism == Mechanism.NODE_ANTI_AFFINITY:
                pass
            elif scenario.mechanism == Mechanism.POD_ANTI_AFFINITY:
                values['affinity'] = {
                    'podAntiAffinity': {
                        'preferredDuringSchedulingIgnoredDuringExecution': [
                            {
                                'podAffinityTerm': {
                                    'topologyKey': 'kubernetes.io/hostname',
                                    'labelSelector': {
                                    'matchExpressions': [
                                        {
                                            'key': 'app.kubernetes.io/name',
                                            'operator': 'In',
                                            'values': ['busybox']
                                        }
                                    ]
                                    # Can use by default in 1.33 and later
                                    #'matchLabelKeys': ['pod-template-hash']
                                },
                                },
                                'weight': 1
                            }
                        ]}}

            else:
                raise ValueError(f"Invalid mechanism: {scenario.mechanism.value}")

            os.makedirs(f"{VALUES_DIR}/{scenario.name}", exist_ok=True)
            yaml.dump(values, open(f"{VALUES_DIR}/{scenario.name}/values-np{nodepool_index}-w{workload_id}-r{replica_count}.yaml", "w"))


def determine_replica_counts_for_nodepool(scenario, nodepool_index):
    """
    @returns a list of replica counts spanning from scenario.replicas_min to scenario.replicas_max, approximately evenly spread. The length of the list is the number of workloads for the nodepool, based on the scenario configuration.
    """
    workload_count = scenario.workloads_per_nodepool[nodepool_index % len(scenario.workloads_per_nodepool)]

    if workload_count == 1:
        replica_counts = [scenario.replicas_min]
    else:
        # Create evenly distributed replica counts from min to max
        step = (scenario.replicas_max - scenario.replicas_min) / (workload_count - 1)
        replica_counts = [int(scenario.replicas_min + i * step) for i in range(workload_count)]
    return replica_counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
