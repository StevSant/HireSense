from pydantic_settings import BaseSettings


class ApplicationsSettings(BaseSettings):
    """LaTeX compiler settings + generated-CV output directory."""

    # LaTeX
    latex_compiler: str = "xelatex"
    latex_timeout_seconds: float = 60.0
    cv_directory: str = "./cvs"
