"""
Credential resolver shared by the pilot runners and teardown.

On the laptop, dispatch authenticates via a named CLI profile (aws-arima /
aws-lstm / aws-adaptive) from ~/.aws/credentials. On the cloud orchestrator
EC2 there are no named profiles - the box authenticates via its IAM instance
role - so a named-profile lookup raises ProfileNotFound. This helper tries the
named profile first and transparently falls back to the default credential
chain (which resolves the instance role on EC2), so the exact same runner code
works in both places with no static keys on the box.
"""
import boto3
from botocore.exceptions import ProfileNotFound


def get_session(profile_name: str = None):
    """Return a boto3 Session for `profile_name`, or the default-chain session
    (instance role on EC2) if that profile isn't configured. Returns None only
    if even the default chain has no credentials."""
    if profile_name:
        try:
            return boto3.Session(profile_name=profile_name)
        except ProfileNotFound:
            pass
    try:
        sess = boto3.Session()
        if sess.get_credentials() is not None:
            return sess
    except Exception:
        pass
    return None
