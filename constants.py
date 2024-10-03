remote_script_path = "/home/ubuntu/run_fmbench.sh"
yaml_file_path = "config.yml"

# Define a dictionary for common AMIs and their corresponding usernames
AMI_USERNAME_MAP = {
    "ami-": "ec2-user",  # Amazon Linux AMIs start with 'ami-'
    "ubuntu": "ubuntu",  # Ubuntu AMIs contain 'ubuntu' in their name
}

AMI_NAME_MAP = {
    "gpu": "Deep Learning OSS Nvidia Driver AMI GPU PyTorch 2.4 (Ubuntu 22.04)",
    "neuron": "Deep Learning AMI Neuron (Ubuntu 22.04)",
    "cpu": "Amazon Linux 2 AMI (HVM) - Kernel 5.10, SSD Volume Type",
}
