from pydantic_settings import BaseSettings, SettingsConfigDict


class OSWEvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    azure_api_key: str
    azure_endpoint: str
    github_personal_access_token: str
