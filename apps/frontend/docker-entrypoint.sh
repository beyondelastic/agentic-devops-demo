#!/bin/sh
set -eu

: "${API_HOST:=api}"
: "${API_SCHEME:=https}"
export API_HOST API_SCHEME

envsubst '${API_HOST} ${API_SCHEME}' \
  < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

exec nginx -g 'daemon off;'
