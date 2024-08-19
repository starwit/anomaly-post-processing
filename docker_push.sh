#!/bin/bash
docker login docker.internal.starwit-infra.de
docker push docker.internal.starwit-infra.de/anomaly-post-processing:$(poetry version --short)