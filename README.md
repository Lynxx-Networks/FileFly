# FileFly
A speedy dockerized app that can expose a folder over http for downloading

![FileFly](assets/filefly.png)


## Introduction

This application is an extremely simple way to expose a folder to an http server and allows you to pull files over curl of any size. Authentication is built in and provides multiple options. 

## Get it started

Starting is super simple and the recommended method is with docker compose. Be sure you change the exposed volume to the folder you want to expose over the network.

```yaml
version: '3'
services:
  filefly:
    image: madeofpendletonwool/filefly:latest
    ports:
    # Filefly Port
      - "8052:8000"
    volumes:
      - /home/user/filefly/data:/filefly
```

