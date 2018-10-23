#!/bin/bash

# Authentication. This authentication code only works when a DSS server is in ridiculously
# insecure 'testing' mode. In real production environment, a user must manually log in once
# using itksnap-wt -dss-auth $DSSURL. Afterwards, the login credentials will be stored in
# the user's ~/.alfabis directory so there is no need to authenticate in the script itself
function dss_auth()
{
  local DSSURL=${1?}

  # Authenticate in a loop (because the server might not be up when this code starts)
  while [[ true ]]; do

    # Obtain token (this code will not work with production DSS servers!)
    local TOKEN=$(curl -s $DSSURL/api/token)

    # Authenticate using the token
    itksnap-wt -dss-auth $DSSURL <<< $TOKEN

    # If successful, exit the loop
    if [[ $? -eq 0 ]]; then return; fi

    # Wait and try again
    sleep 10

  done
}

# This code sets up the service for the first time. We assume the user has already 
# authenticated and use the cookie file created by dss_auth
function dss_admin_service()
{
  # Parameters
  local DSSURL=${1?}
  local SERVICE_GITHASH=${2?}

  # Create a provider called 'test' (repeat calls are ok)
  itksnap-wt -dssa-providers-add test

  # Add the test user to the provider access list
  itksnap-wt -dssa-providers-users-add test test@example.com

  # Add the test service to the provider access list
  local REPO='https://github.com/pyushkevich/alfabis-svc-example'
  itksnap-wt -dssa-providers-services-add test $REPO $SERVICE_GITHASH
}

