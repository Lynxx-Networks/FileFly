# Use an official Python runtime as a parent image
FROM python:3.12.0a7-slim

# Set the maintainer label
LABEL maintainer="Collin Pendleton <collinp@collinpendleton.com>"

# Set non-interactive frontend (useful for Docker builds)
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl gcc libffi-dev zlib1g-dev libjpeg-dev mariadb-client libpq-dev openssl && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file and install Python dependencies
COPY ./requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# Clone the Git repository
RUN git clone https://github.com/Lynxx-Networks/FileFly.git /filefly
RUN chmod -R 755 /filefly

# Set the working directory
WORKDIR /filefly

# Expose the port the app runs on
EXPOSE 8000

# Set the entrypoint as Uvicorn server running the app
ENTRYPOINT ["uvicorn"]
CMD ["main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
