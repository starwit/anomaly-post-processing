import pytest
from anomalypostprocessing.config import MinioConfig, RedisInputConfig, AuthConfig, HttpOutputConfig, LocalOutputConfig, AnomalyPostProcessingConfig, LogLevel
from pydantic import ValidationError

# MinioConfig
def test_minio_config_fields():
    c = MinioConfig(endpoint='e', user='u', password='p', bucket_name='b', secure=True)
    assert c.endpoint == 'e'
    assert c.secure is True

# RedisInputConfig
def test_redis_input_config_valid():
    c = RedisInputConfig(stream_ids=['id'], stream_prefix='prefix')
    assert c.port == 6379
    assert c.stream_ids == ['id']

def test_redis_input_config_invalid_port():
    with pytest.raises(ValidationError):
        RedisInputConfig(port=70000, stream_ids=['id'], stream_prefix='prefix')

# AuthConfig
def test_auth_config_fields():
    c = AuthConfig(token_endpoint_url='http://test', client_id='cid', username='u', password='p')
    assert c.client_id == 'cid'

# HttpOutputConfig
@pytest.mark.parametrize('timeout', [0, 10])
def test_http_output_config_timeout(timeout):
    minio = MinioConfig(endpoint='e', user='u', password='p', bucket_name='b', secure=False)
    c = HttpOutputConfig(target_endpoint='http://test', timeout=timeout, module_name='mod', minio=minio)
    assert c.timeout == timeout

def test_http_output_config_auth_optional():
    minio = MinioConfig(endpoint='e', user='u', password='p', bucket_name='b', secure=False)
    c = HttpOutputConfig(target_endpoint='http://test', timeout=1, module_name='mod', minio=minio)
    assert c.auth is None

# LocalOutputConfig
from pathlib import Path
def test_local_output_config_path():
    c = LocalOutputConfig(path=Path('/tmp'))
    assert c.path == Path('/tmp')
    assert c.max_age_days == 14
    assert c.max_size_gb == 10

def test_local_output_config_limits_can_be_disabled():
    c = LocalOutputConfig(path=Path('/tmp'), max_age_days=None, max_size_gb=None)
    assert c.max_age_days is None
    assert c.max_size_gb is None

def test_local_output_config_fractional_limits():
    c = LocalOutputConfig(path=Path('/tmp'), max_age_days=0.5, max_size_gb=0.25)
    assert c.max_age_days == 0.5
    assert c.max_size_gb == 0.25

@pytest.mark.parametrize('field', ['max_age_days', 'max_size_gb'])
@pytest.mark.parametrize('value', [0, -1])
def test_local_output_config_rejects_non_positive_limits(field, value):
    with pytest.raises(ValidationError):
        LocalOutputConfig(path=Path('/tmp'), **{field: value})

# AnomalyPostProcessingConfig

def test_anomaly_post_processing_config_minimal():
    redis = {'stream_ids': ['id'], 'stream_prefix': 'prefix'}
    c = AnomalyPostProcessingConfig(redis_input=redis)
    assert c.redis_input.stream_ids == ['id']
    assert c.log_level == LogLevel.WARNING

