# FileFly
A speedy dockerized app that can expose a folder over http for downloading

![FileFly](assets/filefly.png)


# Making requests to download files using Filefly

## Introduction

Filefly is an API system for downloading files over networks/the internet regardless of how big they are. It exists to provide a simple way to pull down files from a file repo when we run automations. It requires no port forwarding and entirely runs over http. This document is a guide for using Filefly, deploying it, and it also documents the APIs and how to use them. 

Please note, Filefly provides 2 different apis. A v1 and a v2. V2 should be preferred if at all possible as v2 is significantly more secure, using JWT based authentication rather than basic user and pass like the legacy v1. 

## Deploying Filefly

Filefly is available as a docker container. It entirely contains a user database as sqllite that can be used to authenticate for file downloads. Additional users can be added in addition to the default one as well with the register api endpoint. 

The easiest way to get Filefly up and running is to use Docker Compose. Simply create this file on the server you'd like to host Filefly ensuring you change the volumes and user and pass to values relevant for you. If you skip creating the username and password variables a default user will be created with default credentials of 
username: admin
password: P@ssW0rd!
```
version: '3'
services:
  filefly:
    image: madeofpendletonwool/filefly:latest
    environment:
      USERNAME: "admin"
      PASSWORD: 'P@ssW0rd!'
      SECRET_KEY: '' # 32 character string alpha-num - If not set it will auto generate
    ports:
    # Filefly Port
      - "8052:8000"
    volumes:
      - /home/user/filefly/data:/data
      - /home/user/filefly/sqllite:/filefly/sql
```


## The APIs

### API Version 1.0

####  Downloading a File with Basic Auth (v1):

To download a file using basic authentication, you can use the curl command with the -u option. Replace username:password with the actual credentials and file_path with the path of the file you want to download.

```
curl -u username:password http://myserver:8052/file_path --output downloaded_file
```
### API Version 2.0

#### Downloading a File with JWT Auth (v2):

First, you'll need to obtain a JWT token using the /token endpoint. Then, use that token to download a file.

    Obtaining JWT Token:

```
curl -X 'POST' \
  'http://localhost:8052/token' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=your_username&password=your_password'
```
Using the Token to Download a File:

Replace your_jwt_token with the obtained token and file_path with the desired file's path.

bash

    curl -H "Authorization: Bearer your_jwt_token" http://localhost:8052/files_v2/file_path --output downloaded_file

#### Listing All Files (v2):

To list all files, use the JWT token obtained from the /token endpoint.

```
curl -H "Authorization: Bearer your_jwt_token" http://localhost:8052/files_v2/list_all
```
#### Registering a New User:

To register a new user, you'll need to send a POST request with the username and password for the user you want to create. Use the JWT token from /token endpoint above.

Replace your_jwt_token, new_username, and new_password with appropriate values.
```
curl -X 'POST' \
  'http://localhost:8052/register' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer your_jwt_token' \
  -H 'Content-Type: application/json' \
  -d '{
        "username": "new_username",
        "password": "new_password"
      }'
```

Make sure to replace URLs, port numbers, and paths with the correct values for your setup.
