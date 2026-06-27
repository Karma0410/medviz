FROM python:3.13-slim

RUN pip install --upgrade pip
RUN pip install --no-cache-dir uv

RUN useradd -m api_user

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen

RUN mkdir -p /app/data/uploads
RUN chown -R api_user:api_user /app

USER api_user

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=api_user:api_user config.py ./
COPY --chown=api_user:api_user main.py ./
COPY --chown=api_user:api_user src ./src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]