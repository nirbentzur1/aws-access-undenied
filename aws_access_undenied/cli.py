from __future__ import annotations

import logging
from typing import IO

import boto3
import click
import click_log
import colorlog
import json

from aws_access_undenied import analysis
from aws_access_undenied import common
from aws_access_undenied import logger
from aws_access_undenied import organizations


def _initialize_logger() -> None:
    click_log.basic_config(logger)
    root_handler = logger.handlers[0]
    formatter = colorlog.ColoredFormatter(
        "%(log_color)s[%(asctime)s,%(msecs)d %(levelname)-8s"
        " %(filename)s:%(lineno)d - %(funcName)20s()]%(reset)s"
        " %(white)s%(message)s",
        datefmt="%H:%M:%S",
        reset=True,
        log_colors={
            "DEBUG": "blue",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red",
        },
    )
    root_handler.setFormatter(formatter)


def _initialize_config_from_user_input(
    config: common.Config,
    output_file: IO[str],
    management_account_role_arn: str,
    suppress_output: bool,
    cross_account_role_name: str,
) -> None:
    config.cross_account_role_name = cross_account_role_name
    config.management_account_role_arn = management_account_role_arn
    if logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    config.output_file = output_file
    config.suppress_output = suppress_output


_initialize_logger()
pass_config = click.make_pass_decorator(common.Config, ensure=True)


@click.group()
@click_log.simple_verbosity_option(logger)
@click.option(
    "--profile",
    help="the AWS profile to use (default is default profile)",
    default=None,
)
@pass_config
def aws_access_undenied(config: common.Config, profile: str) -> None:
    """
    Parses AWS AccessDenied CloudTrail events, explains the reasons for them, and offers actionable fixes.
    """
    config.session = boto3.Session(profile_name=profile)
    config.account_id = config.session.client("sts").get_caller_identity()["Account"]
    config.iam_client = config.session.client("iam")


@aws_access_undenied.command()
@click.option(
    "--events-file",
    help="input file of CloudTrail events",
    required=True,
    type=click.File("r"),
)
@click.option(
    "--scp-file",
    help="Service control policy data file generated by the get_scps command.",
    default=None,
    type=click.File("r"),
)
@click.option(
    "--management-account-role-arn",
    help=(
        "a cross-account role in the management account of the organization "
        "that must be assumable by your credentials."
    ),
    default=None,
)
@click.option(
    "--cross-account-role-name",
    help=(
        "The name of the cross-account role for AccessUndenied to assume."
        " default: AccessUndeniedRole"
    ),
    default="AccessUndeniedRole",
)
@click.option(
    "--output-file",
    help="output file for results (default: no output to file)",
    default=None,
    type=click.File("w"),
)
@click.option(
    "--suppress-output/--no-suppress-output",
    help="should output to stdout be suppressed (default: not suppressed)",
    default=False,
)
@pass_config
def analyze(
    config: common.Config,
    events_file: click.File,
    scp_file: IO[str],
    management_account_role_arn: str,
    cross_account_role_name: str,
    output_file: IO[str],
    suppress_output: bool,
) -> None:
    """
    Analyzes AWS CloudTrail events and explains the reasons for AccessDenied
    """
    _initialize_config_from_user_input(
        config,
        output_file,
        management_account_role_arn,
        suppress_output,
        cross_account_role_name,
    )
    organizations.initialize_organization_data(config, scp_file)
    analysis.analyze_cloudtrail_events(config, events_file)


@aws_access_undenied.command()
@click.option(
    "--output-file",
    help="output file for scp data (default: scp_data.json)",
    default="scp_data.json",
    type=click.File("w"),
)
@pass_config
def get_scps(
    config: common.Config,
    output_file: IO[str],
) -> None:
    """
    Writes the organization's SCPs and organizational tree to a file
    """
    logger.info("Gathering Service Control Policy data...")
    organizations.initialize_organization_data(config, None)
    json.dump(config.organization_nodes, output_file, default=vars, indent=2)
    logger.info(f"Finished writing Service Control Policy data to {output_file.name}.")
