# citefix in a container, used by Render (render.yaml) and fine on any Docker host.
# Standard library only, so there is nothing to install. Pass DEEPSEEK_API_KEY and OPENALEX_API_KEY as
# environment variables, plus FEEDBACK_REPO and FEEDBACK_GITHUB_TOKEN to keep tester feedback; on Render
# they are entered under Environment.
FROM python:3.11-slim

# 40 checks an hour per address, because a class on one campus network reaches the app from one IP.
# Feedback files go to /tmp, which is always writable; set FEEDBACK_REPO to keep them for good.
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    CITEFIX_TRUST_PROXY=1 \
    CITEFIX_PER_IP_PER_HOUR=40 \
    CITEFIX_DAILY_LIMIT=200 \
    FEEDBACK_DIR=/tmp/citefix-feedback

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user . .

EXPOSE 8000
# The port comes from $PORT, which hosts such as Render set.
CMD ["python", "-m", "citefix", "serve", "--host", "0.0.0.0"]
