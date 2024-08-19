#!/bin/bash

docker build -t docker.internal.starwit-infra.de/anomly-post-processing:$(poetry version --short) .