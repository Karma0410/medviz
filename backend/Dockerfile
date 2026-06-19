FROM python:3.13-slim

RUN pip install --upgrade pip
RUN pip install --no-cache-dir uv

RUN useradd -m api_user

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN chown -R api_user:api_user ./
USER api_user

RUN uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=api_user:api_user main.py ./
COPY --chown=api_user:api_user src ./src

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]