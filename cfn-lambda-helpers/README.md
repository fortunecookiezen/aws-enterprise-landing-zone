# cfn-lambda-helpers

This is a set of functions that help make up for some missing features in cloudformation
They are all designed to be called as a cloudformation CustomResource.

The serverless.yaml file defines exports for each function so that they can be called 
from other cloudformation stacks

Use the Factory Account to deploy this stack once per region, before the transitGateway Stack is deployed.

### Requirements 

serverless npm module - for lambda deployment
serverless-python-requirements plugin for serverless - to manage python requirements
docker - used by above plugin for building python requirements compatible with aws lambda runtime

### Build Host

Add requirements or link to template for build host creation. - jim to build this.
EC2 instance requirements:

* docker ce
* python3 & pip
* terraform
* tropoform
* git (to clone repo)

### Setup
configure serverless
```
npm install serverless
sls plugin install serverless-python-requirements
```

install docker ce. See https://docs.docker.com/ for instructions

### Deployment

1. configure deployment region in serverless.yaml
2. configure your AWS credentials for the account in which you want to deploy
3. sls deploy

### Cloud Formation Helper Functions

#### subnet_ip_generator.py
Returns a single IP from a Cidr Block and position.
Useful for determining the router for a subnet as Fn::Cidr cant return a single IP

#### vpc_subnet_attributes.py
Returns detailed attributes for an AWS subnet given it's subnetId. 
Specifically returns the subnet cidr, which isn't available in cfn GetAtt for the subnet

#### vpc_tgw_attributes.py
Returns detailed attributes for an AWS transit gateway given it's transitaGatewayId. 
Specifically returns the transit gateway's main route table, which isn't available in cfn GetAtt for the tgw

#### vpc_tgw_route.py
Manages routes in a VPC Route Table to a transit gateway endpoint in a VPC.
Useful because cloudformation doesnt support routing to a tgw endpoint

#### handler_template.py
Just a bolierplate lambda. Copy this to a new file to create a new function

#### moo_helpers.py
set of small helper functions that are useful in all lambdas
