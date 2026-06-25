FROM python:3.13-slim

# to avoid buffer/logs issues
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip
RUN pip install --no-cache-dir uv

RUN useradd -m worker_user

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN chown -R worker_user:worker_user /app
USER worker_user

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=worker_user:worker_user worker ./worker

CMD ["python", "-m", "worker.main"]