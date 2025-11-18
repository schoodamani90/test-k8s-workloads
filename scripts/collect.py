#!/usr/bin/env python3
"""
Collects deployment distribution data for a list of namespaces within a cluster.

This is best for analyzing "real" deployments, as opposed to the synthetic ones used for testing.
"""

import argparse
import logging

from datetime import datetime, timedelta

from deploy import verify_cluster
from measurements import gather_cluster_measurements
from postprocess import PostprocessedData
from utils import setup_logging, OUTPUT_DIR
from experiment import ExperimentResult
from scenarios import Scenario, Mechanism

PROD_LIVE_MAIN_CONTEXT_NAME = "arn:aws:eks:us-east-1:906324658258:cluster/prod-live-main"
TEST_NAMESPACES = [
    "monolith"
]
scenario = Scenario(
        name="DataCollection",
        description="Take measurements from existing deployments on a cluster",
        mechanism=Mechanism.NONE,
        workloads_per_nodepool=0,
        replicas=0,
    )

logger = logging.getLogger(__name__)


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
    parser.add_argument("--scenario", type=str, required=False, default=scenario.name, help=argparse.SUPPRESS)
    return parser.parse_args()


if __name__ == "__main__":
    main()
