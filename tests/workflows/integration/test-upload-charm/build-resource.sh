#!/bin/bash

set -eu

function build_resource() {
    local RESOURCE=$1
    local RESOURCE_OUTPUT=$2

    case $RESOURCE in
        test-file)
            touch "$RESOURCE_OUTPUT"
            ;;
        *)
            echo "Unsupported resource: $RESOURCE"
            exit 1
            ;;
    esac
}

build_resource "$1" "$2"