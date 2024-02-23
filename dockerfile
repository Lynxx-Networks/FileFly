# Use Alpine Linux as the base image
FROM alpine:latest

# Set the maintainer label
LABEL maintainer="Collin Pendleton <collinp@collinpendleton.com>"

# Install Python and other dependencies
RUN apk add --no-cache \
    python3 \
    py3-pip \
    git \
    curl \
    gcc \
    musl-dev \
    libffi-dev \
    zlib-dev \
    jpeg-dev \
    mariadb-connector-c \
    postgresql-dev \
    openssl-dev

# Create directories
RUN mkdir /sql && mkdir /filefly

# Copy the requirements file
COPY ./requirements.txt /

# Setup Python environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
COPY ./requirements.txt /
RUN /opt/venv/bin/pip install --no-cache-dir -r /requirements.txt


# Copy the application code
COPY . /filefly
RUN chmod -R 755 /filefly

# Set the working directory
WORKDIR /filefly

# Expose the port the app runs on
EXPOSE 8000

# Set the entrypoint as Uvicorn server running the app
ENTRYPOINT ["uvicorn"]
CMD ["main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug"]
