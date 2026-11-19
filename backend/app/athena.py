import time
import boto3
from .config import env, int_env

def aws_session():
    profile = env("AWS_PROFILE")
    region = env("AWS_REGION", "ap-south-1")
    return boto3.Session(profile_name=profile, region_name=region) if profile else boto3.Session(region_name=region)

def run_query(sql: str) -> list[dict]:
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
