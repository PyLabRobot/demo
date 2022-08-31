# Use an official Python runtime as a parent image
FROM python:slim

RUN apt-get update

# install docker
RUN apt-get install -y curl
RUN curl -fsSL https://get.docker.com/ -o get-docker.sh \
  && sh get-docker.sh

COPY worker/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Copy the current directory contents into the container
COPY . .

# Run app.py when the container launches
ENTRYPOINT ["python", "worker/worker.py"]

