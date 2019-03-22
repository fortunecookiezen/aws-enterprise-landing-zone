#!/usr/bin/env bash

OPERATION=$1

#set -x
set -e

REGION="us-west-2"
TEMPLATES="$TEMPLATES ./01transitVpc.yaml"
#TEMPLATES="$TEMPLATES common/01vpc.yaml"
#TEMPLATES="$TEMPLATES transitVpc/02transitsubnets.yaml"
#TEMPLATES="$TEMPLATES transitVpc/03transitgateway.yaml"
#TEMPLATES="$TEMPLATES tenantVpc/02tenantsubnets.yaml"

ASI=css
Environment=sbx
Owner=brian.peterson@cloudshift.cc
vpccidr=10.250.0.0/21

PARAMETERS="ParameterKey=ASI,ParameterValue=$ASI"
PARAMETERS="$PARAMETERS ParameterKey=Environment,ParameterValue=$Environment"
PARAMETERS="$PARAMETERS ParameterKey=Owner,ParameterValue=$Owner"
PARAMETERS="$PARAMETERS ParameterKey=vpccidr,ParameterValue=$vpccidr"

create_stackname () {
    # Returns a compliant stack name from a template file string
    TEMPLATE=$1
    local STACK_NAME="stack-`echo $TEMPLATE | awk -F'/' '{print$2}' | awk -F'.' '{print$1}'`"
    echo "$STACK_NAME"
}

deploy_stack () {
    # Deploys a cloudformation stack
    TEMPLATE=$1
    PARAMTERS=$2
    STACK_NAME=$(create_stackname $TEMPLATE)
    STACK_STATUS=$(get_stack_status $STACK_NAME)
    # until the statck is deployed (or updated), run the following loop
    until [ "$STACK_STATUS" = "CREATE_COMPLETE" ] || [ "$STACK_STATUS" == "UPDATE_COMPLETE" ]; do
        STACK_STATUS=$(get_stack_status $STACK_NAME)
        echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
        # Check to see if STACK_STATUS is empty (not deployed)
        if [ "$STACK_STATUS" == "" ]; then
            # There is no stack status, so deploy it
            echo "DEPLOYING STACK: $STACK_NAME"
            STACK_ID=`aws cloudformation create-stack\
                --stack-name $STACK_NAME\
                --template-body file://$TEMPLATE\
                --parameters $PARAMETERS\
                --region $REGION | jq -r .StackId`
        fi
        sleep 5
    done
}

get_stack_status () {
    # returns the status of a stack. Blank if none
    STACK_NAME=$1
    local STACK_STATUS=`aws cloudformation describe-stacks\
        --region $REGION \
        | jq -r --arg StackName $STACK_NAME '.Stacks[] | select(.StackName==$StackName) .StackStatus'`
    echo "$STACK_STATUS"
}

delete_stack () {
    # deletes a cloudformation stack
    TEMPLATE=$1
    STACK_NAME=$(create_stackname $TEMPLATE)
    STACK_STATUS=$(get_stack_status $STACK_NAME)
    # When the stack is deleted, it will have no status
    until [ "$STACK_STATUS" = "" ]; do
        STACK_STATUS=$(get_stack_status $STACK_NAME)
        echo "STACK_NAME: $STACK_NAME, STACK_STATUS: $STACK_STATUS"
        # If the stack is not in "DELETE_IN_PROGRESS" status, initiate the delete
        if [[ "$STACK_STATUS" != *"_IN_PROGRESS" ]] && [ "$STACK_STATUS" != "" ] ; then
            echo "DELETING STACK: $STACK_NAME"
            aws cloudformation delete-stack --stack-name $STACK_NAME --region $REGION
        fi
        sleep 5
    done
}


case $OPERATION in
    "deploy")
        for TEMPLATE in $TEMPLATES; do
            deploy_stack $TEMPLATE $PARAMETERS
        done
        ;;
    "delete")
        for TEMPLATE in $TEMPLATES; do
            delete_stack $TEMPLATE
        done
        ;;
    *)
        echo "invalid operation: \"$OPERATION\""
        exit 1
        ;;
esac
