"""Configuration settings for the Network Simulator backend application.

Uses Pydantic Settings to manage base paths, project name, and directory creation.
"""

import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application-wide settings managed through environment variables or defaults."""

    PROJECT_NAME: str = "Network Simulator"
    API_V1_STR: str = "/api/v1"
    
    # Base paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_DIR: str = os.path.join(BASE_DIR, "configs")
    TEMPLATE_DIR: str = os.path.join(BASE_DIR, "templates")

    class Config:
        """Pydantic configuration options for the Settings model."""

        case_sensitive = True

settings = Settings()

# Ensure directories exist
os.makedirs(settings.CONFIG_DIR, exist_ok=True)
os.makedirs(settings.TEMPLATE_DIR, exist_ok=True)
