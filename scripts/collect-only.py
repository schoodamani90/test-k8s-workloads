"""
Collects deployment distribution data for a list of namespaces within a cluster.

This is best for analyzing "real" deployments, as opposed to the synthetic ones used for testing.
"""
import logging
from measurements import gather_cluster_measurements
from scripts.deploy import verify_cluster


def setup_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logger = logging.getLogger(__name__)
    return logger


logger = setup_logging()


def main():
    namespaces = [
        "monolith",
    ]

    verify_cluster("arn:aws:eks:us-east-1:906324658258:cluster/prod-live-main")

    measurements = gather_cluster_measurements(namespaces)
    logger.info(f"Measurements: {measurements}")


if __name__ == "__main__":
    main()
