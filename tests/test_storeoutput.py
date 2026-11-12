import av
import numpy as np
import pytest
from unittest.mock import MagicMock, patch
from anomalypostprocessing import storeoutput
from visionapi.anomaly_pb2 import JpegFrame, Trajectory

def _make_frames(count, width=320, height=240, step_ms=100):
    frames = []
    for i in range(count):
        img = np.full((height, width, 3), (i * 20) % 256, np.uint8)
        frame = JpegFrame()
        frame.frame_data_jpeg = storeoutput.get_jpeg().encode(img)
        frame.timestamp_utc_ms = 1_000 + i * step_ms
        frames.append(frame)
    return frames


def _make_trajectory(timestamp_utc_ms):
    tr = Trajectory()
    point = tr.trajectory_points.add()
    point.timestamp_utc_ms = timestamp_utc_ms
    point.detection_center.x = 0.5
    point.detection_center.y = 0.5
    return tr


def test_store_annotated_video_encodes_h264(tmp_path):
    frames = _make_frames(10)
    output_file = tmp_path / 'annotated.mp4'
    storeoutput.store_annotated_video(output_file, frames, [_make_trajectory(frames[3].timestamp_utc_ms)])

    with av.open(str(output_file)) as container:
        assert len(container.streams.video) == 1
        stream = container.streams.video[0]
        assert stream.codec_context.name == 'h264'
        decoded = list(container.decode(stream))
    assert len(decoded) == 10
    # pts follow the 100ms capture spacing
    assert decoded[-1].time == pytest.approx(0.9, abs=0.01)


def test_store_annotated_video_odd_dimensions(tmp_path):
    output_file = tmp_path / 'annotated.mp4'
    storeoutput.store_annotated_video(output_file, _make_frames(5, width=321, height=241), [_make_trajectory(0)])

    with av.open(str(output_file)) as container:
        stream = container.streams.video[0]
        assert (stream.codec_context.width, stream.codec_context.height) == (320, 240)


def test_store_annotated_video_identical_timestamps(tmp_path):
    output_file = tmp_path / 'annotated.mp4'
    storeoutput.store_annotated_video(output_file, _make_frames(5, step_ms=0), [_make_trajectory(0)])

    with av.open(str(output_file)) as container:
        assert len(list(container.decode(video=0))) == 5


def test_store_annotated_video_raises_ioerror_on_failure(tmp_path):
    with pytest.raises(IOError, match='Could not create video from frames'):
        storeoutput.store_annotated_video(tmp_path / 'missing_dir' / 'annotated.mp4', _make_frames(2), [_make_trajectory(0)])

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

def test_draw_trajectories_in_frame_returns_annotated_image():
    frame = _make_frames(1)[0]
    result = storeoutput.draw_trajectories_in_frame(frame, [_make_trajectory(frame.timestamp_utc_ms)])
    assert isinstance(result, np.ndarray)
    assert result.shape == (240, 320, 3)
    # red circle drawn at the center (BGR)
    assert tuple(result[120, 160]) == (0, 0, 255)

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
