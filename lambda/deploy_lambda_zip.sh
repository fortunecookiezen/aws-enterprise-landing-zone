#!/usr/bin/env bash

# Zips up all the .py files in the current directory into a file called lambda.zip and pushes to an s3
# bucket specified as a single arg to this script

# As of this writing, these libraries required boto3 version 1.9.120 installed in lib
# mkdir -p lib
# pip install boto3 botocore -t lib

set -e
BUCKET=$1
LAMBDA_ZIP=lambda.zip
REGION=us-west-2

function print_usage() {
    echo "USAGE: ${0} S3_BUCKET"
}

if [[ "${BUCKET}" == "" ]]; then
    echo "ERROR: Must specify a bucket name"
    print_usage
    exit 1
fi

if [[ `aws s3api list-buckets | jq -r '.Buckets[].Name' | grep -c ${BUCKET}` -lt 1 ]]; then
    echo "BUCKET: s3://${BUCKET} does not exit. Creating now"
    aws s3 mb --region $REGION s3://${BUCKET}
else
    echo "BUCKET: s3://${BUCKET} already exits."
fi

echo "Creating lambda.zip"
zip ${LAMBDA_ZIP} *.py
if [[ -d lib ]]; then
    cd lib
    zip ..${LAMBDA_ZIP} *
    cd ..
fi

# Upload ${LAMBDA_ZIP} to s3://${BUCKET}
aws s3 cp ${LAMBDA_ZIP} s3://${BUCKET}
