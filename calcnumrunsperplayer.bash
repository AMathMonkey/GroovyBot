#!/bin/bash
sqlite3 -separator ": " groovy.db "SELECT name, count(name) AS c FROM runs GROUP BY name ORDER BY c DESC;" > numrunsperplayer 

