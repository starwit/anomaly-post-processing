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


def _write_dummy_video(output_file, frames, trajectories):
    output_file.write_bytes(b'video')


def _make_app(local_output_path=None, max_age_days=None, max_size_gb=None):
    config = MagicMock()
    config.log_level = LogLevel.WARNING
    config.http_output = None
    config.raw_anomalies = False
    config.local_output = MagicMock(path=local_output_path, max_age_days=max_age_days, max_size_gb=max_size_gb) if local_output_path else None
    return AnomalyPostProcessing(config)


def _make_msg():
    msg = MagicMock()
    msg.jpeg_frames = [1, 2]
    msg.trajectories = [1]
    return msg


def test_save_anomaly_cleans_up_temp_dir_on_success(tmp_path, monkeypatch):
    temp_root = tmp_path / 'tmp'
    temp_root.mkdir()
    local_output = tmp_path / 'local'
    monkeypatch.setattr('tempfile.tempdir', str(temp_root))

    with patch('anomalypostprocessing.anomalypostprocessing.store_annotated_video', side_effect=_write_dummy_video):
        _make_app(local_output)._save_anomaly(_make_msg(), 'id')

    assert (local_output / 'id' / 'annotated.mp4').read_bytes() == b'video'
    assert list(temp_root.iterdir()) == []


def test_save_anomaly_cleans_up_temp_dir_on_error(tmp_path, monkeypatch, caplog):
    temp_root = tmp_path / 'tmp'
    temp_root.mkdir()
    monkeypatch.setattr('tempfile.tempdir', str(temp_root))

    def write_then_fail(output_file, frames, trajectories):
        _write_dummy_video(output_file, frames, trajectories)
        raise IOError('boom')

    with patch('anomalypostprocessing.anomalypostprocessing.store_annotated_video', side_effect=write_then_fail):
        _make_app()._save_anomaly(_make_msg(), 'id')

    assert 'Error saving anomaly: boom' in caplog.text
    assert list(temp_root.iterdir()) == []


def test_save_anomaly_runs_housekeeping_when_limit_set(tmp_path):
    local_output = tmp_path / 'local'
    with patch('anomalypostprocessing.anomalypostprocessing.store_annotated_video', side_effect=_write_dummy_video), \
         patch('anomalypostprocessing.anomalypostprocessing.cleanup_local_output') as mock_cleanup:
        _make_app(local_output, max_age_days=14, max_size_gb=10)._save_anomaly(_make_msg(), 'id')
    mock_cleanup.assert_called_once_with(local_output, 14, 10)


def test_save_anomaly_skips_housekeeping_without_limits(tmp_path):
    local_output = tmp_path / 'local'
    with patch('anomalypostprocessing.anomalypostprocessing.store_annotated_video', side_effect=_write_dummy_video), \
         patch('anomalypostprocessing.anomalypostprocessing.cleanup_local_output') as mock_cleanup:
        _make_app(local_output)._save_anomaly(_make_msg(), 'id')
    mock_cleanup.assert_not_called()


def test_housekeeping_error_does_not_break_saving(tmp_path, caplog):
    local_output = tmp_path / 'local'
    with patch('anomalypostprocessing.anomalypostprocessing.store_annotated_video', side_effect=_write_dummy_video), \
         patch('anomalypostprocessing.anomalypostprocessing.cleanup_local_output', side_effect=OSError('nope')):
        _make_app(local_output, max_age_days=14)._save_anomaly(_make_msg(), 'id')
    assert (local_output / 'id' / 'annotated.mp4').exists()
    assert 'Error during local output housekeeping: nope' in caplog.text
    assert 'Error saving anomaly' not in caplog.text
