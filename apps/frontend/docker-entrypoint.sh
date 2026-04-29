#!/bin/sh
set -eu

: "${API_HOST:=api}"
export API_HOST

envsubst '${API_HOST}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
