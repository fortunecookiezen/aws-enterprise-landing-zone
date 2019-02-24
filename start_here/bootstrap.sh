#!/usr/bin/env bash
# this should be run first from a laptop or something
# 1. Edit S3BucketPolicy.json and add aws account numbers to it.
# 2. Create an S3 bucket with the S3BucketPolicy.json attached to it
# 3. do something to automate uploading the template files to the newly
#    created s3 bucket.
# 4. create shell scripts to run the templates from the command line
cli=`which aws`

# 1. Create S3 bucket to hold template files:
# $cli --profile factory cloudformation create-stack --stack-name bootstrap --template-body S3.yaml --enable-termination-protection

# $cli --profile sharedservices cloudformation create-stack --stack-name transitvpc --template-body ../transitVpcNestedStack.yaml --enable-termination-protection
# $cli --profile development cloudformation create-stack --stack-name tenantvpc --template-body ../tenantVpcNestedStack.yaml --enable-termination-protection