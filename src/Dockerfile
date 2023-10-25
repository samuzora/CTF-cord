FROM docker.io/oz123/pipenv:3.11-v2023-6-26 AS builder

ENV PIPENV_VENV_IN_PROJECT=1
ADD Pipfile.lock Pipfile /app/
WORKDIR /app/
RUN /root/.local/bin/pipenv sync

FROM docker.io/python:3.11 AS runtime

COPY --from=builder /app/.venv/ /app/.venv/

COPY . /app/

CMD python3 /app/main.py
