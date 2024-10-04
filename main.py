import os
import time
import json
import wget
import yaml
import boto3
import base64
import urllib
import logging
import asyncio
import paramiko
from utils import *
from constants import *
from scp import SCPClient
from typing import Optional, List
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import NoCredentialsError, ClientError
from globals import (
    create_iam_instance_profile_arn,
    get_region,
    get_iam_role,
    get_sg_id,
    get_key_pair,
)


executor = ThreadPoolExecutor()

# Initialize global variables for this file
instance_id_list: List = []
fmbench_config_map: List = []
fmbench_post_startup_script_map: List = []
instance_data_map: Dict = {}

logging.basicConfig(
    level=logging.INFO,  # Set the log level to INFO
    # Define log message format
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("fmbench-Orchestrator.log"),  # Log to a file
        logging.StreamHandler(),  # Also log to console
    ],
)


async def execute_fmbench(instance, formatted_script, remote_script_path):
    """
    Asynchronous wrapper for deploying an instance using synchronous functions.
    """
    # Check for the startup completion flag

    startup_complete = await asyncio.get_event_loop().run_in_executor(
        executor, wait_for_flag, instance, 600, 30, STARTUP_COMPLETE_FLAG_FPATH
    )

    if startup_complete:
        # Handle configuration file (download/upload) and get the remote path
        remote_config_path = await handle_config_file_async(instance)
        # Format the script with the remote config file path
        # Change this later to be a better implementation, right now it is bad.
        formatted_script = formatted_script.format(config_file=remote_config_path)
        print("Startup Script complete, executing fmbench now")

        if instance["fmbench_llm_config_fpath"]:
            logger.info("Going to use custom tokenizer and config")
            await upload_config_and_tokenizer(
                instance["hostname"],
                instance["username"],
                instance["key_file_path"],
                instance["fmbench_llm_config_fpath"],
                instance["fmbench_llm_tokenizer_fpath"],
                instance["fmbench_tokenizer_remote_dir"],
            )

        # Upload and execute the script on the instance
        script_output = await asyncio.get_event_loop().run_in_executor(
            executor,
            upload_and_execute_script_invoke_shell,
            instance["hostname"],
            instance["username"],
            instance["key_file_path"],
            formatted_script,
            remote_script_path,
        )
        print(f"Script Output from {instance['hostname']}:\n{script_output}")

        # Check for the fmbench completion flag
        fmbench_complete = await asyncio.get_event_loop().run_in_executor(
            executor,
            wait_for_flag,
            instance,
            instance["fmbench_complete_timeout"],
            30,
            FMBENCH_TEST_COMPLETE_FLAG_FPATH,
        )

        if fmbench_complete:
            print("Fmbench Run successful, Getting the folders now")
            await asyncio.get_event_loop().run_in_executor(
                executor, check_and_retrieve_results_folder, instance, "output"
            )
            if config_data["run_steps"]["delete_ec2_instance"]:
                delete_ec2_instance(instance["instance_id"], instance["region"])
                instance_id_list.remove(instance["instance_id"])


async def multi_deploy_fmbench(instance_details, remote_script_path):
    tasks = []

    # Create a task for each instance
    for instance in instance_details:
        # Make this async as well?
        # Format the script with the specific config file
        logger.info(f"Instance Details are: {instance}")
        logger.info(
            f"Attempting to open bash script at {instance['post_startup_script']}"
        )
        with open(instance["post_startup_script"]) as file:
            bash_script = file.read()

        logger.info("Read Bash Script")
        logger.info(f"Post startup script is: {bash_script}")

        # Create an async task for this instance
        tasks.append(execute_fmbench(instance, bash_script, remote_script_path))

    # Run all tasks concurrently
    await asyncio.gather(*tasks)


async def main():
    await multi_deploy_fmbench(instance_details, remote_script_path)


logger = logging.getLogger(name=__name__)

