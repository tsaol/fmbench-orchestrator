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
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import NoCredentialsError, ClientError

executor = ThreadPoolExecutor()


# Define a dictionary for common AMIs and their corresponding usernames
AMI_USERNAME_MAP = {
    "ami-": "ec2-user",  # Amazon Linux AMIs start with 'ami-'
    "ubuntu": "ubuntu",  # Ubuntu AMIs contain 'ubuntu' in their name
}


def get_security_group_id_by_name(group_name, vpc_id, region="us-east-1"):
    """
    Retrieve the security group ID based on its name and VPC ID.

    Args:
        sg_name (str): The name of the security group.
        vpc_id (str): The ID of the VPC where the security group is located.
        region (str): The AWS region.

    Returns:
        str: The security group ID if found, None otherwise.
    """
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        response = ec2_client.describe_security_groups(
            Filters=[
                {"Name": "group-name", "Values": [group_name]},
            ]
        )
        # If security group exists, return the ID
        if response["SecurityGroups"]:
            return response["SecurityGroups"][0]["GroupId"]
        else:
            print(f"Security group '{group_name}' not found in VPC '{vpc_id}'.")
            return None

    except ClientError as e:
        print(f"Error retrieving security group: {e}")
        return None


def create_security_group(group_name, description, vpc_id=None, region="us-east-1"):
    """
    Create an EC2 security group.

    Args:
        group_name (str): Name of the security group.
        description (str): Description of the security group.
        vpc_id (str, optional): ID of the VPC in which to create the security group. If None, it will be created in the default VPC.
        region (str): AWS region where the security group will be created.

    Returns:
        str: ID of the created security group.
    """
    # Initialize the EC2 client
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        # Define parameters for creating the security group
        params = {
            "GroupName": group_name,
            "Description": description,
        }

        # Only add the VpcId parameter if vpc_id is not None
        if vpc_id is not None:
            params["VpcId"] = vpc_id

        # Create the security group
        response = ec2_client.create_security_group(**params)

        security_group_id = response["GroupId"]
        print(f"Security Group Created: {security_group_id}")

        return security_group_id

    except ClientError as e:
        # Check if the error is due to the group already existing
        if e.response["Error"]["Code"] == "InvalidGroup.Duplicate":
            print(
                f"Security Group '{group_name}' already exists. Fetching existing security group ID."
            )
            return get_security_group_id_by_name(group_name, vpc_id, region)
        else:
            print(f"Error creating security group: {e}")
            return None


def authorize_inbound_rules(security_group_id, region="us-east-1"):
    """
    Authorize inbound rules to a security group.

    Args:
        security_group_id (str): ID of the security group.
        region (str): AWS region where the security group is located.
    """
    # Initialize the EC2 client
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        # Authorize inbound rules
        ec2_client.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],  # Allow SSH from anywhere
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0"}],  # Allow HTTP from anywhere
                },
            ],
        )
        print(f"Inbound rules added to Security Group {security_group_id}")

    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidPermission.Duplicate":
            print(
                f"Inbound rule already exists for Security Group {security_group_id}. Skipping..."
            )
        else:
            print(f"Error authorizing inbound rules: {e}")


def create_key_pair(key_name, region="us-east-1"):
    """
    Create a new key pair for EC2 instances.

    Args:
        key_name (str): The name of the key pair.
        region (str): AWS region where the key pair will be created.

    Returns:
        str: The private key material in PEM format.
    """
    # Initialize the EC2 client
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        # Create a key pair
        response = ec2_client.create_key_pair(KeyName=key_name)

        # Extract the private key from the response
        private_key = response["KeyMaterial"]

        # Save the private key to a .pem file
        with open(f"{key_name}.pem", "w") as key_file:
            key_file.write(private_key)

        # Set the correct permissions for the .pem file
        import os

        os.chmod(f"{key_name}.pem", 0o400)  # Readable only by the owner

        print(f"Key pair '{key_name}' created and saved as '{key_name}.pem'")
        return private_key

    except ClientError as e:
        print(f"Error creating key pair: {e}")
        return None


