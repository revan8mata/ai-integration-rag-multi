from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel


class Settings(BaseSettings):
    api_key:str
    openai_api_key: str
    anthropic_api_key: str
    database_hostname :str
    database_port :str
    database_password :str
    database_name : str
    database_username : str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()





