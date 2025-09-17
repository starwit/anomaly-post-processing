import pytest
from unittest.mock import MagicMock, patch
from anomalypostprocessing.anomalypostprocessing import AnomalyPostProcessing
from anomalypostprocessing.config import AnomalyPostProcessingConfig, LogLevel

class DummyProto:
    def ParseFromString(self, b):
        self.jpeg_frames = [1, 2]
        self.trajectories = [1]

class DummyConfig:
    log_level = LogLevel.WARNING
    http_output = None
    raw_anomalies = False
    local_output = None

@patch('anomalypostprocessing.anomalypostprocessing.AnomalyMessage', DummyProto)
def test_unpack_proto_returns_dummy():
    app = AnomalyPostProcessing(DummyConfig())
    proto = app._unpack_proto(b'bytes')
    assert hasattr(proto, 'jpeg_frames')

@patch('anomalypostprocessing.anomalypostprocessing.store_annotated_video')
@patch('anomalypostprocessing.anomalypostprocessing.save_file_to_minio')
@patch('anomalypostprocessing.anomalypostprocessing.store_raw')
def test_save_anomaly_calls_store(mock_store_raw, mock_save_file, mock_store_annot):
    config = MagicMock()
    config.log_level = LogLevel.WARNING
    config.http_output = None
    config.raw_anomalies = True
    config.local_output = None
    app = AnomalyPostProcessing(config)
    dummy = MagicMock()
    dummy.jpeg_frames = [1, 2]
    dummy.trajectories = [1]
    app._save_anomaly(dummy, 'id')
    assert mock_store_annot.called
    assert mock_store_raw.called

def test_call_delegates_to_get():
    app = AnomalyPostProcessing(DummyConfig())
    app.get = MagicMock()
    app(b'bytes')
    app.get.assert_called_once()
