# Use an official Python runtime as a parent image
FROM python:slim

RUN apt-get update \
    && apt-get -y install libpq-dev gcc \
    && pip install psycopg2

# install docker
RUN apt-get install -y curl
RUN curl -fsSL https://get.docker.com/ -o get-docker.sh \
  && sh get-docker.sh

# Set the working directory to /app
WORKDIR /app

COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Make port 5001 available to the world outside this container
EXPOSE 5001

# Define environment variable
ENV NAME World

# Run app.py when the container launches
ENTRYPOINT ["python", "-m gunicorn --workers 1 --threads 10 --bind :5001 wsgi:app --timeout 90 --worker-class gevent"]
