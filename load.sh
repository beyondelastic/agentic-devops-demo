#!/bin/bash
FRONTEND_URL=$(azd env get-values | awk -F'=' '/FRONTEND_URL/{gsub(/"/,"",$2); print $2}')
k6 run -e API_BASE="$FRONTEND_URL" load/k6-spike.js