def create_ec2_instance(
    key_name,
    security_group_id,
    user_data_script,
    ami,
    instance_type,
    iam_arn,
    region="us-east-1",
):
    """
    Create an EC2 instance with a startup script (user data) in the specified region.

    Args:
        key_name (str): The name of the key pair to associate with the instance.
        security_group_id (str): The ID of the security group to associate with the instance.
        user_data_script (str): The script to run on startup.
        region (str): The AWS region to launch the instance in.

    Returns:
        str: The ID of the created instance.
    """
    # Initialize a session using Amazon EC2
    ec2_resource = boto3.resource("ec2", region_name="us-east-1")

    try:
        # Create a new EC2 instance with user data
        instances = ec2_resource.create_instances(
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "DeleteOnTermination": True,
                        "Iops": 16000,
                        "VolumeSize": 250,
                        "VolumeType": "gp3",
                    },
                },
            ],
            ImageId=ami,
            InstanceType=instance_type,  # Instance type
            KeyName=key_name,  # Name of the key pair
            SecurityGroupIds=[security_group_id],  # Security group ID
            UserData=user_data_script,  # The user data script to run on startup
            MinCount=1,  # Minimum number of instances to launch
            MaxCount=1,  # Maximum number of instances to launch
            IamInstanceProfile={  # IAM role to associate with the instance
                "Arn": iam_arn
            },
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": "FMbench-EC2"}],
                }
            ],
        )

        # Get the instance ID of the created instance
        instance_id = instances[0].id
        print(f"EC2 Instance '{instance_id}' created successfully with user data.")

        return instance_id

    except ClientError as e:
        print(f"Error creating EC2 instance: {e}")
        return None


def delete_ec2_instance(instance_id, region="us-east-1"):
    """
    Deletes an EC2 instance given its instance ID.

    Args:
        instance_id (str): The ID of the instance to delete.
        region (str): The AWS region where the instance is located.

    Returns:
        bool: True if the instance was deleted successfully, False otherwise.
    """
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        # Terminate the EC2 instance
        response = ec2_client.terminate_instances(InstanceIds=[instance_id])
        print(f"Instance {instance_id} has been terminated.")
        return True
    except ClientError as e:
        print(f"Error deleting instance {instance_id}: {e}")
        return False


def get_ec2_hostname_and_username(instance_id, region="us-east-1", public_dns=True):
    """
    Retrieve the public or private DNS name (hostname) and username of an EC2 instance.

    Args:
        instance_id (str): The ID of the EC2 instance.
        region (str): The AWS region where the instance is located.
        public_dns (bool): If True, returns the public DNS; if False, returns the private DNS.

    Returns:
        tuple: A tuple containing the hostname (public or private DNS) and username.
    """
    ec2_client = boto3.client("ec2", region_name=region)

    try:
        # Describe the instance
        response = ec2_client.describe_instances(InstanceIds=[instance_id])

        # Extract instance information
        instance = response["Reservations"][0]["Instances"][0]
        ami_id = instance.get("ImageId")  # Get the AMI ID used to launch the instance

        # Check if the public DNS or private DNS is required
        if public_dns:
            hostname = instance.get("PublicDnsName")
        else:
            hostname = instance.get("PrivateDnsName")

        # Determine the username based on the AMI ID
        username = determine_username(ami_id)

        # Return the hostname and username if available
        if hostname and username:
            return hostname, username
        else:
            print(
                f"No {'public' if public_dns else 'private'} DNS or username found for instance {instance_id}"
            )
            return None, None

    except ClientError as e:
        print(f"Error fetching instance details: {e}")
        return None, None


