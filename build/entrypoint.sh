#!/bin/bash

# Trigger an error if non-zero exit code is encountered
set -e 

if [ -f "soundscapes/${1}.py" ]; then
    # The command matches a file
    SCRIPT_NAME=${1}
    shift
    exec python3 -m soundscapes.${SCRIPT_NAME} ${@}
else
    # An unknown command (debugging the container?): Forward as is
    exec ${@}
fi
