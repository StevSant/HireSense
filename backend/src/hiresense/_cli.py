import uvicorn
from dotenv import load_dotenv


def main() -> None:
    # Populate os.environ from .env before uvicorn forks its reload subprocess.
    # pydantic-settings only reads .env into Settings; libraries that consult
    # os.environ directly (e.g. huggingface_hub for HF_HUB_OFFLINE) need this.
    load_dotenv()

    # Dev-only entrypoint (`uv run app`); production runs the Dockerfile CMD
    # (uvicorn --host 0.0.0.0 --port 8000), so reload stays on here. The bind
    # port is read from config (APP_PORT) rather than a hardcoded literal.
    from hiresense.config import Settings

    settings = Settings()
    uvicorn.run(
        "hiresense.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=settings.app_port,
        reload=True,
    )
