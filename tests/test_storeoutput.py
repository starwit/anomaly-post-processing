import pytest
from unittest.mock import MagicMock, patch
from anomalypostprocessing import storeoutput
from pathlib import Path

@patch('anomalypostprocessing.storeoutput.subprocess.Popen')
def test_store_annotated_video_runs(mock_popen):
    mock_proc = MagicMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.flush = MagicMock()
    mock_proc.communicate.return_value = (b'', b'')
    mock_proc.returncode = 0
    mock_popen.return_value = mock_proc
    frame = MagicMock()
    frame.timestamp_utc_ms = 0
    frame2 = MagicMock()
    frame2.timestamp_utc_ms = 1000
    with patch('anomalypostprocessing.storeoutput.draw_trajectories_in_frame', return_value=b'bytes'):
        storeoutput.store_annotated_video(Path('/tmp/test.mp4'), [frame, frame2], [MagicMock()])
    assert mock_popen.called

@patch('anomalypostprocessing.storeoutput.Minio')
def test_save_file_to_minio_calls_fput(mock_minio):
    minio_cfg = MagicMock()
    minio_cfg.endpoint = 'e'
    minio_cfg.user = 'u'
    minio_cfg.password = 'p'
    minio_cfg.secure = False
    minio_cfg.bucket_name = 'b'
    client = MagicMock()
    mock_minio.return_value = client
    storeoutput.save_file_to_minio(minio_cfg, '/tmp/file.mp4', 'obj')
    assert client.fput_object.called

def test_draw_trajectories_in_frame_runs():
    frame = MagicMock()
    frame.timestamp_utc_ms = 1
    frame.frame_data_jpeg = b'\xff\xd8\xff\xd9'  # minimal jpeg
    tr = MagicMock()
    tr.trajectory_points = []
    with patch('anomalypostprocessing.storeoutput.cv2.imdecode', return_value=MagicMock(shape=(10,10,3))):
        with patch('anomalypostprocessing.storeoutput.cv2.imencode', return_value=(True, b'bytes')):
            result = storeoutput.draw_trajectories_in_frame(frame, [tr])
            assert isinstance(result, bytes)

@patch('anomalypostprocessing.storeoutput.write_json_to_file')
@patch('anomalypostprocessing.storeoutput.create_and_add_frames_to_zip')
def test_store_raw_calls_helpers(mock_zip, mock_json):
    frame = MagicMock()
    frame.timestamp_utc_ms = 0
    frame2 = MagicMock()
    frame2.timestamp_utc_ms = 1000
    frames = [frame, frame2]
    tr = MagicMock()
    tr.trajectory_points = []
    output_dir = MagicMock()
    output_dir.exists.return_value = True
    output_dir.is_dir.return_value = True
    storeoutput.store_raw(output_dir, frames, [tr])
    assert mock_json.called
    assert mock_zip.called

def test_convert_metadata_to_json_and_make_json_format():
    tr_point = MagicMock()
    tr_point.timestamp_utc_ms = 1
    tr_point.detection_center.x = 0.5
    tr_point.detection_center.y = 0.5
    tr_point.anomaly_trigger = True
    tr = MagicMock()
    tr.trajectory_points = [tr_point]
    result = storeoutput.convert_metadata_to_json(30.0, [tr])
    assert 'framerate' in result
    assert 'tracksUnusualMovement' in result
    json_format = storeoutput.make_json_format(tr_point)
    assert 'timestamp_utc_ms' in json_format

def test_write_json_to_file(tmp_path):
    data = {'a': 1}
    file_path = tmp_path / 'test.json'
    storeoutput.write_json_to_file(data, str(file_path))
    assert file_path.exists()

def test_create_and_add_frames_to_zip(tmp_path):
    frame = MagicMock()
    frame.timestamp_utc_ms = 1
    frame.frame_data_jpeg = b'data'
    zip_path = tmp_path / 'frames.zip'
    storeoutput.create_and_add_frames_to_zip([frame], str(zip_path))
    assert zip_path.exists()
