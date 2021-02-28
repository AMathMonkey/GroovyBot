#!/bin/bash

sqlite3 groovy.db "SELECT * FROM runs" |
awk -F "|" '{myarray[$1]++} END {for (key in myarray) print key, myarray[key]}'|
sort -k 2 -n -r > numrunsperplayer
