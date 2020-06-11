import json
import pytest
import uuid
import boto3

from Sling.chalicelib.api import (
    retrieve_tables_values,
    dictify_resp,
    ValidationException,
)

from .constants import *


@pytest.mark.usefixtures("gateway_factory")
class TestChaliceHelperFunctions:
    """Class testing the helper functions in api.py"""

    def test_retrieve_tables_values(self, gateway_factory):

        # Case 1: Lock is held
        resp = retrieve_tables_values("held_lock", LOCK_TABLE_NAME)
        assert resp[0]["Item"]["HeldBy"]["S"] == "held_service"
        assert resp[0]["Item"]["JobId"]["S"] == "101"

        # Case 2: Lock is not held
        resp = retrieve_tables_values("unheld_lock", LOCK_TABLE_NAME)
        assert resp[0]["Item"]["HeldBy"]["S"] == ""
        assert resp[0]["Item"]["JobId"]["S"] == ""

    @pytest.mark.parametrize(
        "sample, expected",
        [
            (
                [
                    {
                        "Item": {
                            "HeldBy": {"S": "MyRelease"},
                            "LockName": {"S": "MyOtherLock"},
                            "Lock_Acquire_DateTime": {"S": "...20:06:49.990921"},
                        }
                    },
                    {
                        "Item": {
                            "JobId": {"S": "123"},
                            "ServiceName": {"S": "MyRelease"},
                        }
                    },
                ],
                ("MyRelease", "MyOtherLock", "123"),
            ),
            (
                [
                    {
                        "Item": {
                            "HeldBy": {"S": ""},
                            "LockName": {"S": "MyOtherLock"},
                            "Lock_Acquire_DateTime": {"S": "...20:06:49.990921"},
                        }
                    },
                    {
                        "Item": {
                            "JobId": {"S": ""},
                            "ServiceName": {"S": "MyRelease"},
                        }
                    },
                ],
                ("", "MyOtherLock", ""),
            ),
        ],
    )
    def test_dictify_resp(self, sample, expected):
        resp = dictify_resp(sample)
        assert resp["HeldBy"] == expected[0]
        assert resp["LockName"] == expected[1]
        assert resp["JobId"] == expected[2]


