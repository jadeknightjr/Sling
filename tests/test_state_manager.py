from unittest import mock

from Sling.chalicelib.state_manager import (
    state_manager_acquire,
    state_manager_release,
)


@mock.patch("requests.post")
def test_state_manager_acquire(mocked_request):
    # Test parameters are correct
    resp = state_manager_acquire(
        "https://api_route.execute-api.us-west-2.amazonaws.com/api/",
        "unheld_service",
        "unheld_lock",
        "LockTable",
        "RegisteredServices",
    )
    params = {
        "LockName": "unheld_lock",
        "ServiceName": "unheld_service",
        "LockTableName": "LockTable",
        "ServiceTableName": "RegisteredServices",
    }
    mocked_request.assert_called_once_with(
        url="https://api_route.execute-api.us-west-2.amazonaws.com/api/acquire",
        json=params,
    )


@mock.patch("requests.post")
def test_state_manager_release(mocked_request):
    # Test parameters are correct
    resp = state_manager_release(
        "https://api_route.execute-api.us-west-2.amazonaws.com/api/",
        "unheld_service",
        "unheld_lock",
        "001",
        "LockTable",
        "LogTable",
    )
    params = {
        "LockName": "unheld_lock",
        "ServiceName": "unheld_service",
        "JobId": "001",
        "LockTableName": "LockTable",
        "LogTableName": "LogTable",
    }
    mocked_request.assert_called_once_with(
        url="https://api_route.execute-api.us-west-2.amazonaws.com/api/release",
        json=params,
    )
