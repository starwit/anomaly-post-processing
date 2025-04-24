import contextlib
import logging
import signal
import threading
import requests

from prometheus_client import Counter, Histogram, start_http_server
from visionlib.pipeline.consumer import RedisConsumer
from visionlib.pipeline.publisher import RedisPublisher

from .anomalypostprocessing import AnomalyPostProcessing
from .config import AnomalyPostProcessingConfig
from requests.exceptions import HTTPError, Timeout, RequestException

logger = logging.getLogger(__name__)

REDIS_PUBLISH_DURATION = Histogram('anomaly_post_processing_publish_duration', 'The time it takes to push a message onto the Redis stream',
                                   buckets=(0.0025, 0.005, 0.0075, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.25))
FRAME_COUNTER = Counter('anomaly_post_processing_frame_counter', 'How many frames have been consumed from the Redis input stream')

def run_stage():

    stop_event = threading.Event()

    # Register signal handlers
    def sig_handler(signum, _):
        signame = signal.Signals(signum).name
        print(f'Caught signal {signame} ({signum}). Exiting...')
        stop_event.set()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    # Load config from settings.yaml / env vars
    CONFIG = AnomalyPostProcessingConfig()

    logger.setLevel(CONFIG.log_level.value)

    logger.info(f'Starting prometheus metrics endpoint on port {CONFIG.prometheus_port}')

    start_http_server(CONFIG.prometheus_port)

    logger.info(f'Starting anomaly post processing stage. Config: {CONFIG.model_dump_json(indent=2)}')

    anomaly_post_processing = AnomalyPostProcessing(CONFIG)

    consume = RedisConsumer(CONFIG.redis_input.host, CONFIG.redis_input.port, 
                            stream_keys=[f'{CONFIG.redis_input.stream_prefix}:{stream_id}' for stream_id in CONFIG.redis_input.stream_ids])
    
    if (CONFIG.redis_output.enabled):
        publish = RedisPublisher(CONFIG.redis_output.host, CONFIG.redis_output.port) if CONFIG.redis_output is not None else contextlib.nullcontext()
    
    with consume:
        for stream_key, proto_data in consume():
            if stop_event.is_set():
                break

            if stream_key is None:
                continue

            logger.info(f'Received anomaly message from {stream_key}')

            FRAME_COUNTER.inc()

            output_proto_data = anomaly_post_processing.get(proto_data)

            if output_proto_data is None or CONFIG.redis_output is None:
                continue
            
            if (CONFIG.redis_output.enabled):
                with publish:
                    with REDIS_PUBLISH_DURATION.time():
                        publish(f'{CONFIG.redis_output.stream_prefix}:{CONFIG.redis_output.stream_id}', output_proto_data)
                        
            if (CONFIG.http_sender.enabled):
                logger.info(f"Send decisions to cockpit: {CONFIG.http_sender.applicationUrl + CONFIG.http_sender.endpoint}")
                try:
                    response = requests.post(CONFIG.http_sender.applicationUrl + CONFIG.http_sender.endpoint, data = output_proto_data, headers={"Content-Type": "application/json"})
                    # Check if the request was successful
                    if response.status_code != 200:
                        logger.info(f"Request failed with status code: {response.status_code}")
                except Timeout:
                    logger.info("The request timed out.")
                except HTTPError as http_err:
                    logger.info(f"HTTP error occurred: {http_err}")
                except RequestException as req_err:
                    logger.info(f"Request error occurred: {req_err}")
                except Exception as err:
                    logger.info(f"An unexpected error occurred: {err}")