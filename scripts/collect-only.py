#!/usr/bin/env python3
"""
Collects deployment distribution data for a list of namespaces within a cluster.

This is best for analyzing "real" deployments, as opposed to the synthetic ones used for testing.
"""

import argparse
import logging

from datetime import datetime

from deploy import verify_cluster
from measurements import gather_cluster_measurements
from postprocess import PostprocessedData
from utils import setup_logging, write_measurements


PROD_LIVE_MAIN_CONTEXT_NAME = "arn:aws:eks:us-east-1:906324658258:cluster/prod-live-main"
TEST_NAMESPACES = [
    "monolith"
]


logger = logging.getLogger(__name__)


def main():
    setup_logging()
    args = parse_args()
    cluster_name = args.cluster_context.split("/")[-1]

    verify_cluster(args.cluster_context)

    measurements = gather_cluster_measurements(args.namespaces)
    logger.debug(f"Measurements: {measurements}")

    postprocessed_data = PostprocessedData(None, measurements)

    write_measurements(cluster_name, args, None, postprocessed_data, [measurements])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect cluster measurements")

    parser.add_argument("--cluster-context", type=str, required=False, default=PROD_LIVE_MAIN_CONTEXT_NAME)
    parser.add_argument("--namespaces", type=str, nargs="+", required=False, default=TEST_NAMESPACES)
    return parser.parse_args()


if __name__ == "__main__":
    main()
