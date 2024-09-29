import os
import boto3
import requests


def get_region():

    session = boto3.session.Session()
    region_name = session.region_name
    if region_name is None:
        print(
            f"boto3.session.Session().region_name is {region_name}, "
            f"going to use an metadata api to determine region name"
        )
        # THIS CODE ASSUMED WE ARE RUNNING ON EC2, for everything else
        # the boto3 session should be sufficient to retrieve region name
        resp = requests.put(
            "http://169.254.169.254/latest/api/token",
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        )
        token = resp.text
        region_name = requests.get(
            "http://169.254.169.254/latest/meta-data/placement/region",
            headers={"X-aws-ec2-metadata-token": token},
        ).text
        print(f"region_name={region_name}, also setting the AWS_DEFAULT_REGION env var")
        os.environ["AWS_DEFAULT_REGION"] = region_name
    print(f"region_name={region_name}")

    return region_name


def get_iam_role():

    caller = boto3.client("sts").get_caller_identity()
    account_id = caller.get("Account")
    role_arn_from_env = os.environ.get("FMBENCH_ROLE_ARN")
    if role_arn_from_env:
        print(f"role_arn_from_env={role_arn_from_env}, using it to set arn_string")
        arn_string = role_arn_from_env
    else:
        print(
            f"role_arn_from_env={role_arn_from_env}, using current sts caller identity to set arn_string"
        )
        arn_string = caller.get("Arn")
        # if this is an assumed role then remove the assumed role related pieces
        # because we are also using this role for deploying the SageMaker endpoint
        # arn:aws:sts::015469603702:assumed-role/SSMDefaultRoleForOneClickPvreReporting/i-0c5bba16a8b3dac51
        # should be converted to arn:aws:iam::015469603702:role/SSMDefaultRoleForOneClickPvreReporting
        if ":assumed-role/" in arn_string:
            role_name = arn_string.split("/")[-2]
            arn_string = f"arn:aws:iam::{account_id}:instance-profile/{role_name}"
            print(
                f"the sts role is an assumed role, setting arn_string to {arn_string}"
            )
        else:
            arn_string = caller.get("Arn")

    ROLE_NAME = arn_string.split("/")[-1]

    return ROLE_NAME
