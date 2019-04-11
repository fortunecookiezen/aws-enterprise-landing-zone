# transit-vpc-troposphere project

Creates the cloudformation stack required to deploy the transit vpc

## Requirements
python3
troposphere


## Environment setup
* install python
* install boto3 pip package
* install troposphere pip package


## Deployment
* configure AWS credentials for the desired account
* determine deployment region
* deploy lambda helpers stack (see [../cfn-lambda-helpers/README.md](../cfn-lambda-helpers/README.md))
* deploy palo bootstrap config (see [../palo-bootstrap/README.md](../palo-bootstrap/README.md))
* deploy transitVpc Stack

      ./manage_stack.py apply TRANIST_STACK_NAME -m transitVpc.py -p parms.all.yaml,parms.transitVpc.yaml
      
* deploy palo helpers stack (see [../palo-lambda-helpers/README.md](../palo-lambda-helpers/README.md))
* deploy a test tenant VPC

      ./manage_stack.py apply TENNAT_STACK_NAME -m transitVpc.py -p parms.all.yaml,parms.tenantVpc.yaml
      
* Open AWS Simple Systems Manager, connect to the tenant instance and test internet access

      curl https://www.google.com
