
# `FMBench` orchestrator configuration guide

## Overview
This configuration file is used to manage the deployment and orchestration of multiple EC2 instances for running `FMBench` benchmarks. The file defines various parameters, including AWS settings, run steps, security group settings, key pair management, and instance-specific configurations. This guide explains the purpose of each section and provides details on how to customize the file according to your requirements.

## Configuration Sections

### AWS Settings

This section contains the basic settings required to interact with AWS services.

- `region`: Unless you want to specify a region explicitly, this is always set to `{{region}}` which gets replaced with the current region of the EC2 VM on which the orchestrator is being run. The `region` parameter can also be specified with each instance in the `instances` section, if specified in the `instances` section then that value would override the value in this section. This allows for launching instances in a region different from the region in which the orchestrator is running.
- `hf_token_fpath`: Your Hugging Face token for accessing specific resources or APIs. Always set to `/tmp/hf_token.txt` unless you want to store the token in a different path.

### Run Steps

Defines the various steps in the orchestration process. Set each step to `yes` or `no` based on whether you want that step to be executed.

- `security_group_creation`: Whether to create a new security group for the EC2 instances. Set to `yes` to create a new security group or `no` to use an existing one.
- `key_pair_generation`: Whether to generate a new key pair for accessing the EC2 instances. If set to `no`, ensure you have an existing key pair available.
- `deploy_ec2_instance`: Whether to deploy the EC2 instances as specified in the `instances` section.
- `run_bash_script`: Whether to run a startup script on each EC2 instance after deployment.
- `delete_ec2_instance`: Whether to terminate the EC2 instances after completing the benchmarks.

### Security Group

This section configures the security group settings for the EC2 instances. You would typically not need to change anything in this section from what is specified in the [default config file](configs/config.yml).

- `group_name`: Name of the security group to be created or used. If a group with this name already exists, it will be used.
- `description`: A brief description of the security group, such as "MultiDeploy EC2 Security Group."
- `vpc_id`: The VPC ID where the security group will be created. Leave this blank to use the default VPC.

### Key Pair Management

Manages the SSH key pair used for accessing the EC2 instances. You would typically not need to change anything in this section from what is specified in the [default config file](configs/config.yml).

- `key_pair_name`: Name of the key pair to be created or used. If `key_pair_generation` is set to `no`, ensure this matches the name of an existing key pair.
- `key_pair_fpath`: The file path where the key pair file (`.pem`) will be stored locally. Update this path if you have an existing key pair.

### Instances

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


### Sample instance configuration

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

## Cleaning Up

Cleanup is done automatically. But if you select **no** in config, you would have to manually terminate the instances from EC2 console.
