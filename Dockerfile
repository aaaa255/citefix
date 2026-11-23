# citefix on Hugging Face Spaces (Docker SDK). Standard library only, so nothing to install.
# Set DEEPSEEK_API_KEY and OPENALEX_API_KEY as Space secrets; they arrive as environment variables.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    CITEFIX_TRUST_PROXY=1 \
    CITEFIX_PER_IP_PER_HOUR=10 \
    CITEFIX_DAILY_LIMIT=200

# Spaces run containers as user 1000.
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user . .

EXPOSE 7860
CMD ["python", "-m", "citefix", "serve", "--host", "0.0.0.0", "--port", "7860"]
