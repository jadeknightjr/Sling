import os
import json
import logging

from aws_cdk import (
    aws_cloudwatch as _cw,
    aws_logs as _logs,
    aws_dynamodb as _dynamodb,
    core,
)

logger = logging.getLogger(__name__)

# Logger prints to console
console = logging.StreamHandler()
logger.addHandler(console)

# While an exact copy exists on Chalice, I want to try to make the two parts
# of Sling as decoupled as possible
def get_config(config_path):
    """Grab values from the provided config path"""

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
    except FileNotFoundError as e:
        logger.debug("File path: %s does not exist", config_path)
        raise e
    return config


METRIC_NAME = "critical-counts-metric"
METRIC_NAMESPACE = "sling"
FILTER_TAG = '"[CRITICAL]"'


config = get_config("../chalicelib/settings/config.json")
LOG_GROUP_NAME = config["log_group_name"]

# Environmental Variables
PRM_BOT_RUNTIME = os.environ.get("PRM_BOT_RUNTIME", 300)


class CdkEnvironmentSetupStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        critical_counts_metric = _cw.Metric(
            namespace=METRIC_NAMESPACE, metric_name=METRIC_NAME
        )

        critical_filter = _logs.FilterPattern.literal(FILTER_TAG)
        _logs.MetricFilter(
            self,
            id="MetricFilterId",
            metric_name=METRIC_NAME,
            metric_namespace=METRIC_NAMESPACE,
            log_group=_logs.LogGroup.from_log_group_name(
                self, id="log_group_id", log_group_name=LOG_GROUP_NAME,
            ),
            filter_pattern=critical_filter,
            default_value=0,
        )

        sling_alarm = _cw.Alarm(
            self,
            id="PRMBot Critical Alarm",
            metric=critical_counts_metric,
            evaluation_periods=1,
            actions_enabled=True,
            alarm_name="critical_alarm",
            alarm_description="Alarms for critical errors",
            comparison_operator=_cw.ComparisonOperator.GREATER_THAN_THRESHOLD,
            datapoints_to_alarm=1,
            period=core.Duration.minutes(PRM_BOT_RUNTIME),
            threshold=0,
            statistic="max",
        )

        locks_table = _dynamodb.Table(
            self,
            id="lock_table_name",
            table_name=config["lock_table_name"],
            removal_policy=core.RemovalPolicy.DESTROY,
            partition_key=_dynamodb.Attribute(
                name="LockName", type=_dynamodb.AttributeType.STRING
            ),
        )

        registered_services_table = _dynamodb.Table(
            self,
            id="services_dynamodb_table",
            table_name=config["service_table_name"],
            removal_policy=core.RemovalPolicy.DESTROY,
            partition_key=_dynamodb.Attribute(
                name="ServiceName", type=_dynamodb.AttributeType.STRING
            ),
        )

        log_table = _dynamodb.Table(
            self,
            id="log_dynamodb_table",
            table_name=config["log_table_name"],
            removal_policy=core.RemovalPolicy.DESTROY,
            partition_key=_dynamodb.Attribute(
                name="JobId", type=_dynamodb.AttributeType.STRING
            ),
        )
