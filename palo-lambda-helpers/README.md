# palo-lambda-helpers

This is a set of functions that help manage palo alto firewalls from cloudformation
They are all designed to be called as a cloudformation CustomResource.

The serverless.yaml file defines exports for each function so that they can be called 
from other cloudformation stacks

Deploy this stack once per transitVpc stack deployed, after the stack is deployed. These
lambdas run from within the trusted subnet on the transit VPC so that they can access the management
interface

### Requirements 
serverless npm module - for lambda deployment
serverless-python-requirements plugin for serverless - to manage python requirements
docker - used by above plugin for building python requirements compatible with aws lambda runtim

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
3. sls deploy --paloStackName=[NAME_OF_THE_PALO_TRANIST_VPC_STACK]

### Cloud Formation Helper Functions

#### palo_static_route.py
Manages static routes in a palo firewall

#### handler_template.py
Just a boilerplate lambda. Copy this to a new file to create a new function

#### moo_helpers.py
set of small helper functions that are useful in all lambdas
