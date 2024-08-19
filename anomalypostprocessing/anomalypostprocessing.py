import logging
import os
from typing import Any, Dict, NamedTuple

from prometheus_client import Counter, Histogram, Summary
from visionapi.anomaly_pb2 import AnomalyMessage
from visionapi.reporting_pb2 import IncidentMessage
from google.protobuf import text_format


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

        # TODO Your implementation goes (mostly) here
        logger.warning('Received anomaly message from pipeline')
        return self._create_output(anomaly_msg)
        
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
    def _create_output(self, input_msg: AnomalyMessage) -> bytes:
        if self.isDebug:
            for trajectory in input_msg.trajectories:
                self._print_message(trajectory)
        output_msg = IncidentMessage()
        output_msg.model_info.CopyFrom(input_msg.model_info)
        output_msg.timestamp_utc_ms = input_msg.jpeg_frames[0].timestamp_utc_ms
        if self.isDebug:
            self._print_message(output_msg)
        return output_msg.SerializeToString()
    
    def _print_message(self, msg: Any):
        if not os.path.exists('target'):
            os.makedirs('target')
        f = open('target/log.txt', 'a')
        f.write("++++++ new " + str(msg.__class__) + " +++++++++++")
        f.write(text_format.MessageToString(msg))
        f.close()