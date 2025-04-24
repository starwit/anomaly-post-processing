import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from google.protobuf import text_format
from prometheus_client import Counter, Histogram, Summary
from visionapi.anomaly_pb2 import AnomalyMessage
from visionapi.reporting_pb2 import IncidentMessage

from anomalypostprocessing.storeoutput import (save_file_to_minio,
                                               store_annotated_video,
                                               store_raw)

from .config import AnomalyPostProcessingConfig

logging.basicConfig(format='%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s')
logger = logging.getLogger(__name__)

GET_DURATION = Histogram('anomaly_post_processing_get_duration', 'The time it takes to deserialize the proto until returning the tranformed result as a serialized proto',
                         buckets=(0.0025, 0.005, 0.0075, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25))
OBJECT_COUNTER = Counter('anomaly_post_processing_object_counter', 'How many detections have been transformed')
PROTO_SERIALIZATION_DURATION = Summary('anomaly_post_processing_proto_serialization_duration', 'The time it takes to create a serialized output proto')
PROTO_DESERIALIZATION_DURATION = Summary('anomaly_post_processing_proto_deserialization_duration', 'The time it takes to deserialize an input proto')


class AnomalyPostProcessing:
    def __init__(self, config: AnomalyPostProcessingConfig) -> None:
        self.config = config
        self.isDebug = self.config.log_level.value == 'DEBUG'
        logger.setLevel(self.config.log_level.value)

    def __call__(self, input_proto) -> Any:
        return self.get(input_proto)
    
    @GET_DURATION.time()
    def get(self, input_proto: bytes) -> str:
        anomaly_msg: AnomalyMessage = self._unpack_proto(input_proto)
        anomaly_id = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid4().hex[:6]}'
        self._save_anomaly(anomaly_msg, anomaly_id)

        if self.config.redis_output and self.config.minio:
            return self._create_output(anomaly_msg, anomaly_id)
        else:
            return None
        
    @PROTO_DESERIALIZATION_DURATION.time()
    def _unpack_proto(self, message_bytes: bytes) -> AnomalyMessage:
        anomaly_msg = AnomalyMessage()
        anomaly_msg.ParseFromString(message_bytes)

        return anomaly_msg
    
    @PROTO_SERIALIZATION_DURATION.time()
    def _pack_proto(self, anomaly_msg: AnomalyMessage):
        anomaly_msg.trajectories
        return anomaly_msg.SerializeToString()
    
    @PROTO_SERIALIZATION_DURATION.time()
    def _create_output(self, input_msg: AnomalyMessage, anomaly_id: str) -> bytes:
        if self.isDebug:
            for trajectory in input_msg.trajectories:
                self._print_message(trajectory)
        output_msg = IncidentMessage()
        output_msg.media_url = f'{self.config.minio.bucket_name}/{anomaly_id}/annotated.mp4'
        output_msg.model_info.CopyFrom(input_msg.model_info)
        output_msg.timestamp_utc_ms = input_msg.jpeg_frames[0].timestamp_utc_ms

        # Forward camera geo location
        if input_msg.HasField('camera_location'):
            output_msg.camera_location.CopyFrom(input_msg.camera_location)
        
        if self.isDebug:
            self._print_message(output_msg)
        return output_msg.SerializeToString()

    def _save_anomaly(self, input_msg: AnomalyMessage, anomaly_id: str):
        frames = input_msg.jpeg_frames
        if len(frames) < 2: 
            return
        
        trajectories = input_msg.trajectories
        if len(trajectories) == 0: 
            return

        try:
            # Create a temporary directory and store all necessary output artifacts
            temp_output_dir = Path('./output')
            os.makedirs(temp_output_dir, exist_ok=True)
            store_annotated_video(temp_output_dir / 'annotated.mp4', frames, trajectories)
            if self.config.raw_anomalies:
                store_raw(temp_output_dir, frames, trajectories)

            # Copy output artifacts to local storage
            if self.config.local_output is not None:
                shutil.copytree(temp_output_dir, self.config.local_output.path / anomaly_id, dirs_exist_ok=True)
            
            # Upload output artifacts to MinIO
            if self.config.minio:
                for file in temp_output_dir.iterdir():
                    object_name = f"{anomaly_id}/{file.name}"
                    save_file_to_minio(self.config.minio, file, object_name)
        except Exception as e:
            logger.error(f"Error saving anomaly: {e}")

        # Clean up
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        
    def _print_message(self, msg: Any):
        if not os.path.exists('target'):
            os.makedirs('target')
        f = open('target/log.txt', 'a')
        f.write("++++++ new " + str(msg.__class__) + " +++++++++++")
        f.write(text_format.MessageToString(msg))
        f.close()