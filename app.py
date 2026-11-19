import os
import boto3
from dotenv import load_dotenv

load_dotenv()

session = boto3.Session(
    region_name=os.getenv("AWS_REGION", "ap-south-1")
)

sts = session.client("sts")

identity = sts.get_caller_identity()

print("AWS connection successful")
print("Account:", identity["Account"])
print("Identity:", identity["Arn"])