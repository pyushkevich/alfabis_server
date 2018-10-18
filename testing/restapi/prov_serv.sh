#!/bin/bash
# ==============================================
# Test script for the provider and services APIs 
# ==============================================
DSSURL=${1?}
TOKEN=${2?}

# Cookie file
DSSJAR=$(mktemp /tmp/test.XXXXXX)

# Login
curl -v -c $DSSJAR -d token=$TOKEN $DSSURL/api/login

# Shorthand for calling curl
function api()
{
  local rest_path=${1?}
  shift 1

  curl -b $DSSJAR "$@" $DSSURL/api/$rest_path
  local rc=$?
  echo ""

  return $rc
}

# Create provider 01 and 02
api admin/providers -d name=prov01
api admin/providers -d name=prov02

# Create some services for each provider
api admin/providers/prov01/services -d repo=https://github.com/pyushkevich/alfabis-svc-example -d ref=master
api admin/providers/prov01/services -d repo=https://github.com/pyushkevich/alfabis-svc-ashs-harp -d ref=0d3c428471a0b9a75ad124c162c53386d2cb8d7c
api admin/providers/prov02/services -d repo=https://github.com/pyushkevich/alfabis-svc-example -d ref=master

# List available services
api services

# Drop the first provider
api admin/providers/prov01/delete
api services