def determine_username(ami_id):
    """
    Determine the appropriate username based on the AMI ID or name.

    Args:
        ami_id (str): The ID of the AMI used to launch the EC2 instance.

    Returns:
        str: The username for the EC2 instance.
    """
    ec2_client = boto3.client("ec2")

    try:
        # Describe the AMI to get its name
        response = ec2_client.describe_images(ImageIds=[ami_id])
        ami_name = response["Images"][0][
            "Name"
        ].lower()  # Convert AMI name to lowercase

        # Match the AMI name to determine the username
        for key in AMI_USERNAME_MAP:
            if key in ami_name:
                return AMI_USERNAME_MAP[key]

        # Default username if no match is found
        return "ec2-user"

    except ClientError as e:
        print(f"Error fetching AMI details: {e}")
        return "ec2-user"


# Function to check for 'results-*' folders in the root directory of an EC2 instance
def check_for_results_folder(
    hostname,
    username,
    key_file_path,
    folder_pattern="/home/ubuntu/foundation-model-benchmarking-tool/results-*",
):
    """
    Checks if any folder matching the pattern exists in the root directory.

    Args:
        hostname (str): The public IP or DNS of the EC2 instance.
        username (str): The SSH username (e.g., 'ec2-user').
        key_file_path (str): The path to the PEM key file.
        folder_pattern (str): The pattern to match folders (default is '/results-*').

    Returns:
        list: List of matching folder names, or an empty list if none found.
    """
    try:
        # Initialize the SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load the private key
        private_key = paramiko.RSAKey.from_private_key_file(key_file_path)

        # Connect to the instance
        ssh_client.connect(hostname, username=username, pkey=private_key)
        print(f"Connected to {hostname} as {username}")

        # Execute the command to check for folders matching the pattern
        command = f"ls -d {folder_pattern}"
        stdin, stdout, stderr = ssh_client.exec_command(command)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()

        # Close the connection
        ssh_client.close()

        if error:
            # No folder found or other errors
            print(f"No matching folders found on {hostname}: {error}")
            return []

        # Split the output by newline to get folder names
        folders = output.split("\n") if output else []
        return folders

    except Exception as e:
        print(f"Error connecting via SSH to {hostname}: {e}")
        return []


# Function to retrieve folders from the EC2 instance
def get_folder_from_instance(
    hostname, username, key_file_path, remote_folder, local_folder
):
    """
    Retrieves a folder from the EC2 instance to the local machine using SCP.

    Args:
        hostname (str): The public IP or DNS of the EC2 instance.
        username (str): The SSH username (e.g., 'ec2-user').
        key_file_path (str): The path to the PEM key file.
        remote_folder (str): The path of the folder on the EC2 instance to retrieve.
        local_folder (str): The local path where the folder should be saved.

    Returns:
        bool: True if the folder was retrieved successfully, False otherwise.
    """
    try:
        # Initialize the SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load the private key
        private_key = paramiko.RSAKey.from_private_key_file(key_file_path)

        # Connect to the instance
        ssh_client.connect(hostname, username=username, pkey=private_key)

        # Use SCP to copy the folder
        with SCPClient(ssh_client.get_transport()) as scp:
            scp.get(remote_folder, local_path=local_folder, recursive=True)

        print(f"Folder '{remote_folder}' retrieved successfully to '{local_folder}'.")

        # Close the connection
        ssh_client.close()

        return True

    except Exception as e:
        print(f"Error retrieving folder from {hostname} via SCP: {e}")
        return False


