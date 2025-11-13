#!/usr/bin/env python3
import glob
import json
import logging
import os
from pathlib import Path
import statistics
from typing import Optional, Tuple

from measurements import Measurements

logger = logging.getLogger(__name__)


class PostprocessedData:

    def __init__(self, measurements_pre: Optional[Measurements], measurements_post: Measurements):

        if measurements_pre:
            # report if scaling occurred
            self.scale_direction = 'up' if measurements_post.cluster.node_count > measurements_pre.cluster.node_count else 'down' if measurements_post.cluster.node_count < measurements_pre.cluster.node_count else 'none'
            self.scale_amount = measurements_post.cluster.node_count - measurements_pre.cluster.node_count
            self.scale_percentage = abs(self.scale_amount) / measurements_pre.cluster.node_count * 100
        else:
            self.scale_direction = None
            self.scale_amount = None
            self.scale_percentage = None

        # calculate mean+median of jain fairness index, coefficient of variation, gini coefficient
        jfi_values = [deployment.jain_fairness_index for deployment in measurements_post.deployments.values()]
        self.jain_fairness_index_mean = statistics.mean(jfi_values)
        self.jain_fairness_index_median = statistics.median(jfi_values)

        cov_values = [deployment.coefficient_of_variation for deployment in measurements_post.deployments.values()]
        self.coefficient_of_variation_mean = statistics.mean(cov_values)
        self.coefficient_of_variation_median = statistics.median(cov_values)

        gci_values = [deployment.gini_coefficient for deployment in measurements_post.deployments.values()]
        self.gini_coefficient_mean = statistics.mean(gci_values)
        self.gini_coefficient_median = statistics.median(gci_values)

        # determine mean, median, and max skew of node_skew
        node_skew_values = [deployment.node_skew for deployment in measurements_post.deployments.values()]
        self.node_skew_mean = statistics.mean(node_skew_values)
        self.node_skew_median = statistics.median(node_skew_values)
        self.node_skew_max = max(node_skew_values)

        # more metrics on node usage
        nosed_used_values = [deployment.nodes_used for deployment in measurements_post.deployments.values()]
        self.nosed_used_avg = statistics.mean(nosed_used_values)
        self.nosed_used_median = statistics.median(nosed_used_values)
        self.nosed_used_max = max(nosed_used_values)
        self.nosed_used_min = min(nosed_used_values)

    def to_dict(self) -> dict:
        return {
            'scale_direction': self.scale_direction,
            'scale_amount': self.scale_amount,
            'scale_percentage': round(self.scale_percentage, 1) if self.scale_percentage else None,

            'jain_fairness_index_mean': round(self.jain_fairness_index_mean, 3),
            'jain_fairness_index_median': round(self.jain_fairness_index_median, 3),
            'coefficient_of_variation_mean': round(self.coefficient_of_variation_mean, 3),
            'coefficient_of_variation_median': round(self.coefficient_of_variation_median, 3),
            'gini_coefficient_mean': round(self.gini_coefficient_mean, 3),
            'gini_coefficient_median': round(self.gini_coefficient_median, 3),

            'node_skew_mean': round(self.node_skew_mean, 2),
            'node_skew_median': self.node_skew_median,
            'node_skew_max': self.node_skew_max,

            'nosed_used_avg': round(self.nosed_used_avg, 2),
            'nosed_used_median': round(self.nosed_used_median, 2),
            'nosed_used_max': self.nosed_used_max,
            'nosed_used_min': self.nosed_used_min,
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict())


def fetch_measurements(measurements_file: Path) -> Tuple[Measurements, Measurements]:
    """
    Postprocess the measurements file.
    """
    try:
        with open(measurements_file, 'r') as f:
            data = json.load(f)
            # parse pre and post measurements
            pre_measurements = Measurements.from_dict(data['measurements_pre'])
            post_measurements = Measurements.from_dict(data['measurements_post'])

            return pre_measurements, post_measurements
    except json.JSONDecodeError as e:
        raise Exception(f"Error parsing measurements file {measurements_file}") from e


if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO)

    MEASUREMENTS_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/output"
    measurements_pattern = f"{MEASUREMENTS_DIR}/**/*.json"
    measurements_files = glob.glob(measurements_pattern)

    for measurements_file in measurements_files:
        pre_measurements, post_measurements = fetch_measurements(Path(measurements_file))
        results = PostprocessedData(pre_measurements, post_measurements)
        logger.info(f"Results for {measurements_file}: {results}")

        try:
            with open(measurements_file, 'r') as f:
                original_data = json.load(f)
        except json.JSONDecodeError as e:
            raise Exception(f"Error parsing measurements file {measurements_file}") from e
        try:
            with open(measurements_file, 'r+') as f:
                data = {
                    # keep everything the same except for the postprocessed data
                    "args": original_data['args'],
                    "timestamp": original_data['timestamp'],
                    "install_time": original_data['install_time'],
                    "postprocessed": results.to_dict(),
                    "measurements_pre": original_data['measurements_pre'],
                    "measurements_post": original_data['measurements_post'],
                }
                json.dump(data, f, indent=4)
        except Exception as e:
            raise Exception(f"Error writing measurements file {measurements_file}") from e
    logger.info(f"Done. Processed {len(measurements_files)} measurements files")
