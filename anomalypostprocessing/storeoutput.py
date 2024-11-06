import subprocess
import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
import cv2
import numpy as np
import os
import json
import zipfile
from zlib import crc32

from visionapi.anomaly_pb2 import JpegFrame, Trajectory, TrajectoryPoint


log = logging.getLogger(__name__)


def store_video(frames: list[JpegFrame], path: str, trajectories: list[Trajectory]):
    seconds_passed = (frames[-1].timestamp_utc_ms - frames[0].timestamp_utc_ms)/1_000
    framerate = len(frames) / seconds_passed
    ffmpeg_command = [
            'ffmpeg', '-f', 'image2pipe', '-r', str(framerate),
            '-vcodec', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-crf', '25',
            '-analyzeduration', '2147483647', '-probesize', '2147483647', '-y', f'{path}/out.mp4'
        ]
    
    try:
        process = subprocess.Popen(ffmpeg_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #tracks_unusual_movement = filter_relevant_tracks(tracks, anomalies)
        #tracks_dict = transform_trajectory_info(trajectories)
        start_time_millis = time.time() * 1000
        try:
            for frame in frames:
                annotated_frame = draw_trajectories_in_frame(frame, trajectories)
                process.stdin.write(annotated_frame)
                process.stdin.flush()
            log.debug("Average time per frame: " + str((time.time() * 1000 - start_time_millis) / len(frames)))
        except Exception as ex:
            log.error("Could not create video from frames")
            log.debug(str(ex))
            log.debug(process.stderr.read().decode())
            

        process.stdin.close()

        process.wait()

        if process.returncode == 0:
            log.info("Video conversion completed successfully.")
        else:
            log.error("Video conversion failed.")
            log.debug(process.stderr.read().decode())
    except (IOError, subprocess.SubprocessError) as e:
        print(e)


def draw_trajectories_in_frame(frame: JpegFrame, trajectories: list[Trajectory]):
    center_points = []

    for tr in trajectories:
        for tr_point in tr.trajectory_points:
            if tr_point.timestamp_utc_ms == frame.timestamp_utc_ms:
                center_points.append(tr_point.detection_center)

    frame_data = frame.frame_data_jpeg
    np_arr = np.frombuffer(frame_data, np.uint8)
    frame_img = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)

    height, width = frame_img.shape[:2]

    for point in center_points:
        x, y = point.x, point.y
        x = int(x * width)
        y = int(y * height)
        cv2.circle(frame_img, (x, y), 20, (0, 0, 255), -1)

    _, encoded_img = cv2.imencode('.jpeg', frame_img)
    return encoded_img.tobytes()


def store_frames(frames: list[JpegFrame], path: str, trajectories: list[Trajectory]):
    print(trajectories)
    print(trajectories[0].trajectory_points)
    seconds_passed = (frames[-1].timestamp_utc_ms - frames[0].timestamp_utc_ms)/1_000
    framerate = len(frames) / seconds_passed

    metadata_json = convert_metadata_to_json(framerate, trajectories)
    write_json_to_file(metadata_json, os.path.join(path, "metadata.json"))
    create_and_add_frames_to_zip(frames, os.path.join(path, "frames.zip"))


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
    except IOError as e:
        print(f"Could not store JSON file {file_path}")
        print(e)


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
    except IOError as e:
        print(f"Could not store frames in zip-file {zip_file_path}")
        print(e)