# Main function to check and retrieve 'results-*' folders from multiple instances
def check_and_retrieve_results_folder(instance, local_folder_base):
    """
    Checks for 'results-*' folders on a single EC2 instance and retrieves them if found.

    Args:
        instance (dict): Dictionary containing instance details (hostname, username, instance_id).
        key_file_path (str): The path to the PEM key file.
        local_folder_base (str): The local base path where the folders should be saved.

    Returns:
        None
    """
    hostname = instance["hostname"]
    username = instance["username"]
    key_file_path = instance["key_file_path"]

    # Check for 'results-*' folders in the specified directory
    results_folders = check_for_results_folder(hostname, username, key_file_path)

    # If any folders are found, retrieve them
    for folder in results_folders:
        if folder:  # Check if folder name is not empty
            # Create a local folder path for this instance
            local_folder = os.path.join(local_folder_base, os.path.basename(folder))
            os.makedirs(
                local_folder, exist_ok=True
            )  # Create local directory if it doesn't exist

            print(
                f"Retrieving folder '{folder}' from {hostname} to '{local_folder}'..."
            )
            get_folder_from_instance(
                hostname, username, key_file_path, folder, local_folder
            )


def generate_instance_details(
    instance_id_list, key_file_path, config_map, region="us-east-1"
):
    """
    Generates a list of instance details dictionaries containing hostname, username, and key file path.

    Args:
        instance_id_list (list): List of EC2 instance IDs.
        key_file_path (str): The path to the PEM key file.
        region (str): The AWS region where the instances are located.

    Returns:
        list: A list of dictionaries containing hostname, username, and key file path for each instance.
    """
    instance_details = []

    for instance_id in instance_id_list:
        config_entry = next((item for item in config_map if instance_id in item), None)

        # If a config entry is found, get the config path
        if config_entry:
            config_path = config_entry[instance_id]
        # Get the public hostname and username for each instance
        public_hostname, username = get_ec2_hostname_and_username(
            instance_id, region, public_dns=True
        )

        # Append the instance details to the list if hostname and username are found
        if public_hostname and username:
            instance_details.append(
                {
                    "hostname": public_hostname,
                    "username": username,
                    "key_file_path": key_file_path,
                    "config_file": config_path,
                }
            )
        else:
            print(
                f"Failed to retrieve hostname and username for instance {instance_id}"
            )

    return instance_details


def run_command_on_instances(instance_details, key_file_path, command):
    """
    Executes a command on multiple EC2 instances using the instance_details list.

    Args:
        instance_details (list): List of dictionaries containing instance details (hostname, username, key_file_path).
        command (str): The command to execute on each instance.

    Returns:
        dict: A dictionary containing the results of command execution for each instance.
              The key is the instance's hostname, and the value is a dictionary with 'stdout', 'stderr', and 'exit_status'.
    """
    results = {}

    for instance in instance_details:
        hostname = instance["hostname"]
        username = instance["username"]
        key_file_path = key_file_path

        print(f"Running command on {hostname} as {username}...")

        try:
            # Initialize the SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load the private key
            private_key = paramiko.RSAKey.from_private_key_file(key_file_path)

            # Connect to the instance
            ssh_client.connect(hostname, username=username, pkey=private_key)
            print(f"Connected to {hostname} as {username}")

            # Execute the command
            stdin, stdout, stderr = ssh_client.exec_command(command)

            # Wait for the command to complete
            exit_status = stdout.channel.recv_exit_status()

            # Read the outputs
            output = stdout.read().decode()
            error = stderr.read().decode()

            # Close the connection
            ssh_client.close()

            # Store the command result for this instance
            results[hostname] = {
                "stdout": output,
                "stderr": error,
                "exit_status": exit_status,
            }

        except Exception as e:
            print(f"Error connecting to {hostname} or executing command: {e}")
            results[hostname] = {"stdout": "", "stderr": str(e), "exit_status": -1}

    return results


