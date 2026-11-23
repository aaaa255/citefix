# citefix in a container, used by Render (render.yaml) and fine on any Docker host.
# Standard library only, so there is nothing to install. Pass DEEPSEEK_API_KEY and OPENALEX_API_KEY as
# environment variables; on Render they are entered when the Blueprint is created.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    CITEFIX_TRUST_PROXY=1 \
    CITEFIX_PER_IP_PER_HOUR=10 \
    CITEFIX_DAILY_LIMIT=200

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user . .

EXPOSE 8000
# The port comes from $PORT, which hosts such as Render set.
CMD ["python", "-m", "citefix", "serve", "--host", "0.0.0.0"]
