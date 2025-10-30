#!/usr/bin/env python3

import argparse
import glob
import json
import logging
import os
import sys

from datetime import datetime, timedelta
from pathlib import Path

from measurements import gather_cluster_measurements
from postprocess import PostprocessedData
from deploy import verify_install, uninstall_scenario, install_scenario, verify_cluster, render_templates

RELEASE_PREFIX = "bw-"
COSMOS_DEV_COSMOS_CONTEXT_NAME = "arn:aws:eks:us-east-1:843722649052:cluster/cosmos-dev-cosmos"
VALUES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/values"
TEMPLATES_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/build/templates"
MEASUREMENTS_DIR = f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/output"


def setup_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logger = logging.getLogger(__name__)
    return logger

logger = setup_logging()

def parse_args():
    parser = argparse.ArgumentParser(description="Install a scenario")
    parser.add_argument("scenario", type=str, help="The name of the scenario to install", choices=get_scenarios(parser))
    parser.add_argument("--debug", "-d", action="store_true", help="Debug mode")
    parser.add_argument("--no-print", "-np", action="store_true", help="Do not print to console")
    parser.add_argument("--dry-run", action="store_true", help="Do a dry run")
    parser.add_argument("--render-locally", action="store_true", help="Render the templates locally")
    install_group = parser.add_mutually_exclusive_group(required=False)
    install_group.add_argument("--uninstall", "-u", action="store_true", help="Uninstall the scenario instead of installing it")
    install_group.add_argument("--skip-install", "-s", action="store_true", help="Take measurements without performing the install")

    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        # kubernetes is WAY too verbose in debug mode
        logging.getLogger("kubernetes").setLevel(logging.INFO)
    scenario_dir = f"{VALUES_DIR}/{args.scenario}"
    if not os.path.exists(scenario_dir):
        parser.error(f"Scenario directory '{scenario_dir}' does not exist")

    values_pattern = f"{VALUES_DIR}/{args.scenario}/*.yaml"
    values_files = glob.glob(values_pattern)

    if not values_files:
        parser.error(f"No .yaml files found in {scenario_dir}")

    release_to_values_path = {}
    release_names = []
    for values_file in values_files:
        values_path = Path(values_file)
        install_id = values_path.name.replace("values-", "").replace(".yaml", "")
        release_name = f"{RELEASE_PREFIX}{install_id}"
        release_names.append(release_name)
        release_to_values_path[release_name] = values_path

    return args, release_to_values_path

def get_scenarios(parser: argparse.ArgumentParser):
    try:
        return sorted(os.listdir(VALUES_DIR))
    except FileNotFoundError:
        parser.error(f"No scenarios found in {VALUES_DIR}")

def main():
    try:
        args, release_to_values = parse_args()

        logger.info(f"Scenario {args.scenario} loaded. {len(release_to_values)} releases")
        logger.debug(f"Release names: {release_to_values.keys()}")

        verify_cluster(COSMOS_DEV_COSMOS_CONTEXT_NAME)

        # Do not collect release info since that will be done after install
        measurements_pre = gather_cluster_measurements()
        if (not args.no_print) and (not args.skip_install):
            logger.info(f"Pre-install measurements:")
            measurements_pre.print()

        if args.render_locally:
            logger.info(f"Rendering templates locally for {args.scenario}")
            for release_name, values_path in release_to_values.items():
                render_templates(release_name, values_path, Path(TEMPLATES_DIR), debug=args.debug)

        install_time = None
        if not args.skip_install:
            start_time = datetime.now()
            if args.uninstall:
                logger.info(f"Uninstalling {args.scenario}")
                uninstall_scenario(release_to_values.keys(), dry_run=args.dry_run, debug=args.debug)
            else:
                logger.info(f"Installing {args.scenario}")
                install_scenario(release_to_values, dry_run=args.dry_run, debug=args.debug)
            end_time = datetime.now()
            install_time = timedelta(seconds=round((end_time - start_time).total_seconds()))
            logger.info(f"{'Uninstall' if args.uninstall else 'Install'} time: {install_time}s")

        if not args.uninstall:

            verify_install(release_to_values.keys())

            # Gather post-install measurements
            measurements_post = gather_cluster_measurements(release_to_values.keys())
            if not args.no_print:
                logger.info(f"Post-install measurements:")
                measurements_post.print()
            postprocessed_data = PostprocessedData(measurements_pre, measurements_post).to_dict()
            if not args.no_print:
                logger.info(f"Postprocessed data: {postprocessed_data}")

            timestamp = datetime.now().isoformat(timespec='seconds')
            measurements_file = f"{MEASUREMENTS_DIR}/{args.scenario}/{args.scenario}-{timestamp}.json"
            logger.info(f"Saving measurements to {measurements_file}")
            os.makedirs(f"{MEASUREMENTS_DIR}/{args.scenario}", exist_ok=True)
            with open(measurements_file, 'w') as f:
                data = {
                    "args": vars(args),
                    "timestamp": timestamp,
                    "install_time": str(install_time),
                    "postprocessed": postprocessed_data,
                    "measurements_pre": measurements_pre.to_dict(),
                    "measurements_post": measurements_post.to_dict(),
                }
                json.dump(data, f, indent=4)

        logger.info("Done")
    except Exception:
        logger.exception(f"Error running scenario {args.scenario}")
        sys.exit(1)




if __name__ == "__main__":
    main()
