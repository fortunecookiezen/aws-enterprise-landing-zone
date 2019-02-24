# Transit VPC

Creates Transit VPC with public and private subnet pairs across two availability zones:

* 2 public subnets with nat gateways and an Internet gateway for things like load balancers, ec2, etc.
* 2 private subnets attached to a transit gateway, and ...
* transit gateway for other vpcs to connect to

The idea is to create a buffer vpc and provide segmentation of resources from the Internet. By using the  
Transit VPC to host the public subnets, we can better manage the attack surface presented to the Internet.

## To Do

* create security groups for the subnet access control
* create a parameter for the public subnets in the transit vpc in other accounts
* refine the tgw cft to create tgw routes and route associations