import pytest
import boto3

from chalice import Chalice
from chalice.config import Config
from chalice.local import LocalGateway
from Sling.chalicelib import api, prmbot

from .constants import *

# Setup
app = Chalice(app_name="sling")

# Blueprints confirmed to be fully supported
app.experimental_feature_flags.update(["BLUEPRINTS"])
app.register_blueprint(api.lockapi)
app.register_blueprint(prmbot.prmbot)


@pytest.fixture
def gateway_factory():
    """A fixutre that helps set up our rows in our DynamoDB table.

    This fixture runs at the default function scope, meaning it will run whenever
    a method that has gateway_factory as one of its params. Note that even if 
    it isn't used in the method, the fixture will still set up at the begining of 
    the function and takedown at the end of it. 

    In order to see the print messages, make sure your pytest command uses the
    -v and -s flag.
    """

    client = boto3.client("dynamodb")
    lock_table_name = LOCK_TABLE_NAME
    service_table_name = SERVICE_TABLE_NAME
    log_table_name = LOG_TABLE_NAME

    existing_tables = client.list_tables()["TableNames"]

    if lock_table_name not in existing_tables:
        client.create_table(
            AttributeDefinitions=[{"AttributeName": "LockName", "AttributeType": "S"},],
            TableName=lock_table_name,
            KeySchema=[{"AttributeName": "LockName", "KeyType": "HASH"},],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
    if service_table_name not in existing_tables:
        client.create_table(
            AttributeDefinitions=[
                {"AttributeName": "ServiceName", "AttributeType": "S"},
            ],
            TableName=service_table_name,
            KeySchema=[{"AttributeName": "ServiceName", "KeyType": "HASH"},],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
    if log_table_name not in existing_tables:
        client.create_table(
            AttributeDefinitions=[{"AttributeName": "JobId", "AttributeType": "S"},],
            TableName=log_table_name,
            KeySchema=[{"AttributeName": "JobId", "KeyType": "HASH"},],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )

    client.put_item(
        TableName=lock_table_name,
        Item={
            "LockName": {"S": "unheld_lock"},
            "HeldBy": {"S": ""},
            "Lock_Acquire_DateTime": {"S": ""},
            "JobId": {"S": ""},
        },
    )
    client.put_item(
        TableName=service_table_name, Item={"ServiceName": {"S": "unheld_service"}},
    )
    client.put_item(
        TableName=lock_table_name,
        Item={
            "LockName": {"S": "held_lock"},
            "HeldBy": {"S": "held_service"},
            "Lock_Acquire_DateTime": {"S": "2020"},
            "JobId": {"S": "101"},
        },
    )
    client.put_item(
        TableName=lock_table_name,
        Item={
            "LockName": {"S": "released_service_lock"},
            "HeldBy": {"S": "released_service"},
            "Lock_Acquire_DateTime": {"S": "2020"},
            "JobId": {"S": "101"},
        },
    )

    client.put_item(
        TableName=service_table_name, Item={"ServiceName": {"S": "held_service"}},
    )

    yield LocalGateway(app, Config())

    client.delete_item(
        TableName=lock_table_name, Key={"LockName": {"S": "released_service_lock"}},
    )
    client.delete_item(
        TableName=lock_table_name, Key={"LockName": {"S": "unheld_lock"}},
    )
    client.delete_item(
        TableName=service_table_name, Key={"ServiceName": {"S": "unheld_service"}}
    )
    client.delete_item(
        TableName=lock_table_name, Key={"LockName": {"S": "held_lock"}},
    )
    client.delete_item(
        TableName=service_table_name, Key={"ServiceName": {"S": "held_service"}}
    )
    client.delete_item(TableName=log_table_name, Key={"JobId": {"S": "101"}})
