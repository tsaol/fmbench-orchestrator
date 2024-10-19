# IAM role for FMBench orchestrator

Here are the permissions and trust policies that the IAM role assigned to the Amazon EC2 machines used by the FMBench orchestrator needs to have. This role is used both for the driver node i.e. the machine on which the orchestrator is installed and the individual EC2 VMs created by the driver node on which the FMBench benchmarking runs.


1. Permissions

    ```{.bash}
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ecr:GetAuthorizationToken",
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchGetImage",
                    "ecr:ListImages"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:RunInstances",
                    "ec2:DescribeInstances",
                    "ec2:CreateTags",
                    "ec2:StartInstances",
                    "ec2:StopInstances",
                    "ec2:RebootInstances"
                ],
                "Resource": [
                    "arn:aws:ec2:*:*:instance/*",
                    "arn:aws:ec2:*:*:volume/*",
                    "arn:aws:ec2:*:*:network-interface/*",
                    "arn:aws:ec2:*:*:key-pair/*",
                    "arn:aws:ec2:*:*:security-group/*",
                    "arn:aws:ec2:*:*:subnet/*",
                    "arn:aws:ec2:*:*:image/*",
                    "arn:aws:ec2:*:*:capacity-reservation/*"
                ]
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:CreateSecurityGroup",
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:AuthorizeSecurityGroupEgress",
                    "ec2:DescribeSecurityGroups"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:CreateKeyPair",
                    "ec2:DescribeKeyPairs"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:CreateTags",
                    "ec2:DescribeInstances",
                    "ec2:TerminateInstances",
                    "ec2:DescribeInstanceStatus",
                    "ec2:DescribeAddresses",
                    "ec2:AssociateAddress",
                    "ec2:DisassociateAddress",
                    "ec2:DescribeRegions",
                    "ec2:DescribeImages",
                    "ec2:DescribeAvailabilityZones"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": "iam:PassRole",
                "Resource": [
                    "arn:aws:iam::*:role/fmbench*"
                ]
            }
        ]
    }
    ```

1. Trust policies

    ```{.bash}
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "ec2.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }
    ```
