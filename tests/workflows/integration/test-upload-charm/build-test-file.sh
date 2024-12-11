#!/bin/bash

set -eu

function build_resource() {
    local RESOURCE_OUTPUT=$1

    case $RESOURCE_OUTPUT in
        test-file.txt)
            touch "$RESOURCE_OUTPUT"
            ;;
        *)
            echo "Unsupported resource: $RESOURCE_OUTPUT"
            exit 1
            ;;
    esac
}

build_resource "$1"