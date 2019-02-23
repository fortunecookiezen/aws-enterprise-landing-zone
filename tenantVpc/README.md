# Tenant VPC
Creates 2 subnet pairs across two availability zones:

* 2 app subnets for things like load balancers, ec2, etc.
* 2 private (data) subnets for things like rds, dynamodb, etc.

The idea is to create a some segmentation within a single vpc environment, 
even if the Transit VPC is hosting the public subnets.

## To Do
* create security groups for the subnet access control
* create a parameter for the public subnets in the transit vpc
