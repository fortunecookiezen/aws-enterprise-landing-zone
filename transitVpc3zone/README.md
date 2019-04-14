# transit-vpc-troposphere project

Creates the cloudformation stack required to deploy the transit vpc

## Requirements
python3
troposphere
tropoform


## Environment setup
* install python3 and pip3
* install terraform (for palo bootstrap)
* install the serverless framework `npm install serverless` (to deploy the lambda helpers)
* install tropoform using `pip install tropoform` (also installs the following relevant pip packages):
    * boto3
    * troposphere

## Deployment
* configure AWS credentials for the desired account
* determine deployment region and set AWS_DEFAULT_REGION environment variable
* deploy lambda helpers stack (see [../cfn-lambda-helpers/README.md](../cfn-lambda-helpers/README.md))

     $ cd cfn-lambda-helpers
     $ sls deploy
    
* deploy palo bootstrap s3 bucket (see [../palo-bootstrap/README.md](../palo-bootstrap/README.md))

     $ cd ../palo-boostrap
     $ terraform init
     $ terraform plan
     $ terrafrom apply
     
* deploy transitVpc Stack (ensure that the parms.all.yaml has the correct LambdaHelpersStack: parameter)

     $ cd ../transitVpc3zone
     $ tropoform apply TRANIST_STACK_NAME -m transitVpc.py -p parms.all.yaml,parms.transitVpc.yaml
      
* deploy palo helpers stack (see [../palo-lambda-helpers/README.md](../palo-lambda-helpers/README.md))

      $ cd ../palo-lambda-helpers
      $ sls deploy --paloStackName=TRANSIT_STACK_NAME
      
* deploy the Palo Static Routes Stack. Ensure parms.paloRoutes.yaml has correct settings

      $ cd ../transitVpc3zone
      $ tropoform apply PALO_ROUTES_STACK_NAME -m paloStaticRoutes.py -p parms.all.yaml,parms.paloRoutes.yaml

* deploy a test tenant VPC

      $ tropoform apply TENNAT_STACK_NAME -m transitVpc.py -p parms.all.yaml,parms.tenantVpc.yaml
      
* Open AWS Simple Systems Manager, connect to the tenant instance and test internet access

      $ curl https://www.google.com
