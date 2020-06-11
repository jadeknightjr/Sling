import json
import pytest

from aws_cdk import core
from cdk_environment_setup.cdk_environment_setup_stack import CdkEnvironmentSetupStack


def get_template():
    app = core.App()
    CdkEnvironmentSetupStack(app, "cdk-alarm")
    return app.synth().get_stack("cdk-alarm").template


def get_resource_prop(resource_type):
    template = get_template()
    template_dict = template["Resources"]

    for k, v in template_dict.items():
        for x, y in v.items():
            if y == resource_type:
                return template_dict[k]["Properties"]
    return {}


def type_exists(resource_type):
    template = get_template()
    template_dict = template["Resources"]

    for k, v in template_dict.items():
        for x, y in v.items():
            if y == resource_type:
                return True
    return False


def get_dynamo_table_prop(table_name):
    template = get_template()
    template_dict = template["Resources"]

    ret_dict = {}
    for k, v in template_dict.items():
        if v["Type"] == "AWS::DynamoDB::Table":
            if v["Properties"]["TableName"] == table_name:
                return v["Properties"]
    return {}


def test_logs_metricfilter_created():
    assert type_exists("AWS::Logs::MetricFilter") == True
    metricfilter_prop = get_resource_prop("AWS::Logs::MetricFilter")
    assert metricfilter_prop["FilterPattern"] == '"[CRITICAL]"'


def test_cloudwatch_alarm_created():
    assert type_exists("AWS::CloudWatch::Alarm") == True
    alarm_prop = get_resource_prop("AWS::CloudWatch::Alarm")
    assert alarm_prop["ComparisonOperator"] == "GreaterThanThreshold"
    assert alarm_prop["AlarmName"] == "critical_alarm"
    assert alarm_prop["Threshold"] == 0
    assert alarm_prop["Statistic"] == "Maximum"


def test_dynamodb_table_created():
    assert type_exists("AWS::DynamoDB::Table") == True

    # Grab Tables
    log_table_prop = get_dynamo_table_prop("SlingLogTable")
    lock_table_prop = get_dynamo_table_prop("SlingLockTable")
    service_table_prop = get_dynamo_table_prop("SlingRegisteredServices")

    # Test primarykey value
    assert log_table_prop["KeySchema"][0]["AttributeName"] == "JobId"
    assert lock_table_prop["KeySchema"][0]["AttributeName"] == "LockName"
    assert service_table_prop["KeySchema"][0]["AttributeName"] == "ServiceName"
