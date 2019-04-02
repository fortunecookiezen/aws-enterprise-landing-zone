#!/usr/bin/env bash

OPERATION=$1
TEMPLATE=$2

#set -x
set -e

REGION="us-west-2"
ASI=css
Environment=sbx
Owner=brian.peterson@cloudshift.cc
vpcCidr=10.250.0.0/21
LambdaFunctionsBucketName=css-lambda-helpers
paloBootstrapBucket=css-sbx-palo-bootstrap
paloSshKeyName=css-ssh-keypair

testCidr=192.168.1.0/24
testZone=trusted


create_stackname () {
    # Returns a compliant stack name from a template file string
    TEMPLATE=$1
    FILENAME=$(basename ${TEMPLATE})
    local STACK_NAME="stack-`echo ${FILENAME} | awk -F'.' '{print$1}'`"
    echo "$STACK_NAME"
}

deploy_stack () {
    # Deploys a cloudformation stack
    TEMPLATE=$1
    PARAMETERS=$2
    STACK_NAME=$(create_stackname ${TEMPLATE})
    STACK_STATUS=$(get_stack_status ${STACK_NAME})
    # until the stack is deployed (or updated), run the following loop
    until [[ "$STACK_STATUS" = "CREATE_COMPLETE" ]] || [[ "$STACK_STATUS" == "UPDATE_COMPLETE" ]]; do
        STACK_STATUS=$(get_stack_status ${STACK_NAME})
        echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
        # Check to see if STACK_STATUS is empty (not deployed)
        if [[ "$STACK_STATUS" == "" ]]; then
            # There is no stack status, so deploy it
            echo "DEPLOYING STACK: $STACK_NAME"
            STACK_ID=`aws cloudformation create-stack\
                --stack-name ${STACK_NAME}\
                --template-body file://${TEMPLATE}\
                --parameters ${PARAMETERS}\
                --region ${REGION} \
                --capabilities CAPABILITY_NAMED_IAM | jq -r .StackId`
        fi
        sleep 5
    done
    aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} | jq .Stacks[0].Outputs
}

get_stack_status () {
    # returns the status of a stack. Blank if none
    STACK_NAME=$1
    local STACK_STATUS=`aws cloudformation describe-stacks\
        --region ${REGION} \
        | jq -r --arg StackName ${STACK_NAME} '.Stacks[] | select(.StackName==$StackName) .StackStatus'`
    echo "$STACK_STATUS"
}

delete_stack () {
    # deletes a cloudformation stack
    TEMPLATE=$1
    STACK_NAME=$(create_stackname ${TEMPLATE})
    STACK_STATUS=$(get_stack_status ${STACK_NAME})
    # When the stack is deleted, it will have no status
    until [[ "$STACK_STATUS" = "" ]]; do
        STACK_STATUS=$(get_stack_status ${STACK_NAME})
        echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
        # If the stack is not in "DELETE_IN_PROGRESS" status, initiate the delete
        if [[ "$STACK_STATUS" != *"_IN_PROGRESS" ]] && [[ "$STACK_STATUS" != "" ]] ; then
            echo "DELETING STACK: $STACK_NAME"
            aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}
        fi
        sleep 5
    done
}

update_stack () {
    # Updates a cloudformation stack
    TEMPLATE=$1
    PARAMETERS=$2
    STACK_NAME=$(create_stackname ${TEMPLATE})
    STACK_STATUS=$(get_stack_status ${STACK_NAME})
    # until the stack is deployed (or updated), run the following loop
    if [[ "$STACK_STATUS" == "CREATE_COMPLETE" ]] || \
        [[ "$STACK_STATUS" == "UPDATE_COMPLETE" ]] || \
        [[ "$STACK_STATUS" == "UPDATE_ROLLBACK_COMPLETE" ]]; then
        STACK_STATUS=$(get_stack_status ${STACK_NAME})
        echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
        echo "UPDATING STACK: $STACK_NAME"
        STACK_ID=`aws cloudformation update-stack\
            --stack-name ${STACK_NAME}\
            --template-body file://${TEMPLATE}\
            --parameters ${PARAMETERS}\
            --region ${REGION} \
            --capabilities CAPABILITY_NAMED_IAM | jq -r .StackId`
        until [[ "$STACK_STATUS" == "UPDATE_IN_PROGRESS" ]]; do
            STACK_STATUS=$(get_stack_status ${STACK_NAME})
            echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
            sleep 1
        done
    else
        echo "STACK not deployed. exiting"
        exit 1
    fi
    until [[ "$STACK_STATUS" == "UPDATE_COMPLETE" ]] || [[ "$STACK_STATUS" == "UPDATE_ROLLBACK_COMPLETE" ]] ; do
        STACK_STATUS=$(get_stack_status ${STACK_NAME})
        echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
        sleep 5
    done
    aws cloudformation describe-stacks --stack-name ${STACK_NAME} --region ${REGION} | jq .Stacks[0].Outputs
}


PARAMETERS="ParameterKey=ASI,ParameterValue=$ASI"
PARAMETERS="${PARAMETERS} ParameterKey=Environment,ParameterValue=$Environment"
PARAMETERS="${PARAMETERS} ParameterKey=Owner,ParameterValue=$Owner"
if [[ ${TEMPLATE} == *"lambdaHelpers.yaml" ]]; then
    PARAMETERS="${PARAMETERS} ParameterKey=LambdaFunctionsBucketName,ParameterValue=$LambdaFunctionsBucketName"
elif [[ ${TEMPLATE} == *"transitVpc.yaml" ]]; then
    PARAMETERS="${PARAMETERS} ParameterKey=vpcCidr,ParameterValue=$vpcCidr"
    PARAMETERS="${PARAMETERS} ParameterKey=paloSshKeyName,ParameterValue=$paloSshKeyName"
    PARAMETERS="${PARAMETERS} ParameterKey=paloBootstrapBucket,ParameterValue=$paloBootstrapBucket"
elif [[ ${TEMPLATE} == *"tenantVpc.yaml" ]]; then
    PARAMETERS="${PARAMETERS} ParameterKey=vpcCidr,ParameterValue=$testCidr"
    PARAMETERS="${PARAMETERS} ParameterKey=securityZone,ParameterValue=$testZone"
fi

case ${OPERATION} in
    "create" )
        deploy_stack ${TEMPLATE} "${PARAMETERS}"
        ;;
    "delete" )
        delete_stack ${TEMPLATE}
        ;;
    "update" )
        update_stack ${TEMPLATE} "${PARAMETERS}"
        ;;
    *)
        echo "invalid operation: \"$OPERATION\""
        exit 1
        ;;
esac
