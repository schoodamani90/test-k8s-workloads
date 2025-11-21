#!/usr/bin/env python3
import argparse
import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from measurements import Measurements

logger = logging.getLogger(__name__)


class PostprocessedData:

    def __init__(self, before: Optional[Measurements], after: Measurements):

        if before:
            scale_up = after.cluster.node_count > before.cluster.node_count
            scale_down = after.cluster.node_count < before.cluster.node_count
            self.scale_direction = 'up' if scale_up else 'down' if scale_down else 'none'
            self.scale_amount = after.cluster.eligible_node_count - before.cluster.eligible_node_count
            self.scale_percentage = abs(self.scale_amount) / before.cluster.node_count * 100
        else:
            self.scale_direction = None
            self.scale_amount = None
            self.scale_percentage = None

        # exclude the control group from the metrics
        test_deployments = [d for d in after.deployments.values() if 'test-' in d.name]
        if not test_deployments:
            logger.warning("No test deployments found in post-action measurements")
            self.jain_fairness_index_mean = 0
            self.jain_fairness_index_median = 0
            self.coefficient_of_variation_mean = 0
            self.coefficient_of_variation_median = 0
            self.gini_coefficient_mean = 0
            self.gini_coefficient_median = 0
            self.node_skew_mean = 0
            self.node_skew_median = 0
            self.node_skew_max = 0
            self.node_skew_percentage_mean = 0
            self.node_skew_percentage_median = 0
            self.node_skew_percentage_max = 0
            self.nosed_used_avg = 0
            self.nosed_used_median = 0
            self.nosed_used_max = 0
            self.nosed_used_min = 0
            return

        # calculate mean+median of jain fairness index, coefficient of variation, gini coefficient
        jfi_values = [d.jain_fairness_index for d in after.deployments.values()]
        self.jain_fairness_index_mean = statistics.mean(jfi_values)
        self.jain_fairness_index_median = statistics.median(jfi_values)

        cov_values = [d.coefficient_of_variation for d in after.deployments.values()]
        self.coefficient_of_variation_mean = statistics.mean(cov_values)
        self.coefficient_of_variation_median = statistics.median(cov_values)

        gci_values = [d.gini_coefficient for d in after.deployments.values()]
        self.gini_coefficient_mean = statistics.mean(gci_values)
        self.gini_coefficient_median = statistics.median(gci_values)

        # determine mean, median, and max skew of node_skew (raw and percentage)
        node_skew_values = [d.node_skew for d in after.deployments.values()]
        self.node_skew_mean = statistics.mean(node_skew_values)
        self.node_skew_median = statistics.median(node_skew_values)
        self.node_skew_max = max(node_skew_values)

        node_skew_percentage_values = [d.node_skew_percentage for d in after.deployments.values()]
        self.node_skew_percentage_mean = statistics.mean(node_skew_percentage_values)
        self.node_skew_percentage_median = statistics.median(node_skew_percentage_values)
        self.node_skew_percentage_max = max(node_skew_percentage_values)

        # more metrics on node usage
        nosed_used_values = [d.nodes_used for d in after.deployments.values()]
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

            'node_skew_percentage_mean': round(self.node_skew_percentage_mean, 2),
            'node_skew_percentage_median': round(self.node_skew_percentage_median, 2),
            'node_skew_percentage_max': round(self.node_skew_percentage_max, 2),

            'nosed_used_avg': round(self.nosed_used_avg, 2),
            'nosed_used_median': round(self.nosed_used_median, 2),
            'nosed_used_max': self.nosed_used_max,
            'nosed_used_min': self.nosed_used_min,
        }

    def __str__(self) -> str:
        return json.dumps(self.to_dict())


class ExperimentResult:
    def __init__(self, args: argparse.Namespace, cluster: str, start_time: datetime, elapsed_time: timedelta,
                 postprocessed_data: PostprocessedData, measurements_taken: List[Measurements],
                 ):
        self.args = args
        self.cluster = cluster
        self.start_time = start_time
        self.elapsed_time = elapsed_time
        self.postprocessed_data = postprocessed_data
        self.measurements_taken = measurements_taken

    def to_dict(self) -> dict:
        dictionary = {
            "args": vars(self.args),
            "cluster": self.cluster,
            "start_time": self.start_time.isoformat(timespec='seconds'),
            "elapsed_time": str(self.elapsed_time),
            "postprocessed_data": self.postprocessed_data.to_dict(),
            "measurements_taken": [m.to_dict() for m in self.measurements_taken],
        }
        dictionary["args"]["scenario"] = self.args.scenario.name
        dictionary["args"]["action"] = self.args.action.value
        return dictionary

    def __str__(self) -> str:
        return json.dumps(self.to_dict())

    def write_to_file(self, parent_path: Path):
        parent_path.mkdir(parents=True, exist_ok=True)
        file_path = parent_path / f"{self.args.scenario.name}-{self.start_time.isoformat(timespec='seconds')}.json"
        logger.debug(f"Saving measurements to {file_path}")
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=4)
            logger.info(f"Experiment result written to {file_path}")
