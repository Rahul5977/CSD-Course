# Runs the Lab 7 load test from inside the compose network, against the web service.
FROM python:3.12-slim
RUN pip install --no-cache-dir httpx==0.28.1
WORKDIR /lt
COPY scripts/loadtest.py .
ENTRYPOINT ["python", "loadtest.py"]
CMD ["http://web", "--requests", "5000", "--concurrency", "32"]
