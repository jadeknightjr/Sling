import boto3
import uuid
import logging

from botocore.exceptions import ClientError
from datetime import datetime
from chalice import Response, BadRequestError, Blueprint


lockapi = Blueprint(__name__)

logger = logging.getLogger(__name__)

# Logger prints to console
console = logging.StreamHandler
logger.addHandler(console)


class ValidationException(Exception):
    pass


class SingletonDynamoDBClient:
    __instance = None

    @classmethod
    def getInstance(cls):
        if cls.__instance is None:
            client = boto3.client("dynamodb")
            cls.__instance = client
        return cls.__instance


def check_fields(api_data, fields_list):
    """Checks if every element of fields_list appears inside api_data."""

    missing_fields = [field for field in fields_list if field not in api_data]
    if len(missing_fields) > 0:
        miss_msg = "Missing the following fields in your request: %s" % missing_fields
        raise BadRequestError(miss_msg)


@lockapi.route("/acquire", methods=["POST"])
def acquire_lock():
    api_data = lockapi.current_request.json_body
    required_fields = ["ServiceName", "LockName", "LockTableName", "ServiceTableName"]
    check_fields(api_data, required_fields)

    service_name, lock_name, lock_table_name, service_table_name = (
        api_data["ServiceName"],
        api_data["LockName"],
        api_data["LockTableName"],
        api_data["ServiceTableName"],
    )

    client = SingletonDynamoDBClient.getInstance()
    date_time = str(datetime.utcnow())
    job_id = str(uuid.uuid4())

    try:
        # If either service_resp, or response fails, will trigger exception
        service_resp = client.transact_get_items(
            TransactItems=[
                {
                    "Get": {
                        "TableName": service_table_name,
                        "Key": {"ServiceName": {"S": service_name}},
                    }
                }
            ]
        )
        # In case service doesn't exist
        if service_resp["Responses"] == [{}]:
            raise ValidationException("Service doesn't exist")
        response = client.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": lock_table_name,
                        "Key": {"LockName": {"S": lock_name}},
                        "UpdateExpression": "SET HeldBy = :held_by, Lock_Acquire_DateTime = :date_time, JobId = :job_id",
                        "ExpressionAttributeValues": {
                            ":held_by": {"S": service_name},
                            ":empty_string": {"S": ""},
                            ":date_time": {"S": date_time},
                            ":job_id": {"S": job_id},
                        },
                        "ConditionExpression": "HeldBy = :empty_string AND JobId = :empty_string",
                    }
                }
            ]
        )
        response["ResponseMetadata"]["JobId"] = job_id
        response["ResponseMetadata"][
            "Message"
        ] = "%s acquired the following lock: %s" % (service_name, lock_name)

        return response
    except ValidationException as e:
        logger.debug(str(e))
        return Response(
            body={"Message": str(e)},
            status_code=400,
            headers={"Content-Type": "application/json"},
        )
    except ClientError as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unable to acquire a lock"},
            status_code=409,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unexpected exception occurred during the request"},
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


def retrieve_tables_values(lock_name, lock_table_name):
    """Retrieves values from the lock table."""

    client = SingletonDynamoDBClient.getInstance()
    response = client.transact_get_items(
        TransactItems=[
            {
                "Get": {
                    "TableName": lock_table_name,
                    "Key": {"LockName": {"S": lock_name}},
                }
            }
        ]
    )

    return response["Responses"]


def dictify_resp(list_of_dict_item):
    """Converts a list of DynamoDB response dictionaries into a simpler key-value dictionary."""

    ret_dict = {}
    for dict_item in list_of_dict_item:
        dict_item = dict_item.get("Item", {})
        for k, v in dict_item.items():
            for vk, vv in v.items():
                ret_dict[k] = vv
    return ret_dict


