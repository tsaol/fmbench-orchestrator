remote_script_path = "/home/ubuntu/run_fmbench.sh"
yaml_file_path = "config.yml"

# Define a dictionary for common AMIs and their corresponding usernames
AMI_USERNAME_MAP = {
    "ami-": "ec2-user",  # Amazon Linux AMIs start with 'ami-'
    "ubuntu": "ubuntu",  # Ubuntu AMIs contain 'ubuntu' in their name
}


