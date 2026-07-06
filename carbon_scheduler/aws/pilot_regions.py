"""
Maps the scheduler's demo region names to real AWS region codes and their
Electricity Maps zone codes, for the live one-week pilot.

Note: af-south-1 (Cape Town) is an AWS "opt-in" region - it must be
enabled manually in Account > AWS Regions before instances can be
launched there. If you haven't enabled it, the pilot will skip it and
note it as excluded rather than fail the whole run.
"""

# app region name -> (aws_region_code, electricity_maps_zone)
PILOT_REGIONS = {
    "us-east-1 (N. Virginia)":     ("us-east-1", "US-MIDA-PJM"),
    "eu-west-1 (Ireland)":         ("eu-west-1", "IE"),
    "ap-south-1 (Mumbai)":         ("ap-south-1", "IN-WE"),
    "sa-east-1 (Sao Paulo)":       ("sa-east-1", "BR"),
    "ca-central-1 (Canada)":       ("ca-central-1", "CA-QC"),
    "af-south-1 (Cape Town)":      ("af-south-1", "ZA"),       # opt-in region
    "eu-central-1 (Frankfurt)":    ("eu-central-1", "DE"),
    "us-west-2 (Oregon)":          ("us-west-2", "US-NW-PACW"),
    "ap-southeast-2 (Sydney)":     ("ap-southeast-2", "AU-NSW"),
    "eu-north-1 (Sweden)":         ("eu-north-1", "SE"),
    "ap-southeast-1 (Singapore)":  ("ap-southeast-1", "SG"),
    "ap-northeast-1 (Tokyo)":      ("ap-northeast-1", "JP"),
    "us-east-2 (Ohio)":            ("us-east-2", "US-MIDW-MISO"),
}

OPT_IN_REGIONS = {"af-south-1"}

INSTANCE_TYPE = "t3.micro"
SECURITY_GROUP_NAME = "carbon-pilot-sg"
TAG_KEY = "Project"
TAG_VALUE = "carbon-aware-pilot"
