#!/usr/bin/env python3

import argparse
import logging
import sys
import time

from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Tuple

import deploy
import scenarios
import measurements
import utils
from postprocess import PostprocessedData


DEFAULT_RELEASE_PREFIX = "bw-"
COSMOS_DEV_COSMOS_CONTEXT_NAME = "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos"

RESTART_DELAY = 60
ROLLOUT_WAIT = 300


logger = logging.getLogger(__name__)


def parse_args() -> Tuple[argparse.Namespace, Dict[str, Path]]:
    parser = argparse.ArgumentParser(description="Install a scenario")
    parser.add_argument("scenario", type=str, help="The name of the scenario to install", choices=get_scenarios())
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")
    parser.add_argument("--no-print", "-np", action="store_true", help="Do not print to console")
    parser.add_argument("--release-prefix", "-rp", type=str,
                        help="Prefix all generated release names with this string", default=DEFAULT_RELEASE_PREFIX)
    parser.add_argument("--dry-run", action="store_true", help="Do a dry run")
    parser.add_argument("--render-locally", action="store_true", help="Render the templates locally")
    parser.add_argument("--skip-value-generation", action="store_true", help="Skip value generation")

    install_group = parser.add_mutually_exclusive_group(required=False)
    install_group.add_argument("--uninstall", "-u", action="store_true",
                               help="Uninstall the scenario instead of installing it")
    install_group.add_argument("--skip-install", "-s", action="store_true",
                               help="Take measurements without performing the install. Also skips restarts.")

    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # kubernetes is WAY too verbose in debug mode
        logging.getLogger("kubernetes").setLevel(logging.INFO)

    try:
        args.scenario = scenarios.get_scenario(args.scenario)
        if not args.skip_value_generation:
            scenarios.generate_values(args.scenario)
    except ValueError:
        parser.error(f"Scenario {args.scenario} not found")

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


def get_scenarios():
    return [scenario.name for scenario in scenarios.SCENARIOS]


def main():
    utils.setup_logging()
    args = None
    try:
        args, release_to_values = parse_args()

        logger.info(f"Scenario {args.scenario} loaded. {len(release_to_values)} releases")
        logger.debug(f"Release names: {release_to_values.keys()}")

        deploy.verify_cluster(COSMOS_DEV_COSMOS_CONTEXT_NAME)

        measurements_pre = measurements.gather_cluster_measurements(release_to_values.keys())
        if (not args.no_print) and (not args.skip_install):
            logger.info("Pre-install measurements:")
            measurements_pre.print()

        if args.render_locally:
            logger.info(f"Rendering templates locally for {args.scenario}")
            for release_name, values_path in release_to_values.items():
                deploy.render_templates(release_name, values_path, utils.TEMPLATES_DIR, debug=args.debug)

        install_time = None
        if not args.skip_install:
            start_time = datetime.now()
            if args.uninstall:
                logger.info(f"Uninstalling {args.scenario}")
                deploy.uninstall_scenario(release_to_values.keys(), dry_run=args.dry_run, debug=args.debug)
            else:
                logger.info(f"Installing {args.scenario}")
                deploy.install_scenario(release_to_values, dry_run=args.dry_run, debug=args.debug)
            end_time = datetime.now()
            install_time = timedelta(seconds=round((end_time - start_time).total_seconds()))
            logger.info(f"{'Uninstall' if args.uninstall else 'Install'} time: {install_time}s")

        if not args.uninstall:

            deploy.verify_install(release_to_values.keys())

            measurements_mid = measurements.gather_cluster_measurements(release_to_values.keys())

            if args.scenario.restart_count > 0 and not args.skip_install:
                logger.info(f"Restarting deployments {release_to_values.keys()} {args.scenario.restart_count} times")
                for restart_index in range(args.scenario.restart_count):
                    logger.info(f"Beginning restart {restart_index + 1}/{args.scenario.restart_count}")
                    deploy.restart_deployments(release_to_values.keys())
                    # From experimentation, rollouts take a bit longer than the initial install
                    logger.info(f"Waiting {ROLLOUT_WAIT} seconds for rollouts to complete")
                    time.sleep(ROLLOUT_WAIT)
                    deploy.verify_install(release_to_values.keys())
                    logger.info(f"Completed restart {restart_index + 1}/{args.scenario.restart_count}")
                    time.sleep(RESTART_DELAY)
                logger.info("Restarts complete")

            # Gather post-install measurements
            measurements_post = measurements.gather_cluster_measurements(release_to_values.keys())
            if not args.no_print:
                logger.info("Post-install measurements:")
                measurements_post.print()
            postprocessed_data = PostprocessedData(measurements_pre, measurements_post).to_dict()
            if not args.no_print:
                logger.info(f"Postprocessed data: {postprocessed_data}")

            utils.write_measurements(args.scenario.name, args, install_time, postprocessed_data,
                                     [measurements_pre, measurements_mid, measurements_post])
        logger.info("Done")
    except Exception:
        if args and args.scenario:
            logger.exception(f"Error running scenario {args.scenario}")
        else:
            logger.exception("Unexpected error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()
