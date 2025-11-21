#!/usr/bin/env python3

import argparse
import logging
import yaml

from enum import Enum
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

NODEPOOL_LABEL = "workload-isolation-test-nodepool"
NODEPOOL_VALUE_PREFIX = "workload-isolation-test-nodepool-"

VALUES_DIR = Path(__file__).parent.parent / "build" / "values"
VALUES_DIR.mkdir(parents=True, exist_ok=True)


class Mechanism(Enum):
    NONE = "none"
    NODE_SELECTOR = "nodeSelector"
    NODE_AFFINITY = "nodeAffinity"
    NODE_ANTI_AFFINITY = "nodeAntiAffinity"
    POD_ANTI_AFFINITY = "podAntiAffinity"
    TOPOLOGY_SPREAD = "topologySpreadConstraint"

class Preference(Enum):
    SOFT = "soft"
    HARD = "hard"

class Scenario:
    """
    Holds the parameters for our test scenarios as called out in
    https://docs.google.com/document/d/1ABx52N-S7Oji2xwaI5I7l_CRB3oMLvMnrEbjSUqlExY/edit?tab=t.0#heading=h.5kjqx4qz5vzr

    Args:
        name: The name of the scenario.
        description: A free-form description of the scenario.
        mechanism: The mechanism to use for the scenario.
        workloads_per_nodepool: A list of the number of workloads per nodepool.
                                Or a single integer if the scenario has a fixed number of workloads per nodepool.
        replicas: A tuple indicating the range of replicas for the scenario.
                  Or a single integer if the scenario has a fixed number of replicas.
        nodepools: The number of nodepools to use for the scenario.
        control_pods: The number of control group pods to use for the scenario.
                      The purpose is primarily to make it so that the experimental deploy does not represent an
                      unrealistic percentage of the total cluster resources.

    """
    def __init__(self, name: str, description: str, mechanism: Mechanism,
                 workloads_per_nodepool: List[int] | int = 1,
                 replicas: Tuple[int, int] | int = 2,
                 nodepools: int = 1,
                 control_pods: int = 0,
                 preference: Preference = Preference.SOFT):
        self.name: str = name
        self.description: str = description
        self.mechanism: Mechanism = mechanism
        self.nodepools: int = nodepools
        self.workloads_per_nodepool: List[int] = workloads_per_nodepool if isinstance(workloads_per_nodepool, list) else [workloads_per_nodepool]
        self.replicas: Tuple[int, int] = replicas if isinstance(replicas, tuple) else (replicas, replicas)
        self.control_pods: int = control_pods
        self.preference: Preference = preference

    def __str__(self):
        return self.name


SCENARIOS = [
    Scenario(
        name="C1",
        description="Default behavior test with a variety of replica counts",
        mechanism=Mechanism.NONE,
        workloads_per_nodepool=10,
        replicas=(2, 50),
    ),
    Scenario(
        name="C2",
        description="Default beahvior test with a fixed large number of replicas",
        mechanism=Mechanism.NONE,
        workloads_per_nodepool=10,
        replicas=50
    ),
    Scenario(
        name="NS1",
        description="Node selector with a single workload per nodepool",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=1,
        replicas=(2, 20),
    ),
    Scenario(
        name="NS2.i",
        description="Node selector with multiple workloads per nodepool",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=[2, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="NS2.ii",
        description="Even more workloads per nodepool",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=2,
        workloads_per_nodepool=10,
        replicas=(2, 50),
    ),
    Scenario(
        name="NS3.ii",
        description="More nodepools",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=5,
        workloads_per_nodepool=[2, 5, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="NS3.iii",
        description="Even more nodepools",
        mechanism=Mechanism.NODE_SELECTOR,
        nodepools=10,
        workloads_per_nodepool=[2, 5, 10],
        replicas=(2, 50),
    ),
    Scenario(
        name="P1.i",
        description="Basic pod anti-affinity",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        replicas=2,
    ),
    Scenario(
        name="P1.ii",
        description="Pod anti-affinity with multiple test workloads",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=2,
    ),
    Scenario(
        name="P1.iii",
        description="Pod anti-affinity with a range of replica counts",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=(2, 10),
    ),
    Scenario(
        name="P1.iv",
        description="Pod anti-affinity with a larger range of replicas",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=(2, 50),
    ),
    Scenario(
        name="P3",
        description="Pod anti-affinity with a large number of replicas",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        workloads_per_nodepool=10,
        replicas=50,
    ),
    Scenario(
        name="P4.i",
        description="Pod anti-affinity with a large number of replicas and a control group",
        mechanism=Mechanism.POD_ANTI_AFFINITY,
        replicas=10,
        control_pods=100,
    ),
    Scenario(
        name="TSC1",
        description="TSC soft preference over a range of replicas",
        mechanism=Mechanism.TOPOLOGY_SPREAD,
        workloads_per_nodepool=10,
        replicas=(2, 50),
        preference=Preference.SOFT
    ),
    Scenario(
        name="TSC2",
        description="TSC hard preference over a range of replicas",
        mechanism=Mechanism.TOPOLOGY_SPREAD,
        workloads_per_nodepool=10,
        replicas=(2, 50),
        preference=Preference.HARD
    )
]


def main():
    logger.info("Generating values files for all scenarios")
    generate_all_values()
    logger.info("Done")


def get_scenario(name: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.name == name:
            return scenario
    raise ValueError(f"Scenario {name} not found")


def parse_scenario(scenario_name: str) -> Scenario:
    """Convert a scenario name string to a Scenario instance for use with argparse."""
    try:
        return get_scenario(scenario_name)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Scenario '{scenario_name}' not found")


def generate_all_values() -> None:
    for scenario in SCENARIOS:
        generate_values(scenario)


def generate_values(scenario: Scenario | str) -> None:

    if isinstance(scenario, str):
        scenario = get_scenario(scenario)

    # Mkae the scenario name valid as a release name
    scenario_name = scenario.name.replace('.', '-').lower()

    (VALUES_DIR / scenario.name).mkdir(parents=True, exist_ok=True)
    default_values = yaml.safe_load(open("busybox-chart/values.yaml"))

    for nodepool_index in range(scenario.nodepools):
        replica_counts = determine_replica_counts_for_nodepool(scenario, nodepool_index)
        for workload_id in range(scenario.workloads_per_nodepool[nodepool_index % len(scenario.workloads_per_nodepool)]):
            replica_count = replica_counts[workload_id % len(replica_counts)]
            release_name = f"{scenario_name}-test-{workload_id}"

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
                values['topologySpreadConstraints'] = [
                    {
                        'labelSelector': {
                            'matchLabels': {
                                'app.kubernetes.io/name': 'busybox-chart',
                                'app.kubernetes.io/instance': release_name
                            }
                        },
                        'maxSkew': 1,
                        'topologyKey': 'kubernetes.io/hostname',
                        'whenUnsatisfiable': 'ScheduleAnyway' if scenario.preference == Preference.SOFT else 'DoNotSchedule'
                    }
                ]
            else:
                raise ValueError(f"Invalid mechanism: {scenario.mechanism.value}")

            yaml.dump(values, open(f"{VALUES_DIR}/{scenario.name}/values-{release_name}.yaml", "w"))

    if scenario.control_pods > 0:
        # Generate the ballast values file
        ballast_values = default_values.copy()
        ballast_values['replicaCount'] = scenario.control_pods
        release_name = f"{scenario_name}-control-0"
        yaml.dump(ballast_values, open(f"{VALUES_DIR}/{scenario.name}/values-{release_name}.yaml", "w"))


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
