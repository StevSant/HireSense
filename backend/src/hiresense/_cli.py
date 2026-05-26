import uvicorn
from dotenv import load_dotenv


def main() -> None:
    # Populate os.environ from .env before uvicorn forks its reload subprocess.
    # pydantic-settings only reads .env into Settings; libraries that consult
    # os.environ directly (e.g. huggingface_hub for HF_HUB_OFFLINE) need this.
    load_dotenv()
    uvicorn.run(
        "hiresense.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
