import os
import boto3
import requests
import logging
from constants import *
from utils import create_security_group, load_yaml_file
from utils import authorize_inbound_rules, create_key_pair
from botocore.exceptions import NoCredentialsError, ClientError

logger = logging.getLogger(name=__name__)

config_data = load_yaml_file(yaml_file_path)

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


def get_sg_id(region):
    # Append the region to the group name
    GROUP_NAME = f"{config_data['security_group'].get('group_name')}-{region}"
    DESCRIPTION = config_data["security_group"].get("description", " ")
    VPC_ID = config_data["security_group"].get("vpc_id")
    
    try:
        # Create or get the security group with the region-specific name
        sg_id = create_security_group(GROUP_NAME, DESCRIPTION, VPC_ID, region)
        logger.info(f"Security group '{GROUP_NAME}' created or imported in {region}")

        if sg_id:
            # Add inbound rules if security group was created or imported successfully
            authorize_inbound_rules(sg_id, region)
            logger.info(f"Inbound rules added to security group '{GROUP_NAME}'")
        
        return sg_id
    
    except ClientError as e:
        logger.error(f"An error occurred while creating or getting the security group '{GROUP_NAME}': {e}")
        raise  # Re-raise the exception for further handling if needed




def get_key_pair(region):
    # Create 'key_pair' directory if it doesn't exist
    key_pair_dir = "key_pair"
    if not os.path.exists(key_pair_dir):
        os.makedirs(key_pair_dir)

    # Generate the key pair name using the format: config_name-region
    config_name = config_data["key_pair_gen"]["key_pair_name"]
    key_pair_name = f"{config_name}-{region}"  # Create the key pair name as config_name-region
    private_key_fname = os.path.join(key_pair_dir, f"{key_pair_name}.pem")  # Ensure .pem is added once

    # Check if key pair generation is enabled
    if config_data["run_steps"]["key_pair_generation"]:
        # First, check if the key pair file already exists
        if os.path.exists(private_key_fname):
            try:
                # If the key pair file exists, read it
                with open(private_key_fname, "r") as file:
                    private_key = file.read()
                print(f"Using existing key pair from {private_key_fname}")
            except IOError as e:
                raise ValueError(f"Error reading existing key pair file '{private_key_fname}': {e}")
        else:
            # If the key pair file doesn't exist, create a new key pair
            try:
                private_key = create_key_pair(key_pair_name, region)
                # Save the key pair to the file
                with open(private_key_fname, "w") as key_file:
                    key_file.write(private_key)
                
                # Set file permissions to be readable only by the owner
                os.chmod(private_key_fname, 0o400)
                print(f"Key pair '{key_pair_name}' created and saved as '{private_key_fname}'")
            except Exception as e:
                # If key pair creation fails, raise an error
                raise ValueError(f"Failed to create key pair '{key_pair_name}': {e}")
    else:
        # If key pair generation is disabled, attempt to use an existing key
        try:
            with open(private_key_fname, "r") as file:
                private_key = file.read()
            print(f"Using pre-existing key pair from {private_key_fname}")
        except FileNotFoundError:
            raise ValueError(f"Key pair file not found at {private_key_fname}")
        except IOError as e:
            raise ValueError(f"Error reading key pair file '{private_key_fname}': {e}")

    return private_key_fname, key_pair_name

