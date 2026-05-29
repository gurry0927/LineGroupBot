FROM python:3.12-slim@sha256:090ba77e2958f6af52a5341f788b50b032dd4ca28377d2893dcf1ecbdfdfe203

RUN groupadd -g 1000 gakes && useradd -u 1000 -g 1000 -m -s /bin/bash gakes

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data && chown -R gakes:gakes /app

USER gakes

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
