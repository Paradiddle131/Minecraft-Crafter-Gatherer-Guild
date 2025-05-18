from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional, Tuple, Any
import ast

class Settings(BaseSettings):
    google_api_key: str = "YOUR_GEMINI_API_KEY_DEFAULT_IF_NOT_IN_ENV"
    minecraft_host: str = "localhost"
    minecraft_port: int = 25565
    minecraft_bot_username: str = "ADK_Guild_Bot_Pydantic"
    minecraft_auth: str = "offline"
    minecraft_version: str = "1.21"
    gemini_model_name: str = "gemini-2.5-flash-preview-04-17"
    initial_teleport_coords: Optional[Tuple[int, int, int]] = None

    @field_validator("initial_teleport_coords", mode="before")
    @classmethod
    def parse_initial_teleport_coords(cls, value: Any) -> Optional[Tuple[int, int, int]]:
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                parsed_value = ast.literal_eval(value)
                if isinstance(parsed_value, tuple) and len(parsed_value) == 3 and all(isinstance(i, int) for i in parsed_value):
                    return parsed_value
                else:
                    raise ValueError("String must be a tuple of three integers e.g., '(10, 20, 30)'")
            except (SyntaxError, ValueError) as e:
                raise ValueError(f"Invalid format for initial_teleport_coords: {value}. Expected format like '(x, y, z)'. Error: {e}")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()