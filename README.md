# FMBench Orchestrator

![fmbench_architecture](docs/img/Fmbench-Orchestrator-Architecture-v1.png)

## Overview

The **FMBench Orchestrator** is a tool designed to automate the deployment and management of `FMBench` for benchmarking on Amazon EC2, Amazon SageMaker and Amazon Bedrock. In case of benchmarking on EC2, we could benchmark on multiple instances simultaneously, and these instances can be of different instance types (so you could run `g6e`, `p4de` and a `trn1` instances via the same config file), in different AWS regions and also test multiple `FMBench` config files. This orchestrator automates the creation of Security Groups, Key Pairs, EC2 instances, runs `FMBench` for a specific config, retrieves the results, and shuts down the instances after completion. Thus it **simplifies the benchmarking process (no more manual creation of SageMaker Notebooks, EC2 instances and cleanup, downloading results folder) and ensures a streamlined and scalable workflow**.

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

1. **Activate the Environment**:

    ```bash
    conda activate fmbench-orchestrator-py311
    ```

1. **Install Required Packages**:

    ```bash
    pip install -r requirements.txt
    ```

1. **Hugging Face token**:

   Most models and tokenizers are downloaded from Hugging Face, to enable this place your Hugging Face token in `/tmp/hf_token.txt`.

   ```bash
   # replace with your Hugging Face token
   hf_token=your-hugging-face-token
   echo $hf_token > /tmp/hf_token.txt
   ```

### Steps to run the orchestrator:

You can either use an existing config file included in this repo, such as [`configs/ec2.yml`](configs/ec2.yml) or create your own using the files provided in the [`configs`](configs) directory as a template. Make sure you are in the `fmbench-orchestrator-py311` conda environment. The following command runs benchmarking for the `Llama3-8b` model on an `g6e.2xlarge` and `g6e.4xlarge` instance types.

```bash
python main.py --config-file configs/ec2.yml
```

Here is a description of all the command line parameters that are supported by the orchestrator:

- **--config-file** - _required_, path to the orchestrator configuration file.
- **--ami-mapping-file** - _optional_, _default=ami_mapping.yml_, path to a config file containing the region->instance type->AMI mapping
- **--fmbench-config-file** - _optional_, config file to use with `FMBench`, this is used if the orchestrator config file uses the "{{config_file}}" format for specifying the `FMBench` config file. If you are benchmarking on SageMaker or Bedrock then parameter does need to be specified.
- **--infra-config-file** - _optional_, _default=infra.yml_, config file to use with AWS infrastructure
- **--write-bucket** - _optional_, _default=placeholder_, *this parameter is only needed when benchmarking on SageMaker*, Amazon S3 bucket to store model files for benchmarking on SageMaker

Once the run is completed you can see the `FMBench` results folder downloaded in the `results` directory under the orchestrator, the `fmbench.log` file is also downloaded from the EC2 instances and placed alongside the results folder.

To analyze the results i.e. compare and contrast the price performance of different EC2 instance types that were a part of the run by running an analytics script. The example below shows how to use the `analytcs.py` script to analyze results obtained from running the orchestrator with the [`llama3-8b-g6e-triton.yml`](configs/llama3/8b/llama3-8b-triton-g6e.yml) config file.

```{.bashrc}
python analytics/analytics.py --results-dir results/llama3-8b-g6e-triton --model-id llama3-8b --payload-file payload_en_3000-3840.jsonl --latency-threshold 2
```

Running the scripts above creates a `results` folder under `analytics` which contains summaries of the results and a heatmap that helps understand which instance type gives the best price performance at the desired scale (transactions/minute) while maintaining the inference latency below a desired threshold.

## How do I ...

See [configuration guide](docs/config_guide.md) for details on the orchestrator config file.

### Benchmark for EC2

Take an existing config file from the [`configs`](configs/) folder, create a copy and edit it as needed. You would typically only need to modify the `instances` section of the config file to either modify the instance type and config file or add additional types. For example the following command line benchmarks the `Llama3.1-8b` models on `g6e` EC2 instance types.

```bash
python main.py --config-file configs/ec2.yml
```

## Benchmark for SageMaker

You can benchmark any model(s) on Amazon SageMaker by simply pointing the orchestrator to the desired `FMBench` SageMaker config file. The orchestrator will create an EC2 instance and use that for running `FMBench` benchmarking for SageMaker. For example the following command line benchmarks the `Llama3.1-8b` models on `ml.g5` instance types on SageMaker.

```bash
# provide the name of an S3 bucket in which you want
# SageMaker to store the model files (for models downloaded
# from Hugging Face)
write_bucket=your-bucket-name
python main.py --config-file configs/sagemaker.yml --fmbench-config-file fmbench:llama3.1/8b/config-llama3.1-8b-g5.yml --write-bucket $write_bucket
```

## Benchmark for Bedrock

You can benchmark any model(s) on Amazon Bedrock by simply pointing the orchestrator to the desired `FMBench` SageMaker config file. The orchestrator will create an EC2 instance and use that for running `FMBench` benchmarking for Bedrock.  For example the following command line benchmarks the `Llama3.1` models on Bedrock.

```bash
python main.py --config-file configs/bedrock.yml --fmbench-config-file fmbench:bedrock/config-bedrock-llama3-1-no-streaming.yml
```

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

The `instances` section has an `upload_files` section for each instance where we can provide a list of `local` files and `remote` directory paths to place any custom file on an EC2 instance. This could be a `tokenizer.json` file, a custom prompt file, or a custom dataset. The example below shows how to upload a custom `pricing.yml` and a custom dataset to an EC2 instance.

```{.bashrc}
instances:
- instance_type: g6e.2xlarge
  <<: *ec2_settings
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