if __name__ == "__main__":
    config_data = load_yaml_file(YAML_FILE_PATH)
    logger.info(f"Loaded Config {config_data}")

    hf_token_fpath = config_data["aws"].get("hf_token_fpath")
    hf_token: Optional[str] = None
    logger.info(f"Got Hugging Face Token file path from config. {hf_token_fpath}")
    logger.info("Attempting to open it")

    with open(hf_token_fpath) as file:
        hf_token = file.read()
    if hf_token is None:
        logger.error(f"No HF token found in {hf_token_fpath}")
    else:
        logger.info(f"HF token found and loaded from {hf_token_fpath}")

    logger.info(f"read hugging face token {hf_token} from file path")
    assert len(hf_token) > 4, "Hf_token is too small or invalid, please check"

    for i in config_data["instances"]:
        logger.info(f"Instance list is as follows: {i}")

    logger.info(f"Deploying Ec2 Instances")
    if config_data["run_steps"]["deploy_ec2_instance"]:

        if config_data["run_steps"]['create_iam_role']:
            try:
                iam_arn = create_iam_instance_profile_arn()
            except Exception as e:
                logger.error(f"Cannot create IAM Role due to exception {e}")
                logger.info("Going to get iam role from the current instance")
                iam_arn = get_iam_role()
        
        else:
            try:
                iam_arn = get_iam_role()
            except Exception as e:
                logger.error(f"Cannot get IAM Role due to exception {e}")

        if not iam_arn:
            raise NoCredentialsError("""Unable to locate credentials,
                                        Please check if an IAM role is 
                                        attched to your instance.""")
        
        logger.info(f"iam arn: {iam_arn}")
        # WIP Parallelize This.
        for instance in config_data["instances"]:
            region = instance["region"]
            startup_script = instance["startup_script"]
            logger.info(f"Region Set for instance is: {region}")
            if config_data["run_steps"]["security_group_creation"]:
                logger.info(
                    f"Creating Security Groups. getting them by name if they exist"
                )
                sg_id = get_sg_id(region)
            PRIVATE_KEY_FNAME, PRIVATE_KEY_NAME = get_key_pair(region)
            # command_to_run = instance["command_to_run"]
            with open(f"{startup_script}", "r") as file:
                user_data_script = file.read()
                # Replace the hf token in the bash script to pull the HF model
                user_data_script = user_data_script.replace("__HF_TOKEN__", hf_token)
            if instance.get("instance_id") is None:
                instance_type = instance["instance_type"]
                ami_id = instance["ami_id"]
                device_name = instance["device_name"]
                ebs_del_on_termination = instance["ebs_del_on_termination"]
                ebs_Iops = instance["ebs_Iops"]
                ebs_VolumeSize = instance["ebs_VolumeSize"]
                ebs_VolumeType = instance["ebs_VolumeType"]
                # Retrieve CapacityReservationId and CapacityReservationResourceGroupArn if they exist
                CapacityReservationId = instance.get("CapacityReservationId", None)
                CapacityReservationPreference = instance.get(
                    "CapacityReservationPreference", "none"
                )
                CapacityReservationResourceGroupArn = instance.get(
                    "CapacityReservationResourceGroupArn", None
                )

                # Initialize CapacityReservationTarget only if either CapacityReservationId or CapacityReservationResourceGroupArn is provided
                CapacityReservationTarget = {}
                if CapacityReservationId:
                    CapacityReservationTarget["CapacityReservationId"] = (
                        CapacityReservationId
                    )
                if CapacityReservationResourceGroupArn:
                    CapacityReservationTarget["CapacityReservationResourceGroupArn"] = (
                        CapacityReservationResourceGroupArn
                    )

                # If CapacityReservationTarget is empty, set it to None
                if not CapacityReservationTarget:
                    CapacityReservationTarget = None

                # user_data_script += command_to_run
                # Create an EC2 instance with the user data script
                instance_id = create_ec2_instance(
                    PRIVATE_KEY_NAME,
                    sg_id,
                    user_data_script,
                    ami_id,
                    instance_type,
                    iam_arn,
                    region,
                    device_name,
                    ebs_del_on_termination,
                    ebs_Iops,
                    ebs_VolumeSize,
                    ebs_VolumeType,
                    CapacityReservationPreference,
                    CapacityReservationTarget)
                instance_id_list.append(instance_id)
                instance_data_map[instance_id] = {

                "fmbench_config": instance["fmbench_config"],

                    "post_startup_script": instance["post_startup_script"],
                    "fmbench_llm_tokenizer_fpath": instance.get(
                        "fmbench_llm_tokenizer_fpath"
                    ),
                    "fmbench_llm_config_fpath": instance.get(
                        "fmbench_llm_config_fpath"
                    ),
                    "fmbench_tokenizer_remote_dir": instance.get(
                        "fmbench_tokenizer_remote_dir"
                    ),
                    "fmbench_complete_timeout": instance["fmbench_complete_timeout"],
                    "region": instance["region"],
                    "PRIVATE_KEY_FNAME": PRIVATE_KEY_FNAME,
                }
            if instance.get("instance_id") is not None:
                instance_id = instance["instance_id"]
                # TODO: Check if host machine can open the private key provided, if it cant, raise exception
                PRIVATE_KEY_FNAME = instance["private_key_fname"]
                if not PRIVATE_KEY_FNAME:
                    logger.error(
                        "Private key not found, not adding instance to instance id list"
                    )
                if PRIVATE_KEY_FNAME:
                    instance_id_list.append(instance_id)
                    instance_data_map[instance_id] = {

                "fmbench_config": instance["fmbench_config"],

                    "post_startup_script": instance["post_startup_script"],
                    "fmbench_llm_tokenizer_fpath": instance.get(
                        "fmbench_llm_tokenizer_fpath"
                    ),
                    "fmbench_llm_config_fpath": instance.get(
                        "fmbench_llm_config_fpath"
                    ),
                    "fmbench_tokenizer_remote_dir": instance.get(
                        "fmbench_tokenizer_remote_dir"
                    ),
                    "fmbench_complete_timeout": instance["fmbench_complete_timeout"],
                    "region": instance["region"],
                    "PRIVATE_KEY_FNAME": PRIVATE_KEY_FNAME,
                }

    logger.info("Going to Sleep for 60 seconds to make sure the instances are up")
    time.sleep(60)

    if config_data["run_steps"]["run_bash_script"]:
        instance_details = generate_instance_details(
            instance_id_list, instance_data_map
        )  # Call the async function
        asyncio.run(main())
