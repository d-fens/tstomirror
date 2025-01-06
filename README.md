# tstomirror

## How to use

The prerequise is that docker is installed and running correctly.

Download the [docker-compose.yml](https://raw.githubusercontent.com/d-fens/tstomirror/refs/heads/main/docker-compose.yml) file into an **empty** directory. 

Run `docker compose run mirror` in a command promp in the same folder.

Check the folder contains the output which is a folder called `static` that contains `oct2018-4-35-0-uam5h44a.tstodlc.eamobile.com` and a log file of the run called `debug.log`. If run from the same folder it will refresh the content.

A number of older files will be missing from the output and have an WARNING message in the logs.
