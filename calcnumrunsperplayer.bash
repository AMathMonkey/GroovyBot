#!/bin/bash

sqlite3 groovy.db "SELECT name, count(name) AS c FROM runs GROUP BY name ORDER BY c DESC;" > numrunsperplayer 
