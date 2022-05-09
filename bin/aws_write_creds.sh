#!/usr/bin/env bash
set -o errexit  # abort on nonzero exit status
set -o pipefail # don't hide errors within pipes

# 
# This script is temporary until we rewrite the AWS deployment following #81 and #82.
# We look into the environment and if we see environment variables for the AWS 
# authentication process we move them into a credentials file. This is primarily being
# done at this time to support Jenkins using env vars for creds
#

aws_auth_vars=(AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN)

missing_auth_vars=()
for i in "${aws_auth_vars[@]}"
do
    test -n "${!i:+y}" || missing_vars+=("$i")
done

if [ ${#missing_auth_vars[@]} -ne 0 ]
then
    echo "Did not find values for:" 
    printf ' %q\n' "${missing_vars[@]}"
    echo "Will assume they are in credentials file or not needed"
else
    echo "Creating credentials file"
    # Create the directory....
    mkdir -p ~/.aws
    CREDS=~/.aws/credentials
    echo "[default]"                                    >  $CREDS
    echo "aws_access_key_id=$AWS_ACCESS_KEY_ID"         >> $CREDS 
    echo "aws_secret_access_key=$AWS_SECRET_ACCESS_KEY" >> $CREDS
    # This is if we have non-temp credentials...
    if [[ -z "${AWS_SESSION_TOKEN+x}" ]]; then
      echo "Variable AWS_SESSION_TOKEN was unset; not adding to credentials"
    else
      echo "aws_session_token=$AWS_SESSION_TOKEN"         >> $CREDS
    fi

fi

