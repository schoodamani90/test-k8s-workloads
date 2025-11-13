#! /usr/bin/env python3

from enum import Enum
import logging
import os
from typing import List, Tuple
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
    TOPOLOGY_SPREAD = "topologySpreadConstraint"


class Scenario:
    """
    Holds the parameters for our test scenarios as called out in
    https://docs.google.com/document/d/1ABx52N-S7Oji2xwaI5I7l_CRB3oMLvMnrEbjSUqlExY/edit?tab=t.0#heading=h.5kjqx4qz5vzr

    Args:
        name: The name of the scenario.
        mechanism: The mechanism to use for the scenario.
        workloads_per_nodepool: A list of the number of workloads per nodepool.
                                Or a single integer if the scenario has a fixed number of workloads per nodepool.
        replicas: A tuple indicating the range of replicas for the scenario.
                  Or a single integer if the scenario has a fixed number of replicas.
        nodepools: The number of nodepools to use for the scenario.
        ballast_pods: The number of ballast pods to use for the scenario. This could also be seen as a control group.
                      The purpose is primarily to make it so that the experimental deploy does not represent an
                      unrealistic percentage of the total cluster resources.

    """
    def __init__(self, name: str, mechanism: Mechanism,
                 workloads_per_nodepool: List[int] | int = 1,
                 replicas: Tuple[int, int] | int = 2,
                 nodepools: int = 1,
                 ballast_pods: int = 0):
        self.name = name
        self.mechanism = mechanism
        self.nodepools = nodepools
        self.workloads_per_nodepool = workloads_per_nodepool if isinstance(workloads_per_nodepool, list) else [workloads_per_nodepool]
        self.replicas = replicas if isinstance(replicas, tuple) else (replicas, replicas)
        self.ballast_pods = ballast_pods

    def __str__(self):
        return self.name


class LongRunningScenario(Scenario):
    """
    A scenario that is long running, for instance can be restarted, redeployed, or otherwise modified.
    """
    def __init__(self, name: str, mechanism: Mechanism,
                 workloads_per_nodepool: List[int] | int = 1,
                 replicas: Tuple[int, int] | int = 2,
                 nodepools: int = 1,
                 ballast_pods: int = 0,
                 restart_count: int = 0,):
        super().__init__(name, mechanism, workloads_per_nodepool, replicas, nodepools, ballast_pods)
        self.restart_count = restart_count


SCENARIOS = [
    Scenario(
        name="C1",
        mechanism=Mechanism.NONE,
        workloads_per_nodepool=10,
        replicas=(2, 50),
    ),
    Scenario(
        name="C2",
        mechanism=Mechanism.NONE,
        workloads_per_nodepool=10,
        replicas=50
    ),
    Scenario(
        name="NS1",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=1,
        replicas=(2, 20),
    ),
    Scenario(
        name="NS2.i",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=[2, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="NS2.ii",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=[5, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="NS3.i",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=[2, 5, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="NS3.ii",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=5,
        workloads_per_nodepool=[2, 5, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="NS3.iii",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=10,
        workloads_per_nodepool=[2, 5, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="P1.i",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=1,
        replicas=2,
    ),
    Scenario(
        name="P1.ii",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=2,
    ),
    Scenario(
        name="P1.iii",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=(2, 10),
    ),
    Scenario(
        name="P1.iv",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        nodepools=1,
        workloads_per_nodepool=10,
        replicas=(2, 50),
    ),
    Scenario(
        name="P2",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        nodepools=1,
        workloads_per_nodepool=10,
        replicas=50,
    ),
    LongRunningScenario(
        name="P3.i",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=50,
        restart_count=1,
    ),
    LongRunningScenario(
        name="P3.ii",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=50,
        restart_count=10,
    ),
    LongRunningScenario(
        name="P4.i",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=1,
        replicas=10,
        restart_count=10,
        ballast_pods=100,
    ),
]


def main():
    generate_all_values()


def get_scenario(name: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    raise ValueError(f"Scenario {name} not found")


def generate_all_values() -> None:
    for scenario in SCENARIOS:
        generate_values(scenario)


def generate_values(scenario: Scenario | str) -> None:

    if isinstance(scenario, str):
        scenario = get_scenario(scenario)

    os.makedirs(f"{VALUES_DIR}/{scenario.name}", exist_ok=True)
    default_values = yaml.safe_load(open("busybox-chart/values.yaml"))

    for nodepool_index in range(scenario.nodepools):
        replica_counts = determine_replica_counts_for_nodepool(scenario, nodepool_index)
        for workload_id in range(scenario.workloads_per_nodepool[nodepool_index % len(scenario.workloads_per_nodepool)]):
            replica_count = replica_counts[workload_id % len(replica_counts)]
            release_name = f"np{nodepool_index}-w{workload_id}"

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
                                                'values': ['busybox-chart']
                                            },
                                            {
                                                'key': 'app.kubernetes.io/instance',
                                                'operator': 'In',
                                                'values': [release_name]
                                            }
                                        ]
                                        # Can use by default in 1.33 and later.
                                        # On 1.29 this would need to be enabled at the cluster level.
                                        # 'matchLabelKeys': ['pod-template-hash']
                                    },
                                },
                                'weight': 1
                            }
                        ]}}

            elif scenario.mechanism == Mechanism.TOPOLOGY_SPREAD:
                pass
            else:
                raise ValueError(f"Invalid mechanism: {scenario.mechanism.value}")

            yaml.dump(values, open(f"{VALUES_DIR}/{scenario.name}/values-{release_name}.yaml", "w"))

    if scenario.ballast_pods > 0:
        # Generate the ballast values file
        ballast_values = default_values.copy()
        ballast_values['replicaCount'] = scenario.ballast_pods
        yaml.dump(ballast_values, open(f"{VALUES_DIR}/{scenario.name}/values-ballast.yaml", "w"))


def determine_replica_counts_for_nodepool(scenario: Scenario, nodepool_index: int) -> List[int]:
    """
    @returns a list of replica counts spanning from scenario.replicas_min to scenario.replicas_max,
             approximately evenly spread. The length of the list is the number of workloads for the nodepool,
             based on the scenario configuration.
    """
    workload_count = scenario.workloads_per_nodepool[nodepool_index % len(scenario.workloads_per_nodepool)]

    if workload_count == 1:
        replica_counts = [scenario.replicas[0]]
    else:
        # Create evenly distributed replica counts from min to max
        step = (scenario.replicas[1] - scenario.replicas[0]) / (workload_count - 1)
        replica_counts = [int(scenario.replicas[0] + i * step) for i in range(workload_count)]
    return replica_counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
