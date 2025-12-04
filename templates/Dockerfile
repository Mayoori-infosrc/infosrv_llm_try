FROM python:3.10

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

# Ensure src is on Python path so `import llm` works
ENV PYTHONPATH=/app/src

CMD ["python", "-m", "llm.main"]