def upload_and_execute_script_invoke_shell(
    hostname, username, key_file_path, script_content, remote_script_path
):
    """
    Uploads a bash script to the EC2 instance and executes it via an interactive SSH shell.

    Args:
        hostname (str): The public IP or DNS of the EC2 instance.
        username (str): The SSH username (e.g., 'ubuntu').
        key_file_path (str): The path to the PEM key file.
        script_content (str): The content of the bash script to upload.
        remote_script_path (str): The remote path where the script should be saved on the instance.

    Returns:
        str: The output of the executed script.
    """
    try:
        # Initialize the SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Load the private key
        private_key = paramiko.RSAKey.from_private_key_file(key_file_path)

        # Connect to the instance
        ssh_client.connect(hostname, username=username, pkey=private_key)
        print(f"Connected to {hostname} as {username}")

        # Open SFTP session to upload the script
        sftp = ssh_client.open_sftp()
        with sftp.open(remote_script_path, "w") as remote_file:
            remote_file.write(script_content)
        sftp.close()
        print(f"Script uploaded to {remote_script_path}")

        # Open an interactive shell session
        shell = ssh_client.invoke_shell()
        time.sleep(1)  # Give the shell some time to initialize

        # Send the commands to the shell
        shell.send(f"chmod +x {remote_script_path}\n")  # Make the script executable
        time.sleep(1)  # Wait for the command to complete

        # Execute the script
        shell.send(
            f"nohup bash {remote_script_path} > /home/ubuntu/run_fmbench_nohup.log 2>&1 & disown\n"
        )
        time.sleep(1)  # Wait for the command to complete

        # Read the output of the script
        output = ""
        while shell.recv_ready():
            output += shell.recv(1024).decode("utf-8")
            time.sleep(2)  # Allow time for the command output to be captured

        # Close the shell and connection
        shell.close()
        ssh_client.close()

        return output

    except Exception as e:
        print(f"Error connecting via SSH to {hostname}: {e}")
        return None


def is_url(path):
    """Checks if a given path is a URL."""
    parsed = urllib.parse.urlparse(path)
    return parsed.scheme in ("http", "https")


# Asynchronous function to download a configuration file if it is a URL
async def download_config_async(url, download_dir="downloaded_configs"):
    """Asynchronously downloads the configuration file from a URL."""
    os.makedirs(download_dir, exist_ok=True)
    local_path = os.path.join(download_dir, os.path.basename(url))
    # Run the blocking download operation in a separate thread
    await asyncio.get_event_loop().run_in_executor(
        executor, wget.download, url, local_path
    )
    return local_path


# Asynchronous function to upload a file to the EC2 instance
async def upload_file_to_instance_async(
    hostname, username, key_file_path, local_path, remote_path
):
    """Asynchronously uploads a file to the EC2 instance."""

    def upload_file():
        try:
            # Initialize the SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Load the private key
            private_key = paramiko.RSAKey.from_private_key_file(key_file_path)

            # Connect to the instance
            ssh_client.connect(hostname, username=username, pkey=private_key)
            print(f"Connected to {hostname} as {username}")

            # Upload the file
            with SCPClient(ssh_client.get_transport()) as scp:
                scp.put(local_path, remote_path)
                print(f"Uploaded {local_path} to {hostname}:{remote_path}")

            # Close the SSH connection
            ssh_client.close()
        except Exception as e:
            print(f"Error uploading file to {hostname}: {e}")

    # Run the blocking upload operation in a separate thread
    await asyncio.get_event_loop().run_in_executor(executor, upload_file)


# Asynchronous function to handle the configuration file
async def handle_config_file_async(instance):
    """Handles downloading and uploading of the config file based on the config type (URL or local path)."""
    config_path = instance["config_file"]

    # Check if the config path is a URL
    if is_url(config_path):
        print(f"Config is a URL. Downloading from {config_path}...")
        local_config_path = await download_config_async(config_path)
    else:
        # It's a local file path, use it directly
        local_config_path = config_path

    # Define the remote path for the configuration file on the EC2 instance
    remote_config_path = (
        f"/home/{instance['username']}/{os.path.basename(local_config_path)}"
    )

    # Upload the configuration file to the EC2 instance
    await upload_file_to_instance_async(
        instance["hostname"],
        instance["username"],
        instance["key_file_path"],
        local_config_path,
        remote_config_path,
    )

    return remote_config_path
