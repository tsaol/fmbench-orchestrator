# FMBench Orchestrator

![fmbench_architecture](docs/img/Fmbench-Orchestrator-Architecture-v1.png)

## Overview

The **FMBench Orchestrator** is a tool designed to automate the deployment and management of `FMBench` on multiple Amazon EC2 instances in AWS. The multiple instances can be of different instance types (so you could run `g6e`, `p4de` and a `trn1` instances via the same config file), in different AWS regions and also test multiple `FMBench` config files. This orchestrator automates the creation of Security Groups, Key Pairs, EC2 instances, runs `FMBench` for a specific config, retrieves the results, and shuts down the instances after completion. Thus it **simplifies the benchmarking process (no more manual instance creation and cleanup, downloading results folder) and ensures a streamlined and scalable workflow**.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Conda Environment Setup](#conda-environment-setup)
4. [Configuration](#configuration)
5. [Usage](#usage)
6. [Workflow](#workflow)
7. [Cleaning Up](#cleaning-up)
8. [Contributing](#contributing)
9. [License](#license)

## Prerequisites

- **IAM ROLE**: You need an active AWS account having an **IAM Role** necessary permissions to create, manage, and terminate EC2 instances. See [this](docs/iam.md) link for the permissions and trust policies that this IAM role needs to have. Call this IAM role as `fmbench-orchestrator`.

    
- **Service quota**: Your AWS account needs to have appropriately set service quota limits to be able to start the Amazon EC2 instances that you may want to use for benchmarking. This may require you to submit service quota increase requests, use [this link](https://docs.aws.amazon.com/servicequotas/latest/userguide/request-quota-increase.html) for submitting a service quota increase requests. This would usually mean increasing the CPU limits for your accounts, getting quota for certain instance types etc.

- **EC2 Instance**: It is recommended to run the orchestrator on an EC2 instance, attaching the IAM Role with permissions, preferably located in the same AWS region where you plan to launch the multiple EC2 instances (although launching instances across regions is supported as well).

    - Use `Ubuntu` as the instance OS, specifically the `ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-20240927` AMI.
    - Use `t3.xlarge` as the instance type with preferably at least 100GB of disk space.
    - Associate the `fmbench-orchestrator` IAM role with this instance.

## Installation

1. **Install `conda`**

    ```{.bash}
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash Miniconda3-latest-Linux-x86_64.sh -b  # Run the Miniconda installer in batch mode (no manual intervention)
    rm -f Miniconda3-latest-Linux-x86_64.sh    # Remove the installer script after installation
    eval "$(/home/$USER/miniconda3/bin/conda shell.bash hook)" # Initialize conda for bash shell
    conda init  # Initialize conda, adding it to the shell
    ```

1. **Clone the Repository**

    ```bash
    git clone https://github.com/awslabs/fmbench-orchestrator.git
    cd fmbench-orchestrator
    ```

### Conda Environment Setup

1. **Create a Conda Environment with Python 3.11**:

    ```bash
    conda create --name fmbench-orchestrator-py311 python=3.11 -y
    ```

2. **Activate the Environment**:

    ```bash
    conda activate fmbench-orchestrator-py311
    ```

3. **Install Required Packages**:

    ```bash
    pip install -r requirements.txt
    ```

### Steps to run the orchestrator:

You can either use an existing config file included in this repo, such as [`configs/config.yml`](configs/config.yml) or create your own using the files provided in the [`configs`](configs) directory as a template. Make sure you are in the `fmbench-orchestrator-py311` conda environment.

```bash
python main.py -f configs/config.yml
```

Once the run is completed you can analyze the results i.e. compare and contrast the price performance of different EC2 instance types that were a part of the run by running an analytics script. The example below shows how to use the `analytcs.py` script to analyze results obtained from running the orchestrator with the [`llama3-8b-g6e-triton.yml`](configs/llama3/8b/llama3-8b-triton-g6e.yml) config file.

```{.bashrc}
python analytics/analytics.py --results-dir results/llama3-8b-g6e-triton --model-id llama3-8b --payload-file payload_en_3000-3840.jsonl --latency-threshold 2
```

Running the scripts above creates a `results` folder under `analytics` which contains summaries of the results and a heatmap that helps understand which instance type gives the best price performance at the desired scale (transactions/minute) while maintaining the inference latency below a desired threshold.

## `FMBench` orchestrator configuration guide

### Overview
This configuration file is used to manage the deployment and orchestration of multiple EC2 instances for running `FMBench` benchmarks. The file defines various parameters, including AWS settings, run steps, security group settings, key pair management, and instance-specific configurations. This guide explains the purpose of each section and provides details on how to customize the file according to your requirements.

### Configuration Sections

#### AWS Settings

This section contains the basic settings required to interact with AWS services.

- `region`: Unless you want to specify a region explicitly, this is always set to `{{region}}` which gets replaced with the current region of the EC2 VM on which the orchestrator is being run. The `region` parameter can also be specified with each instance in the `instances` section, if specified in the `instances` section then that value would override the value in this section. This allows for launching instances in a region different from the region in which the orchestrator is running.
- `hf_token_fpath`: Your Hugging Face token for accessing specific resources or APIs. Always set to `/tmp/hf_token.txt` unless you want to store the token in a different path.

#### Run Steps

Defines the various steps in the orchestration process. Set each step to `yes` or `no` based on whether you want that step to be executed.

- `security_group_creation`: Whether to create a new security group for the EC2 instances. Set to `yes` to create a new security group or `no` to use an existing one.
- `key_pair_generation`: Whether to generate a new key pair for accessing the EC2 instances. If set to `no`, ensure you have an existing key pair available.
- `deploy_ec2_instance`: Whether to deploy the EC2 instances as specified in the `instances` section.
- `run_bash_script`: Whether to run a startup script on each EC2 instance after deployment.
- `delete_ec2_instance`: Whether to terminate the EC2 instances after completing the benchmarks.

#### Security Group

This section configures the security group settings for the EC2 instances. You would typically not need to change anything in this section from what is specified in the [default config file](configs/config.yml).

- `group_name`: Name of the security group to be created or used. If a group with this name already exists, it will be used.
- `description`: A brief description of the security group, such as "MultiDeploy EC2 Security Group."
- `vpc_id`: The VPC ID where the security group will be created. Leave this blank to use the default VPC.

#### Key Pair Management

Manages the SSH key pair used for accessing the EC2 instances. You would typically not need to change anything in this section from what is specified in the [default config file](configs/config.yml).

- `key_pair_name`: Name of the key pair to be created or used. If `key_pair_generation` is set to `no`, ensure this matches the name of an existing key pair.
- `key_pair_fpath`: The file path where the key pair file (`.pem`) will be stored locally. Update this path if you have an existing key pair.

#### Instances

Defines the EC2 instances to be launched for running the benchmarks. This section can contain multiple instance configurations.

- `instance_type`: The type of EC2 instance to be launched (e.g., `g5.2xlarge`). Choose based on your resource requirements.
- `deploy`: (_Optional_, default: `yes`) set to `yes` if you want to run benchmarking on this instance, `no` otherwise (comes in handy if you want to skip a particular instance from the run but do not want to remove it from the config file).
- `ami_id`: Set to one of `{{gpu}}`, `{{cpu}}`, or `{{neuron}}` depending upon instance type. The orchestrator code replaces it with the actual ami id based on the region and whether it is a `gpu`, `cpu` or `neuron` instance.
- `startup_script`: Path to the startup script that will be executed when the instance is launched. This script should be stored in the `startup_scripts` directory.
- `post_startup_script`: Path to a script that will be executed after the initial startup script. Use this for any additional configuration or benchmark execution commands.
- `fmbench_config`: URL or file path to the `FMBench` configuration file that will be used by the orchestrator. If specifying a config file from the `FMBench` GitHub repo you can simply say (for example) `fmbench:llama3.1/70b/config-ec2-llama3-1-70b-p4de.24xl-deploy-ec2-longbench.yml` which will be translated into `https://raw.githubusercontent.com/aws-samples/foundation-model-benchmarking-tool/refs/heads/main/src/fmbench/configs/llama3.1/70b/config-ec2-llama3-1-70b-p4de.24xl-deploy-ec2-longbench.yml` by the orchestrator code.

- `upload_files`: this is a list of `local` and `remote` entries where any file on the orchestrator machine can be uploaded to a remote path into the instance. This can be used for uploading a custom prompt, a custom tokenizer, a custom pricing file etc. In the example below we are uploading a custom dataset and a custom prompt template from the local (orchestrator) machine to the remote machine.
    ```
    upload_files:
    - local: byo_dataset/synthetic_data_large_prompts.jsonl
      remote: /tmp/fmbench-read/source_data
    - local: byo_dataset/prompt_template_llama3_summarization.txt
      remote: /tmp/fmbench-read/prompt_template/prompt_template_llama3_summarization.txt
    ```


#### Sample instance configuration

The following is an example configuration for deploying a `g6e.2xlarge` instance with GPU AMI (Ubuntu Deep Learning OSS) and startup scripts:

```yaml
instances:
- instance_type: g6e.2xlarge
  region: {{region}}
  ami_id: {{gpu}}
  device_name: /dev/sda1
  ebs_del_on_termination: True
  ebs_Iops: 16000
  ebs_VolumeSize: 250
  ebs_VolumeType: gp3
  startup_script: startup_scripts/ubuntu_startup.txt
  post_startup_script: post_startup_scripts/fmbench.txt
  # Timeout period in Seconds before a run is stopped
  fmbench_complete_timeout: 2400
  fmbench_config: 
  - fmbench:llama3/8b/config-ec2-llama3-8b-g6e-2xlarge.yml
  upload_files:
  - local: byo_dataset/custom.jsonl
    remote: /tmp
  - local: analytics/pricing.yml
    remote: /tmp
```

### Workflow

```
+---------------------+       +------------------------+       +------------------------+       +---------------------+       +-----------------------+
| Initialization      |  →    | Instance Creation      |  →    | FMBENCH Execution      |  →    | Results Collection  |  →    | Instance Termination  |
| (Configure & Setup) |       | (Launch EC2 Instances) |       | (Run Benchmark Script) |       | (Upload to S3)      |       | (Shut Down Instances) |
+---------------------+       +------------------------+       +------------------------+       +---------------------+       +-----------------------+

```


1. **Initialization**: Reads the configuration file and initializes the necessary AWS resources.
2. **Instance Creation**: Launches the specified number of EC2 instances with the provided configuration.
3. **FMBENCH Execution**: Runs the FMBENCH benchmark script on each instance.
4. **Results Collection**: Collects the results from each instance and uploads them to the specified S3 bucket.
5. **Instance Termination**: Terminates all instances to prevent unnecessary costs.

### Cleaning Up

Cleanup is done automatically. But if you select **no** in config, you would have to manually terminate the instances from EC2 console.


## Contributing
Contributions are welcome! Please fork the repository and submit a pull request with your changes. For major changes, please open an issue first to discuss what you would like to change.


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the MIT-0 License - see the [LICENSE](LICENSE) file for details.


