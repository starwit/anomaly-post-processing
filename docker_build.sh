#!/bin/bash
docker build -t docker.internal.starwit-infra.de/anomaly-post-processing:$(poetry version --short) .