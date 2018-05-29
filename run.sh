#!/bin/bash

organization="UNISTOOP2018S"
assignment="assignment-4"
token="token"
roster="roster.csv"

python script.py --org-name=${organization} --assign-name=${assignment} --token-file=${token} --roster-file=${roster}
