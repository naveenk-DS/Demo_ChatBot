import time
import boto3
from .config import env, int_env, bool_env

def is_athena_enabled() -> bool:
    """Checks whether Athena queries are explicitly enabled via feature flag."""
    return bool_env("ENABLE_ATHENA", False)

def aws_session():
    profile = env("AWS_PROFILE")
    region = env("AWS_REGION", "ap-south-1")
    # Avoid placeholder profiles
    if profile and profile not in ("your-aws-profile-name", "realestate-demo"):
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)

def run_query(sql: str) -> list[dict]:
    """
    Executes SQL query against Athena.
    Disabled by default via ENABLE_ATHENA=false to prevent unwanted Athena permissions/costs.
    """
    if not is_athena_enabled():
        return []

    database, output = env("ATHENA_DATABASE"), env("ATHENA_OUTPUT_LOCATION")
    if not database or not output.startswith("s3://"):
        raise RuntimeError("Configure ATHENA_DATABASE and ATHENA_OUTPUT_LOCATION.")
    client = aws_session().client("athena")
    started = client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": output},
        WorkGroup=env("ATHENA_WORKGROUP", "primary"),
    )
    qid = started["QueryExecutionId"]
    deadline = time.time() + int_env("ATHENA_QUERY_TIMEOUT_SECONDS", 45)
    while time.time() < deadline:
        status = client.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        state = status["State"]
        if state == "SUCCEEDED": break
        if state in ("FAILED", "CANCELLED"):
            raise RuntimeError(status.get("StateChangeReason", f"Athena query {state}"))
        time.sleep(1)
    else:
        client.stop_query_execution(QueryExecutionId=qid)
        raise TimeoutError("Athena query timed out.")
    result = client.get_query_results(QueryExecutionId=qid, MaxResults=100)["ResultSet"]["Rows"]
    if not result: return []
    headers = [c.get("VarCharValue", "") for c in result[0]["Data"]]
    records = []
    for row in result[1:]:
        vals = [c.get("VarCharValue") for c in row.get("Data", [])]
        vals += [None] * (len(headers) - len(vals))
        records.append(dict(zip(headers, vals)))
    return records
