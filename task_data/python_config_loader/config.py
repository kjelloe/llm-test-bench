import os
from dataclasses import dataclass


@dataclass
class Config:
    host: str
    port: int
    debug: bool
    max_connections: int
    app_name: str


def load_config() -> Config:
    return Config(
        host=os.environ.get("APP_HOST", "localhost"),
        port=int(os.environ.get("APP_PORT", "8080")),
        debug=os.environ.get("APP_DEBUG", "false").lower() == "true",
        max_connections=int(os.environ.get("APP_MAX_CONN", "10")),
        app_name=os.environ.get("APP_NAME", "myapp"),
    )
