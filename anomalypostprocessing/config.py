import pathlib
from typing import List, Optional, Optional

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated
from visionlib.pipeline.settings import LogLevel, YamlConfigSettingsSource


class MinioConfig(BaseModel):
    endpoint: str = 'localhost:9000'
    user: str = 'test'
    password: str = 'test'
    bucket_name: str = 'test'
    secure: bool = True

class RedisInputConfig(BaseModel):
    host: str = 'localhost'
    port: Annotated[int, Field(ge=1, le=65536)] = 6379
    stream_ids: List[str]
    stream_prefix: str

class RedisOutputConfig(BaseModel):
    host: str = 'localhost'
    port: Annotated[int, Field(ge=1, le=65536)] = 6379
    stream_id: str
    stream_prefix: str

class LocalOutputConfig(BaseModel):
    path: pathlib.Path

class AnomalyPostProcessingConfig(BaseSettings):
    log_level: LogLevel = LogLevel.WARNING
    minio: Optional[MinioConfig] = None
    redis_input: RedisInputConfig
    redis_output: Optional[RedisOutputConfig] = None
    prometheus_port: Annotated[int, Field(ge=1024, le=65536)] = 8000
    raw_anomaly: bool = False                                                     # store anomaly as raw frames plus metadata and annotated video (otherwise just annotated video)
    local_output: Optional[LocalOutputConfig] = None                              # store anomalies into file system 

    model_config = SettingsConfigDict(env_nested_delimiter='__')

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (init_settings, env_settings, YamlConfigSettingsSource(settings_cls), file_secret_settings)