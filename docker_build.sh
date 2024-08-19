#!/bin/bash

docker build -t starwitorg/anomly-post-processing:$(poetry version --short) .