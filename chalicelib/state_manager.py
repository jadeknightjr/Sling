import requests
from urllib.parse import urljoin

## Acquire Lock
def state_manager_acquire(
    api_url, service_name, lock_name, lock_table_name, service_table_name
):
    url = urljoin(api_url, "acquire")
    params = {
        "LockName": lock_name,
        "ServiceName": service_name,
        "LockTableName": lock_table_name,
        "ServiceTableName": service_table_name,
    }
    response = requests.post(url=url, json=params)

    return response


## Release Lock
def state_manager_release(
    api_url, service_name, lock_name, job_id, lock_table_name, log_table_name
):
    url = urljoin(api_url, "release")
    params = {
        "LockName": lock_name,
        "ServiceName": service_name,
        "JobId": job_id,
        "LockTableName": lock_table_name,
        "LogTableName": log_table_name,
    }
    response = requests.post(url=url, json=params)

    return response
