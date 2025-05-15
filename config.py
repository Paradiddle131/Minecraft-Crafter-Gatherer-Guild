from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    google_api_key: str = "YOUR_GEMINI_API_KEY_DEFAULT_IF_NOT_IN_ENV"
    minecraft_host: str = "localhost"
    minecraft_port: int = 25565
    minecraft_bot_username: str = "ADK_Guild_Bot_Pydantic"
    minecraft_auth: str = "offline"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()