#!/usr/bin/bash

organization="UNISTOOP2018S"
assignment="assignment-4"
token="token"
roster="classroom_roster.csv"


python script.py --org_nae=${organization} --assign_name=${assignment} --token_file=${token} --roster_file=${roster}
