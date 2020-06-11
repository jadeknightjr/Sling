import logging
import json
import requests
import base64
import os

import boto3
from github3 import login, GitHubError
from chalice import Blueprint
from urllib3.exceptions import NewConnectionError

from .state_manager import state_manager_acquire, state_manager_release

prmbot = Blueprint(__name__)

logger = logging.getLogger(__name__)

# Logger prints to console
console = logging.StreamHandler()
logger.addHandler(console)

# Environmental Variables
PRM_BOT_RUNTIME = os.environ.get("PRM_BOT_RUNTIME", 300)


def get_secret(secret_name, region_name):
    """Grabs the values from AWS Secrets Manager"""

    # Create a Secrets Manager client
    session = boto3.session.Session()
    client = session.client(service_name="secretsmanager", region_name=region_name)

    get_secret_value_response = client.get_secret_value(SecretId=secret_name)

    if "SecretString" in get_secret_value_response:
        secret = get_secret_value_response["SecretString"]
        return json.loads(secret)
    else:
        decoded_binary_secret = base64.b64decode(
            get_secret_value_response["SecretBinary"]
        )
        return json.loads(decoded_binary_secret)


def get_config(config_path):
    """Grab values from the provided config path"""

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError as e:
        logger.debug("File path: %s does not exist", config_path)
        raise e
    return config


def has_valid_label(labels_list, merge_label):
    """Checks if the labels_list contains the provided merge_label"""

    for label in labels_list:
        if label["name"] == merge_label:
            return True
    return False


def has_valid_review(reviews, pr_id):
    """Determines if a pull request has a review that makes the pull request mergeable

        Currently, GitHub states could be the following:
        COMMENT:Submit general feedback
        APPROVED: Approve merging the changes proposed in pull request
        REQUEST_CHANGES: Submit feedback that must be addressed before merge
    """

    for review in reviews:

        state = review.state
        auth_assoc = review.author_association
        if state == "APPROVED" and auth_assoc in ("COLLABORATOR", "MEMBER", "OWNER"):
            return True

    logger.warning(
        "Pull Requests: %s has a mergeable tag, but doesn't have approval review", pr_id
    )
    return False


def get_mergeable_pr(pr_generator, config):
    """Returns a list of pull requests that are ready to be merged"""

    mergeable_pr = []
    for pull_req in pr_generator:
        labels = pull_req.labels
        if has_valid_label(labels, config["merge_label"]):
            reviews = pull_req.reviews()
            if has_valid_review(reviews, pull_req.id):
                mergeable_pr.append(pull_req)
    return mergeable_pr


def merge_pull_req(mergeable_pr_list, config):
    """Merges qualified pull requests and returns list of pull requests that somehow fail to merge"""

    failed_mergeable_pr = []
    for pull_req in mergeable_pr_list:
        pr_id = pull_req.id
        try:
            pull_req.merge(
                commit_message=config["commit_msg"],
                commit_title=config["commit_title"],
                merge_method=config["merge_type"],
            )
            logger.warning(f"Successfully merged pull request #{pr_id}")
        except (requests.exceptions.RequestException, GitHubError) as e:
            logger.warning(f"Unable to merge pull request #{pr_id}: {str(e)}")
            failed_mergeable_pr.append(pull_req)

    return failed_mergeable_pr


@prmbot.schedule(f"rate({PRM_BOT_RUNTIME} minutes)")
def prm_bot(event):

    # Config File Settings
    config_path = "chalicelib/settings/config.json"
    config = get_config(config_path)

    # GitHub Login Credentials
    secret_name = config["secret_name"]
    region_name = config["region_name"]

    github_credentials = get_secret(secret_name, region_name)
    github_username = github_credentials["github_username"]
    github_password = github_credentials["github_password"]

    # Get GitHub Repository
    github_client = login(github_username, password=github_password)
    repository = github_client.repository(config["repo_owner"], config["repo_name"])

    # Find all mergeable PR
    pull_req_generator = repository.pull_requests()
    mergeable_pr = get_mergeable_pr(pull_req_generator, config)

    if len(mergeable_pr) == 0:
        logger.warning("Nothing to do here")
        return "Nothing to do here"

    service_name = config["service_name"]
    lock_name = config["lock_name"]
    lock_table_name = config["lock_table_name"]
    service_table_name = config["service_table_name"]
    log_table_name = config["log_table_name"]

    # Find API Route and strip possible leading or trailing white spaces
    api_route = config["api_route"].strip()
    if not api_route:
        logger.critical("No REST API URL found in config. ")
        return {
            "message": "Endpoint configured incorrectly or inaccessible. Please contact service administrator"
        }
    try:
        acquire_lock_resp = state_manager_acquire(
            api_route, service_name, lock_name, lock_table_name, service_table_name
        )
        if acquire_lock_resp.status_code == 200:

            # Grab JobId for later release of lock
            job_id = acquire_lock_resp.json()["ResponseMetadata"]["JobId"]

            logger.warning("Acquired lock successfully. JobID: %s", job_id)

            # Merge the pull requests. We should know which ones failed.
            failed_mergeable_pr = merge_pull_req(mergeable_pr, config)
            # Used warn here so that message will appear in lambda logs
            logger.warning(
                "Merged the following pull requests: %s",
                set(mergeable_pr) - set(failed_mergeable_pr),
            )
            logger.warning(
                "Failed to merge the following pull requests: %s", failed_mergeable_pr
            )

            release_lock_resp = state_manager_release(
                api_route,
                service_name,
                lock_name,
                job_id,
                lock_table_name,
                log_table_name,
            )

            if release_lock_resp.status_code == 200:
                logger.warning("Released lock successfully")
            else:
                # CloudWatch Alarms Catches this and reports it
                message = "For JobId: {0} :Failed to release lock: {1}".format(
                    job_id, release_lock_resp.json()["Message"]
                )
                logger.critical(message)
        else:
            # CloudWatch Alarms Catches this and reports it
            message = "Failed to acquire lock"
            logger.warning(message)
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.RequestException,
        NewConnectionError,
    ) as e:
        logger.critical(f"The following exception occurred: {str(e)}")
    except Exception as e:
        logger.critical(str(e))
