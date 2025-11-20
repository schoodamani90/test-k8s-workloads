#!/usr/bin/env python3
import json
import logging
import statistics
from typing import Optional

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

        if not measurements_post.deployments:
            logger.warning("No deployments found in post-action measurements")
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
        jfi_values = [d.jain_fairness_index for d in measurements_post.deployments.values()]
        self.jain_fairness_index_mean = statistics.mean(jfi_values)
        self.jain_fairness_index_median = statistics.median(jfi_values)

        cov_values = [d.coefficient_of_variation for d in measurements_post.deployments.values()]
        self.coefficient_of_variation_mean = statistics.mean(cov_values)
        self.coefficient_of_variation_median = statistics.median(cov_values)

        gci_values = [d.gini_coefficient for d in measurements_post.deployments.values()]
        self.gini_coefficient_mean = statistics.mean(gci_values)
        self.gini_coefficient_median = statistics.median(gci_values)

        # determine mean, median, and max skew of node_skew (raw and percentage)
        node_skew_values = [d.node_skew for d in measurements_post.deployments.values()]
        self.node_skew_mean = statistics.mean(node_skew_values)
        self.node_skew_median = statistics.median(node_skew_values)
        self.node_skew_max = max(node_skew_values)

        node_skew_percentage_values = [d.node_skew_percentage for d in measurements_post.deployments.values()]
        self.node_skew_percentage_mean = statistics.mean(node_skew_percentage_values)
        self.node_skew_percentage_median = statistics.median(node_skew_percentage_values)
        self.node_skew_percentage_max = max(node_skew_percentage_values)

        # more metrics on node usage
        nosed_used_values = [d.nodes_used for d in measurements_post.deployments.values()]
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
