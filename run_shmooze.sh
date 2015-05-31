#!/bin/bash -e

trap "trap - SIGTERM && kill -- -$$" SIGINT SIGTERM EXIT

# You may want to uncomment this if before installing system-wide
export PYTHONPATH=$PWD

# Load settings.json file 
export SHMOOZE_SETTINGS="$PWD/settings.json"
#export SHMOOZE_SETTINGS=$1
echo "Shmooze settings.json:  $SHMOOZE_SETTINGS";

# One way to run all the shmooze services is to use supervisord
# in not daemon mode. 

SCONF="$PWD/supervisord.conf"
#SCONF=$(python -c "import pkg_resources; print pkg_resources.resource_filename('shmooze', '../supervisord.conf')")
echo "Supervisor configuration: $SCONF";

supervisord -n -c $SCONF;

# Alternatively, you can run all of your services individually:

#python -m shmooze.wsgi &
#python -m myapp.queue

