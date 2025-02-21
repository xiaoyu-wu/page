import boto3
from botocore.config import Config

retry_config = Config(
    retries={
        "max_attempts": 5,
        "mode": "adaptive",
    }
)

CLIENT = boto3.client("bedrock-runtime", region_name="us-west-2", config=retry_config)
MODEL_ID = "anthropic.claude-3-5-sonnet-20241022-v2:0"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TEMPERATURE = 0.3
DEFAULT_TOP_P = 0.9

UNDERSTANDING_ERROR = "Error: Unable to understand the bill."
