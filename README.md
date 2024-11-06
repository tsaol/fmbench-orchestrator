# FMBench Orchestrator

![fmbench_architecture](docs/img/Fmbench-Orchestrator-Architecture-v1.png)

## Overview

The **FMBench Orchestrator** is a tool designed to automate the deployment and management of `FMBench` on multiple Amazon EC2 instances in AWS. The multiple instances can be of different instance types (so you could run `g6e`, `p4de` and a `trn1` instances via the same config file), in different AWS regions and also test multiple `FMBench` config files. This orchestrator automates the creation of Security Groups, Key Pairs, EC2 instances, runs `FMBench` for a specific config, retrieves the results, and shuts down the instances after completion. Thus it **simplifies the benchmarking process (no more manual instance creation and cleanup, downloading results folder) and ensures a streamlined and scalable workflow**.

```
+---------------------------+
| Initialization            |
| (Configure & Setup)       |
+---------------------------+
          ↓
+---------------------------+
| Instance Creation         |
| (Launch EC2 Instances)    |
+---------------------------+
          ↓
+---------------------------+
| FMBENCH Execution         |
| (Run Benchmark Script)    |
+---------------------------+
          ↓
+---------------------------+
| Results Collection        |
| (Download from instances) |
+---------------------------+
          ↓
+---------------------------+
| Instance Termination      |
| (Terminate Instances)     |
+---------------------------+
```

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
python main.py --config-file configs/config.yml
```

Once the run is completed you can see the `FMBench` results folder downloaded in the `results` directory under the orchestrator, the `fmbench.log` file is also downloaded from the EC2 instances and placed alongside the results folder.

To analyze the results i.e. compare and contrast the price performance of different EC2 instance types that were a part of the run by running an analytics script. The example below shows how to use the `analytcs.py` script to analyze results obtained from running the orchestrator with the [`llama3-8b-g6e-triton.yml`](configs/llama3/8b/llama3-8b-triton-g6e.yml) config file.

```{.bashrc}
python analytics/analytics.py --results-dir results/llama3-8b-g6e-triton --model-id llama3-8b --payload-file payload_en_3000-3840.jsonl --latency-threshold 2
```

Running the scripts above creates a `results` folder under `analytics` which contains summaries of the results and a heatmap that helps understand which instance type gives the best price performance at the desired scale (transactions/minute) while maintaining the inference latency below a desired threshold.

## How do I ...

See [configuration guide](docs/config_guide.md) for details on the orchestrator config file.

### Benchmark for my instance types and serving containers of interest

Take an existing config file from the [`configs`](configs/) folder, create a copy and edit it as needed. You would typically only need to modify the `instances` section of the config file.

### Use an existing `FMBench` config file but modify it slightly for my requirements

1. Download an `FMBench` config file from the [`FMBench repo`](https://github.com/aws-samples/foundation-model-benchmarking-tool/tree/main/src/fmbench/configs) and place it in the [`configs/fmbench`](./configs/fmbench/) folder.
1. Modify the downloaded config as needed.
1. Update the `instance -> fmench_config` section for the instance that needs to use this file to point to the updated config file in `fmbench/configs` so for example if the updated config file was `config-ec2-llama3-8b-g6e-2xlarge-custom.yml` then the following parameter:

    ```{.bashrc}
    fmbench_config: 
    - fmbench:llama3/8b/config-ec2-llama3-8b-g6e-2xlarge.yml
    ```
      would be changed to:

    ```{.bashrc}
    fmbench_config: 
    - configs/fmbench/config-ec2-llama3-8b-g6e-2xlarge-custom.yml
    ```

    The orchestrator would now upload the custom config on the EC2 instance being used for benchmarking.

### Provide a custom prompt/custom tokenizer for my benchmarking test

The `instances` section has an `upload_files` section for each instance where we can provide a list of `local` files and `remote` directory paths to place any custom file on an EC2 instance. This could be a tokenizer.json file, a custom prompt file, or a custom dataset. The example below shows how to upload a custom `pricing.yml` and a custom dataset to an EC2 instance.

```{.bashrc}
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
     remote: /tmp/fmbench-read/source_data/
   - local: analytics/pricing.yml
     remote: /tmp/fmbench-read/configs/
```

### Benchmark multiple config files on the same EC2 instance

Often times we want to benchmark different combinations of parameters on the same EC2 instance, for example we may want to test tensor parallelism degree of 2, 4 and 8 for say `Llama3.1-8b` model on the same EC2 machine say `g6e.48xlarge`. Can do that easily with the orchestrator by specifying a list of config files rather than just a single config file as shown in the following example:

   ```{.bashrc}
  fmbench_config: 
  - fmbench:llama3.1/8b/config-llama3.1-8b-g6e.48xl-tp-2-mc-max-djl.yml
  - fmbench:llama3.1/8b/config-llama3.1-8b-g6e.48xl-tp-4-mc-max-djl.yml
  - fmbench:llama3.1/8b/config-llama3.1-8b-g6e.48xl-tp-8-mc-max-djl.yml
  ```
The orchestrator would in this case first run benchmarking for the first file in the list, and then on the same EC2 instance run benchmarking for the second file and so on and so forth. The results folders and `fmbench.log` files for each of the runs is downloaded at the end when all config files for that instance have been processed.

## Contributing
Contributions are welcome! Please fork the repository and submit a pull request with your changes. For major changes, please open an issue first to discuss what you would like to change.


## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This project is licensed under the MIT-0 License - see the [LICENSE](LICENSE) file for details.