@lockapi.route("/release", methods=["POST"])
def release_lock():
    api_data = lockapi.current_request.json_body
    required_fields = [
        "LockName",
        "ServiceName",
        "JobId",
        "LockTableName",
        "LogTableName",
    ]
    check_fields(api_data, required_fields)

    service_name, lock_name, job_id, lock_table_name, log_table_name = (
        api_data["ServiceName"],
        api_data["LockName"],
        api_data["JobId"],
        api_data["LockTableName"],
        api_data["LogTableName"],
    )

    client = SingletonDynamoDBClient.getInstance()

    try:

        # Put relevant Row information into dict. This is for logging purposes
        read_resp = retrieve_tables_values(lock_name, lock_table_name)
        row_dict = dictify_resp(read_resp)

        date_time = str(datetime.utcnow())

        response = client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": log_table_name,
                        "Item": {
                            "LockName": {"S": lock_name},
                            "ServiceName": {"S": service_name},
                            "JobId": {"S": job_id},
                            "Lock_Acquire_DateTime": {
                                "S": row_dict.get("Lock_Acquire_DateTime", "")
                            },
                            "Lock_Release_DateTime": {"S": date_time},
                        },
                    }
                },
                {
                    "Update": {
                        "TableName": lock_table_name,
                        "Key": {"LockName": {"S": lock_name}},
                        "UpdateExpression": "SET HeldBy = :empty_string, JobId = :empty_string",
                        "ExpressionAttributeValues": {
                            ":held_by": {"S": service_name},
                            ":empty_string": {"S": ""},
                            ":job_id": {"S": job_id},
                        },
                        "ConditionExpression": "HeldBy = :held_by AND JobId = :job_id",
                    }
                },
            ]
        )

        response["ResponseMetadata"]["Message"] = (
            "%s released the following lock: %s with JobId: %s"
            % (service_name, lock_name, job_id)
        )
        return response

    except ClientError as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unable to release lock"},
            status_code=409,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.debug(str(e))
        return Response(
            body={"Mesage": "Unexpected exception occurred during the request"},
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


@lockapi.route("/register_lock", methods=["POST"])
def register_lock():
    api_data = lockapi.current_request.json_body
    required_fields = ["LockName", "LockTableName"]
    check_fields(api_data, required_fields)

    lock_name, lock_table_name = (api_data["LockName"], api_data["LockTableName"])

    client = SingletonDynamoDBClient.getInstance()

    try:
        date_time = str(datetime.utcnow())

        response = client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": lock_table_name,
                        "Item": {
                            "LockName": {"S": lock_name},
                            "HeldBy": {"S": ""},
                            "Lock_Acquire_DateTime": {"S": date_time},
                            "JobId": {"S": ""},
                        },
                        "ConditionExpression": "attribute_not_exists(LockName)",
                    }
                }
            ]
        )
        response["ResponseMetadata"]["Message"] = "Registered Lock: %s" % lock_name

        return response
    except ClientError as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unable to register a lock"},
            status_code=409,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unexpected exception occurred during the request"},
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


@lockapi.route("/deregister_lock", methods=["POST"])
def deregister_lock():
    api_data = lockapi.current_request.json_body
    required_fields = ["LockName", "LockTableName"]
    check_fields(api_data, required_fields)

    lock_name, lock_table_name = (api_data["LockName"], api_data["LockTableName"])

    client = SingletonDynamoDBClient.getInstance()

    try:
        response = client.transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": lock_table_name,
                        "Key": {"LockName": {"S": lock_name}},
                        "ExpressionAttributeValues": {":empty_string": {"S": ""}},
                        "ConditionExpression": "HeldBy = :empty_string AND JobId = :empty_string",
                    }
                }
            ]
        )
        response["ResponseMetadata"]["Message"] = "Deregistered Lock: %s" % lock_name

        return response
    except ClientError as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unable to deregister a lock"},
            status_code=409,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unexpected exception occurred during the request"},
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


@lockapi.route("/register_service", methods=["POST"])
def register_service():
    api_data = lockapi.current_request.json_body
    required_fields = ["ServiceName", "ServiceTableName"]
    check_fields(api_data, required_fields)

    service_name, service_table_name = (
        api_data["ServiceName"],
        api_data["ServiceTableName"],
    )

    client = SingletonDynamoDBClient.getInstance()

    try:

        response = client.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": service_table_name,
                        "Item": {"ServiceName": {"S": service_name},},
                        "ConditionExpression": "attribute_not_exists(ServiceName)",
                    }
                }
            ]
        )
        response["ResponseMetadata"]["Message"] = (
            "Registered Service: %s" % service_name
        )

        return response
    except ClientError as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unable to register a service"},
            status_code=409,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unexpected exception occurred during the request"},
            status_code=500,
            headers={"Content-Type": "application/json"},
        )


@lockapi.route("/deregister_service", methods=["POST"])
def deregister_service():
    api_data = lockapi.current_request.json_body
    required_fields = ["ServiceName", "ServiceTableName"]
    check_fields(api_data, required_fields)

    service_name, service_table_name = (
        api_data["ServiceName"],
        api_data["ServiceTableName"],
    )

    client = SingletonDynamoDBClient.getInstance()

    try:
        response = client.transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": service_table_name,
                        "Key": {"ServiceName": {"S": service_name}},
                        "ExpressionAttributeValues": {
                            ":service_name": {"S": service_name}
                        },
                        "ConditionExpression": "ServiceName = :service_name",
                    }
                }
            ]
        )
        response["ResponseMetadata"]["Message"] = (
            "Deregistered Service: %s" % service_name
        )
        return response
    except ClientError as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unable to deregister a service"},
            status_code=409,
            headers={"Content-Type": "application/json"},
        )
    except Exception as e:
        logger.debug(str(e))
        return Response(
            body={"Message": "Unexpected exception occurred during the request"},
            status_code=500,
            headers={"Content-Type": "application/json"},
        )

