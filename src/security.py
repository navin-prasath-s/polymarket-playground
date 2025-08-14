import os

from dotenv import load_dotenv

from fastapi import Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

load_dotenv()
L1_KEY = os.getenv("L1_KEY", "abc")
L2_KEY = os.getenv("L2_KEY", "def")


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(
    key: str = Security(api_key_header)
):
    if key == L2_KEY:
        return "L2"
    if key == L1_KEY:
        return "L1"
    raise HTTPException(403, "Invalid API Key")

def require_l1(api_level=Depends(get_api_key)):
    if api_level not in ("L1","L2"):
        raise HTTPException(403, "L1 or higher required")
def require_l2(api_level=Depends(get_api_key)):
    if api_level != "L2":
        raise HTTPException(403, "L2 required")