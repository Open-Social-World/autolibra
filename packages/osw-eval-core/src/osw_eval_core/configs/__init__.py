from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class OSWEvalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    azure_api_key: str
    azure_endpoint: str
    github_personal_access_token: str
    azure_openai_4o_model: str | None = Field(default=None)
    azure_openai_o1_model: str | None = Field(default=None)
    azure_openai_o3_model: str | None = Field(default=None)
