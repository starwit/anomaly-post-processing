import pytest
from unittest.mock import MagicMock, patch
from anomalypostprocessing.httpoutput import HttpOutput
from anomalypostprocessing.config import HttpOutputConfig, LogLevel

class DummyAnomalyMessage:
    def __init__(self):
        self.jpeg_frames = [type('Frame', (), {'timestamp_utc_ms': 123456789})()]
        self.camera_location = type('Loc', (), {'latitude': 1.23, 'longitude': 4.56})()
    def HasField(self, name):
        return name == 'camera_location'

@patch('anomalypostprocessing.httpoutput.requests.post')
def test_send_decision_message_success(mock_post):
    config = MagicMock(spec=HttpOutputConfig)
    config.target_endpoint = 'http://test'
    config.timeout = 1
    config.auth = None
    config.module_name = 'mod'
    config.minio = MagicMock()
    config.minio.bucket_name = 'bucket'
    dummy_msg = DummyAnomalyMessage()
    mock_post.return_value.json.return_value = {'access_token': 'token'}
    mock_post.return_value.raise_for_status.return_value = None
    http_output = HttpOutput(config, LogLevel.INFO)
    http_output._create_decision_msg = MagicMock(return_value=b'{}')
    http_output.send_decision_message(dummy_msg, 'anomalyid')
    assert mock_post.called

def test_create_decision_msg_fields():
    config = MagicMock(spec=HttpOutputConfig)
    config.module_name = 'mod'
    config.minio = MagicMock()
    config.minio.bucket_name = 'bucket'
    dummy_msg = DummyAnomalyMessage()
    http_output = HttpOutput(config, LogLevel.INFO)
    # Patch model_dump_json to avoid serialization issues
    with patch.object(type('Decision', (), {}), 'model_dump_json', return_value=b'{}', create=True):
        result = http_output._create_decision_msg(dummy_msg, 'anomalyid')
        assert isinstance(result, str)
