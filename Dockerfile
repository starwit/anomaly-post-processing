FROM starwitorg/base-python-image:0.0.15 AS build

# Copy only files that are necessary to install dependencies
COPY poetry.lock poetry.toml pyproject.toml /code/
WORKDIR /code
RUN poetry install --only main
    
# Copy the rest of the project
COPY . /code/

### Main artifact / deliverable image

FROM python:3.12-slim
RUN apt update && apt install --no-install-recommends -y \
    libturbojpeg0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and group
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Copy only what is needed at runtime
WORKDIR /code
COPY --from=build --chown=appuser:appgroup /code/.venv /code/.venv
COPY --from=build --chown=appuser:appgroup /code/anomalypostprocessing /code/anomalypostprocessing
COPY --from=build --chown=appuser:appgroup /code/main.py /code/main.py

# Switch to non-root user
USER appuser

ENV PATH="/code/.venv/bin:$PATH"
CMD [ "python", "main.py" ]
