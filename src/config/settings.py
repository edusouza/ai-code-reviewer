from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    app_name: str = "AI Code Reviewer"
    debug: bool = False
    version: str = "1.0.0"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    
    # Google Cloud
    project_id: str = ""
    firestore_database: str = "(default)"
    pubsub_topic: str = "code-reviews"
    
    # GitHub
    github_webhook_secret: str = ""
    github_app_id: Optional[str] = None
    github_private_key: Optional[str] = None
    
    # GitLab
    gitlab_webhook_secret: str = ""
    gitlab_token: Optional[str] = None
    
    # Bitbucket
    bitbucket_webhook_secret: str = ""
    bitbucket_username: Optional[str] = None
    bitbucket_app_password: Optional[str] = None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