@pytest.mark.usefixtures("gateway_factory")
class TestChaliceLocksAndServicesAPI:
    """A class containing tests for our API endpoints.

    This class contains tests for the responses of successful and unsuccessful calls.
    """

    service_name = str(uuid.uuid4())
    lock_name = str(uuid.uuid4())

    lock_table_name = LOCK_TABLE_NAME
    service_table_name = SERVICE_TABLE_NAME
    log_table_name = LOG_TABLE_NAME

    def test_register_service(self, gateway_factory):
        body = {
            "ServiceName": self.service_name,
            "ServiceTableName": self.service_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/register_service",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "Registered Service: %s" % self.service_name
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_register_existing_service(self, gateway_factory):
        body = {
            "ServiceName": "unheld_service",
            "ServiceTableName": self.service_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/register_service",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to register a service"

    def test_register_lock(self, gateway_factory):
        body = {"LockName": self.lock_name, "LockTableName": self.lock_table_name}
        response = gateway_factory.handle_request(
            method="POST",
            path="/register_lock",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "Registered Lock: %s" % self.lock_name
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_register_existing_lock(self, gateway_factory):
        body = {"LockName": "unheld_lock", "LockTableName": self.lock_table_name}
        response = gateway_factory.handle_request(
            method="POST",
            path="/register_lock",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )

        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to register a lock"

    def test_acquire(self, gateway_factory):
        body = {
            "ServiceName": "unheld_service",
            "LockName": "unheld_lock",
            "LockTableName": self.lock_table_name,
            "ServiceTableName": self.service_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/acquire",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "%s acquired the following lock: %s" % (
            "unheld_service",
            "unheld_lock",
        )
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_acquire_acquired_lock(self, gateway_factory):
        body = {
            "ServiceName": "unheld_service",
            "LockName": "held_lock",
            "LockTableName": self.lock_table_name,
            "ServiceTableName": self.service_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/acquire",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to acquire a lock"

    def test_acquire_nonexistant_lock(self, gateway_factory):
        body = {
            "ServiceName": "unheld_service",
            "LockName": "doesn't exist",
            "LockTableName": self.lock_table_name,
            "ServiceTableName": self.service_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/acquire",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to acquire a lock"

    def test_release_lock(self, gateway_factory):
        body = {
            "ServiceName": "held_service",
            "LockName": "held_lock",
            "JobId": "101",
            "LockTableName": self.lock_table_name,
            "LogTableName": self.log_table_name,
        }

        response = gateway_factory.handle_request(
            method="POST",
            path="/release",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "%s released the following lock: %s with JobId: %s" % (
            "held_service",
            "held_lock",
            "101",
        )
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_release_released_lock(self, gateway_factory):
        body = {
            "ServiceName": "unheld_service",
            "LockName": "unheld_lock",
            "JobId": "101",
            "LockTableName": self.lock_table_name,
            "LogTableName": self.log_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/release",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to release lock"

    def test_release_nonexistant_lock(self, gateway_factory):
        nonexistent_lock_name_body = {
            "LockName": "doesn't exist",
            "ServiceName": self.service_name,
            "JobId": "101",
            "LockTableName": self.lock_table_name,
            "LogTableName": self.log_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/release",
            headers={"Content-Type": "application/json"},
            body=json.dumps(nonexistent_lock_name_body),
        )
        assert response["statusCode"] == 409

    def test_release_lock_with_nonexisting_service(self, gateway_factory):
        nonexistent_service_name_body = {
            "LockName": "released_service_lock",
            "ServiceName": "released_service",
            "JobId": "101",
            "LockTableName": self.lock_table_name,
            "LogTableName": self.log_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/release",
            headers={"Content-Type": "application/json"},
            body=json.dumps(nonexistent_service_name_body),
        )
        assert response["statusCode"] == 200

    def test_release_lock_never_existed_service(self, gateway_factory):
        never_existed_service_name_body = {
            "LockName": "held_lock",
            "ServiceName": "doesn't exist",
            "JobId": "101",
            "LockTableName": self.lock_table_name,
            "LogTableName": self.log_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/release",
            headers={"Content-Type": "application/json"},
            body=json.dumps(never_existed_service_name_body),
        )
        assert response["statusCode"] == 409

    def test_release_lock_nonexistant_job_id(self, gateway_factory):
        nonexistent_job_id_body = {
            "LockName": self.lock_name,
            "ServiceName": self.service_name,
            "JobId": "doesn't exist",
            "LockTableName": self.lock_table_name,
            "LogTableName": self.log_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/release",
            headers={"Content-Type": "application/json"},
            body=json.dumps(nonexistent_job_id_body),
        )
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to release lock"

    def test_deregister_lock_held_by_a_service(self, gateway_factory):
        body = {"LockName": "held_lock", "LockTableName": self.lock_table_name}

        response = gateway_factory.handle_request(
            method="POST",
            path="/deregister_lock",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to deregister a lock"

    def test_deregister_lock_not_held_by_a_service(self, gateway_factory):
        body = {"LockName": "unheld_lock", "LockTableName": self.lock_table_name}

        response = gateway_factory.handle_request(
            method="POST",
            path="/deregister_lock",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "Deregistered Lock: %s" % body["LockName"]
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_deregister_service_holding_lock(self, gateway_factory):
        body = {
            "ServiceName": "held_service",
            "ServiceTableName": self.service_table_name,
        }

        response = gateway_factory.handle_request(
            method="POST",
            path="/deregister_service",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "Deregistered Service: %s" % body["ServiceName"]
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_deregister_service_not_holding_lock(self, gateway_factory):
        body = {
            "ServiceName": "unheld_service",
            "ServiceTableName": self.service_table_name,
        }

        response = gateway_factory.handle_request(
            method="POST",
            path="/deregister_service",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )
        assert response["statusCode"] == 200
        actual = json.loads(response["body"])
        expected = "Deregistered Service: %s" % body["ServiceName"]
        assert actual["ResponseMetadata"]["Message"] == expected

    def test_deregister_nonexistant_lock(self, gateway_factory):
        body = {"LockName": "doesn't exist", "LockTableName": self.lock_table_name}
        response = gateway_factory.handle_request(
            method="POST",
            path="/deregister_lock",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )

        assert response["statusCode"] == 409
        assert json.loads(response["body"])["Message"] == "Unable to deregister a lock"

    def test_deregister_nonexistant_service(self, gateway_factory):
        body = {
            "ServiceName": "doesn't exist",
            "ServiceTableName": self.service_table_name,
        }
        response = gateway_factory.handle_request(
            method="POST",
            path="/deregister_service",
            headers={"Content-Type": "application/json"},
            body=json.dumps(body),
        )

        assert response["statusCode"] == 409
        assert (
            json.loads(response["body"])["Message"] == "Unable to deregister a service"
        )

