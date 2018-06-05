#!/bin/bash

organization="UNISTOOP2018S"
assignment="assignment-4"
token="token"
roster="roster.csv"

if [ -z "$1" ]; then
    python script.py --org-name=${organization} --assign-name=${assignment} --token-file=${token} --roster-file=${roster}
else
    python script.py --org-name=${organization} --assign-name=${assignment} --token-file=${token} --roster-file=${roster} --student=$1
fi

