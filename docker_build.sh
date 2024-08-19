#!/bin/bash
docker login docker.internal.starwit-infra.de
docker build -t docker.internal.starwit-infra.de/anomaly-post-processing:$(poetry version --short) .