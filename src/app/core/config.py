import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Network Simulator"
    API_V1_STR: str = "/api/v1"
    
    # Base paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_DIR: str = os.path.join(BASE_DIR, "configs")
    TEMPLATE_DIR: str = os.path.join(BASE_DIR, "templates")

    class Config:
        case_sensitive = True

settings = Settings()

# Ensure directories exist
os.makedirs(settings.CONFIG_DIR, exist_ok=True)
os.makedirs(settings.TEMPLATE_DIR, exist_ok=True)
