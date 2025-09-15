FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .


RUN pip install --no-cache-dir -r requirements.txt


COPY book_search_engine.py .


CMD ["python", "book_search_engine.py"]
