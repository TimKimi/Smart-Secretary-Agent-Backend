from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    app_name: str = "SSA"
    debug: bool = False
    database_url: str = "sqlite:///ssa.db"


settings = Settings()
