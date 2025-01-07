# tstomirror

## How to use

The prerequisite is that docker is installed and running correctly.

### docker

Create a folder, open a prompt in it, run the command: 

`docker run -v ./:/output ghcr.io/d-fens/tstomirror:main`

### docker compose

Download the [docker-compose.yml](https://raw.githubusercontent.com/d-fens/tstomirror/refs/heads/main/docker-compose.yml) file into an **empty** directory. 

Run `docker compose run mirror` in a command prompt in the same folder.

Check the folder contains the folder `oct2018-4-35-0-uam5h44a.tstodlc.eamobile.com` and a log file of the run called `debug.log`. If run from the same folder it will refresh the content.

A number of older files will be missing from the output and have a WARNING message in the logs.
