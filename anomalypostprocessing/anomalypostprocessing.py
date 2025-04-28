import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from prometheus_client import Histogram, Summary
from visionapi.anomaly_pb2 import AnomalyMessage

from anomalypostprocessing.storeoutput import (save_file_to_minio,
                                               store_annotated_video,
                                               store_raw)

from .config import AnomalyPostProcessingConfig
from .httpoutput import HttpOutput

logging.basicConfig(format='%(asctime)s %(name)-15s %(levelname)-8s %(processName)-10s %(message)s')
logger = logging.getLogger(__name__)

GET_DURATION = Histogram('anomaly_post_processing_get_duration', 'The time it takes to deserialize the proto until returning the tranformed result as a serialized proto',
                         buckets=(0.0025, 0.005, 0.0075, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25))
PROTO_DESERIALIZATION_DURATION = Summary('anomaly_post_processing_proto_deserialization_duration', 'The time it takes to deserialize an input proto')


class AnomalyPostProcessing:
    def __init__(self, config: AnomalyPostProcessingConfig) -> None:
        self.config = config
        self.http_output = HttpOutput(config.http_output, config.log_level) if config.http_output else None
        self.isDebug = self.config.log_level.value == 'DEBUG'
        logger.setLevel(self.config.log_level.value)

    def __call__(self, input_proto) -> Any:
        return self.get(input_proto)
    
    @GET_DURATION.time()
    def get(self, input_proto: bytes) -> None:
        anomaly_msg: AnomalyMessage = self._unpack_proto(input_proto)
        anomaly_id = f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{uuid4().hex[:6]}'
        self._save_anomaly(anomaly_msg, anomaly_id)
        if self.http_output:
            self.http_output.send_decision_message(anomaly_msg, anomaly_id)
        
    @PROTO_DESERIALIZATION_DURATION.time()
    def _unpack_proto(self, message_bytes: bytes) -> AnomalyMessage:
        anomaly_msg = AnomalyMessage()
        anomaly_msg.ParseFromString(message_bytes)

        return anomaly_msg
    
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
            
            # Upload output artifacts to MinIO if http_output is configured
            if self.config.http_output is not None:
                for file in temp_output_dir.iterdir():
                    object_name = f"{anomaly_id}/{file.name}"
                    save_file_to_minio(self.config.http_output.minio, file, object_name)
        except Exception as e:
            logger.error(f"Error saving anomaly: {e}")

        # Clean up
        shutil.rmtree(temp_output_dir, ignore_errors=True)
        