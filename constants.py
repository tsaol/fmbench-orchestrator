remote_script_path = "/home/ubuntu/run_fmbench.sh"
yaml_file_path = "config.yml"

# Define a dictionary for common AMIs and their corresponding usernames
AMI_USERNAME_MAP = {
    "ami-": "ec2-user",  # Amazon Linux AMIs start with 'ami-'
    "ubuntu": "ubuntu",  # Ubuntu AMIs contain 'ubuntu' in their name
}

bash_script = """echo {hf_token} > /tmp/fmbench-read/scripts/hf_token.txt
                cd /home/ubuntu/foundation-model-benchmarking-tool;
                source activate fmbench_python311;
                 . ~/.bashrc;
                if [[ "$CONDA_DEFAULT_ENV" == "fmbench_python311" ]]; then
                    echo "The current environment is fmbench_python311. Running FMBench..."
                    
                    # Run fmbench and redirect output to a log file
                    nohup fmbench --config-file {config_file} --local-mode yes --write-bucket placeholder --tmp-dir /tmp > fmbench.log 2>&1 &
                    FM_BENCH_PID=$!
                    echo "FMBench is running with PID $FM_BENCH_PID. Logs are being written to fmbench.log."
                    
                    # Wait for the fmbench process to complete
                    wait $FM_BENCH_PID
                    echo "FMBench execution completed."

                    # Check if any directory matching results-* exists
                    if ls results-* 1> /dev/null 2>&1; then
                        echo "Results directory found. Creating flag file in /tmp."
                        # Create a flag file in /tmp
                        touch /tmp/fmbench_completed.flag
                    else
                        echo "Results directory not found. No flag file created."
                    fi
                else
                    echo "Error: The current environment is not fmbench_python311. Exiting."
                    exit 1
                fi
                """
