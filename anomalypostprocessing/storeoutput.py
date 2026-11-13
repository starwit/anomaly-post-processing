import functools
import json
import logging
import time
import zipfile
from fractions import Fraction
from pathlib import Path
from zlib import crc32

import av
import numpy as np
from minio import Minio
from PIL import Image, ImageDraw
from turbojpeg import TurboJPEG
from visionapi.anomaly_pb2 import JpegFrame, Trajectory, TrajectoryPoint

from .config import MinioConfig

log = logging.getLogger(__name__)

DEFAULT_FRAMERATE = 10
# Frames are kept in BGR channel order (as decoded by TurboJPEG), so colors are BGR, too.
# Pillow does not care about channel order, it just calls the image mode "RGB".
ANNOTATION_COLOR = (0, 0, 255)
ANNOTATION_RADIUS = 20


@functools.cache
def get_jpeg() -> TurboJPEG:
    return TurboJPEG()


def store_annotated_video(output_file: Path, frames: list[JpegFrame], trajectories: list[Trajectory]) -> None:
    first_ts = frames[0].timestamp_utc_ms
    duration_ms = frames[-1].timestamp_utc_ms - first_ts
    # Average rate is only a hint for players; actual timing comes from per-frame pts
    framerate = Fraction(len(frames) - 1) / Fraction(duration_ms, 1_000) if duration_ms > 0 else Fraction(DEFAULT_FRAMERATE)

    try:
        with av.open(str(output_file.resolve()), mode='w') as container:
            stream = container.add_stream('libx264', rate=framerate.limit_denominator(1_000))
            stream.pix_fmt = 'yuv420p'
            stream.options = {'crf': '25'}
            stream.time_base = Fraction(1, 1_000)

            start_time_millis = time.time() * 1000
            width = height = None
            last_pts = -1
            skipped = 0
            for frame in frames:
                try:
                    img = draw_trajectories_in_frame(frame, trajectories)
                except OSError as e:
                    # Skip undecodable frames (e.g. empty frame_data_jpeg) instead of dropping the whole video
                    log.warning(f"Skipping undecodable frame (ts={frame.timestamp_utc_ms}, {len(frame.frame_data_jpeg)} bytes): {e}")
                    skipped += 1
                    continue
                if width is None:
                    # yuv420p requires even dimensions
                    height, width = (img.shape[0] // 2) * 2, (img.shape[1] // 2) * 2
                    stream.width, stream.height = width, height
                img = np.ascontiguousarray(img[:height, :width])

                video_frame = av.VideoFrame.from_ndarray(img, format='bgr24')
                # Use real capture timestamps; enforce strictly increasing pts
                pts = max(frame.timestamp_utc_ms - first_ts, last_pts + 1)
                video_frame.pts = pts
                video_frame.time_base = stream.time_base
                last_pts = pts
                container.mux(stream.encode(video_frame))

            if width is None:
                raise ValueError(f"None of the {len(frames)} frames could be decoded")
            if skipped:
                log.warning(f"Skipped {skipped} of {len(frames)} frames that could not be decoded")
            container.mux(stream.encode())
            log.debug("Average time per frame: " + str((time.time() * 1000 - start_time_millis) / len(frames)))
        log.info(f"Video conversion completed successfully ({output_file.resolve()})")
    except (av.error.FFmpegError, OSError, ValueError) as e:
        raise IOError("Could not create video from frames") from e

def save_file_to_minio(minio_config: MinioConfig, file_path: str, object_name: str) -> None:
    client = Minio(
        endpoint=minio_config.endpoint,
        access_key=minio_config.user,
        secret_key=minio_config.password,
        secure=minio_config.secure
    )

    # Determine content type based on file extension
    content_type = {
        '.zip': 'application/zip',
        '.mp4': 'video/mp4',
        '.json': 'application/json',
    }.get(Path(file_path).suffix, 'application/octet-stream')

    try:
        client.fput_object(
            minio_config.bucket_name,
            object_name, 
            file_path=file_path,
            content_type=content_type
        )
    except Exception as e:
        raise IOError(f"Could not upload file {file_path} to MinIO") from e

def draw_trajectories_in_frame(frame: JpegFrame, trajectories: list[Trajectory]) -> np.ndarray:
    center_points = []

    for tr in trajectories:
        for tr_point in tr.trajectory_points:
            if tr_point.timestamp_utc_ms == frame.timestamp_utc_ms:
                center_points.append(tr_point.detection_center)

    image = Image.fromarray(get_jpeg().decode(frame.frame_data_jpeg))
    draw = ImageDraw.Draw(image)

    for point in center_points:
        x = int(point.x * image.width)
        y = int(point.y * image.height)
        draw.ellipse((x - ANNOTATION_RADIUS, y - ANNOTATION_RADIUS, x + ANNOTATION_RADIUS, y + ANNOTATION_RADIUS), fill=ANNOTATION_COLOR)

    return np.asarray(image)


def store_raw(output_directory: Path, frames: list[JpegFrame], trajectories: list[Trajectory]):
    segment_length = (frames[-1].timestamp_utc_ms - frames[0].timestamp_utc_ms)/1_000
    framerate = len(frames) / segment_length

    if not output_directory.exists() or not output_directory.is_dir():
        raise IOError(f"Directory {output_directory} does not exist")

    metadata_json = convert_metadata_to_json(framerate, trajectories)
    write_json_to_file(metadata_json, output_directory / "metadata.json")
    create_and_add_frames_to_zip(frames, output_directory / "frames.zip")


def convert_metadata_to_json(framerate: float, trajectories: list[Trajectory]):
    metadata_json = {
        "framerate": framerate,
        "tracksUnusualMovement": {}
    }

    for tr in trajectories:
        for tr_point in tr.trajectory_points:
            #key = tr_point.timestamp_utc_ms.isoformat()
            key = tr_point.timestamp_utc_ms
            if key in metadata_json["tracksUnusualMovement"].keys():
                metadata_json["tracksUnusualMovement"][key].append(make_json_format(tr_point))
            else:
                metadata_json["tracksUnusualMovement"][key] = [make_json_format(tr_point)]

    return metadata_json


def make_json_format(tr_point: TrajectoryPoint):
    track_json = {}
    track_json["timestamp_utc_ms"] = str(tr_point.timestamp_utc_ms)
    #track_json["geo_coordinate"] = tr_point.geo_coordinate
    track_json["detection_center"] = {"x": tr_point.detection_center.x, "y": tr_point.detection_center.y}
    track_json["anomaly_trigger"] = int(tr_point.anomaly_trigger)
    return track_json


def write_json_to_file(json_data: dict, file_path: str):
    try:
        with open(file_path, 'w') as file_writer:
            json.dump(json_data, file_writer, indent=2)
    except Exception as e:
        raise IOError(f"Could not write metadata to file {file_path}") from e


def create_and_add_frames_to_zip(frames: list[JpegFrame], zip_file_path: str):
    try:
        with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_STORED) as zip_output_stream:
            for frame in frames:
                data = frame.frame_data_jpeg 
                entry_name = f"frameTs_{frame.timestamp_utc_ms}.jpg"
                
                crc = crc32(data) & 0xffffffff

                zip_info = zipfile.ZipInfo(entry_name)
                zip_info.compress_type = zipfile.ZIP_STORED
                zip_info.file_size = len(data)
                zip_info.CRC = crc

                zip_output_stream.writestr(zip_info, data)
    except Exception as e:
        raise IOError(f"Could not create zip file {zip_file_path}") from e