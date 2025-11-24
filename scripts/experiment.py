#!/usr/bin/env python3

import argparse
from enum import Enum
import logging
import sys

from datetime import datetime, timedelta
from pathlib import Path
import time
from typing import Dict, Tuple

import deploy
import scenarios
import collect
import utils
from postprocess import ExperimentResult, PostprocessedData

DEFAULT_RELEASE_PREFIX = ""
COSMOS_DEV_COSMOS_CONTEXT_NAME = "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos"

ROLLOUT_WAIT = 300

logger = logging.getLogger(__name__)


class Action(Enum):
    INSTALL = "install"
    UNINSTALL = "uninstall"
    RESTART = "restart"
    NONE = "none"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    def __eq__(self, other):
        return self.value == other.value


def parse_args() -> Tuple[argparse.Namespace, Dict[str, Path]]:
    parser = argparse.ArgumentParser(description="Install a scenario")
    parser.add_argument(
        "scenario",
        type=scenarios.parse_scenario,
        help="The name of the scenario to install",
        choices=scenarios.SCENARIOS
    )

    # General arguments
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")
    parser.add_argument("--no-print", "-np", action="store_true",
                        help="Do not include measurement visualizations in the console output")
    parser.add_argument("--dry-run", action="store_true", help="Do a dry run")

    # Local template rendering arguments
    parser.add_argument("--render-locally", action="store_true", help="Render the templates locally")
    parser.add_argument("--skip-value-generation", action="store_true",
                        help="Skip value generation. Useful for testing manually crafted values files.")

    # Install modification arguments
    parser.add_argument("--namespace", "-ns", required=True, type=str,
                        help="The namespace to install the scenario into")
    parser.add_argument("--release-prefix", "-rp", type=str,
                        help="Prefix all generated release names with this string",
                        required=False, default=DEFAULT_RELEASE_PREFIX)
    # Action arguments
    parser.add_argument("--action", "-a", type=Action, choices=list(Action),
                        help="The action to perform", default=Action.INSTALL)

    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # kubernetes is WAY too verbose in debug mode
        logging.getLogger("kubernetes").setLevel(logging.INFO)

    # args.scenario is already a Scenario instance at this point
    if not args.skip_value_generation:
        scenarios.generate_values(args.scenario)

    # Sanity check that generation succeeded as expected
    scenario_dir = utils.VALUES_DIR / args.scenario.name
    if not scenario_dir.exists():
        parser.error(f"Scenario directory '{scenario_dir}' does not exist")

    values_files = list(scenario_dir.glob("*.yaml"))

    if not values_files:
        parser.error(f"No .yaml files found in scenario directory {scenario_dir.name}")

    release_to_values_path: Dict[str, Path] = {}
    release_names = []
    for values_file in values_files:
        values_path = Path(values_file)
        install_id = values_path.name.replace("values-", "").replace(".yaml", "")
        release_name = f"{args.release_prefix}{install_id}"
        release_names.append(release_name)
        release_to_values_path[release_name] = values_path

    return args, release_to_values_path


def main():
    utils.setup_logging()
    args = None
    try:
        args, release_to_values = parse_args()

        logger.info(f"Scenario {args.scenario} loaded. {len(release_to_values)} releases. Action: {args.action}")
        logger.debug(f"Release names: {release_to_values.keys()}")

        if args.render_locally:
            logger.info(f"Rendering templates locally for {args.scenario}")
            for release_name, values_path in release_to_values.items():
                deploy.render_templates(args.scenario, release_name, values_path, args.namespace, utils.TEMPLATES_DIR,
                                        debug=args.debug)

        deploy.verify_cluster(COSMOS_DEV_COSMOS_CONTEXT_NAME)

        measurements_pre = collect.gather_cluster_measurements([args.namespace])
        if not args.no_print:
            logger.info("Pre-action measurements:")
            measurements_pre.print()

        start_time = datetime.now()
        elapsed_time = perform_action(args, release_to_values)
        logger.info(f"{args.action.value} took {elapsed_time}")

        # Gather post-install measurements
        measurements_post = collect.gather_cluster_measurements([args.namespace])
        if not args.no_print:
            logger.info("Post-action measurements:")
            measurements_post.print()
        postprocessed_data = PostprocessedData(measurements_pre, measurements_post)
        if not args.no_print:
            logger.info(f"Postprocessed data: {postprocessed_data}")

        experiment_result = ExperimentResult(args, COSMOS_DEV_COSMOS_CONTEXT_NAME, start_time, elapsed_time,
                                             postprocessed_data, [measurements_pre, measurements_post])
        experiment_result.write_to_file(utils.OUTPUT_DIR / args.scenario.name)

        logger.info("Done")
    except Exception:
        if args and args.scenario:
            logger.exception(f"Error running scenario {args.scenario}")
        else:
            logger.exception("Unexpected error occurred")
        sys.exit(1)


def perform_action(args: argparse.Namespace, release_to_values: Dict[str, Path]) -> timedelta:
    start_time = datetime.now()
    logger.info(f"Performing {args.action} on {len(release_to_values)} releases in namespace {args.namespace}")
    if args.action == Action.INSTALL:
        deploy.install_scenario(release_to_values, args.namespace, dry_run=args.dry_run, debug=args.debug)
        # Wait for pods to start
        if not args.dry_run:
            deploy.verify_install(release_to_values.keys(), args.namespace)
    elif args.action == Action.UNINSTALL:
        deploy.uninstall_scenario(release_to_values.keys(), args.namespace, dry_run=args.dry_run, debug=args.debug)
    elif args.action == Action.RESTART:
        deploy.restart_deployments(release_to_values.keys(), args.namespace, dry_run=args.dry_run, debug=args.debug)
        logger.info("Waiting for rollout restart to complete")
        time.sleep(ROLLOUT_WAIT)
        # Wait for rollout restart to complete
        if not args.dry_run:
            deploy.verify_install(release_to_values.keys(), args.namespace)
    elif args.action == Action.NONE:
        logger.info("No action specified. Skipping.")
    else:
        raise ValueError(f"Invalid action: {args.action}")
    end_time = datetime.now()
    return end_time - start_time if not args.action == Action.NONE else timedelta(0)


if __name__ == "__main__":
    main()
