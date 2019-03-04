# Transit VPC

Creates Transit VPC with public and private subnet pairs across two availability zones:

* 2 public subnets with nat gateways and an Internet gateway for things like load balancers, ec2, etc.
* 2 private subnets attached to a transit gateway, and ...
* transit gateway for other vpcs to connect to

The idea is to create a buffer vpc and provide segmentation of resources from the Internet. By using the  
Transit VPC to host the public subnets, we can better manage the attack surface presented to the Internet.

## Steps to Create Transit VPC
1. Create VPC - common/01vpc.yaml
2. Enable VPC flow logs - common/02enableVpcFlowLogs.yaml
3. Create subnets - transitVpc/02transitsubnets.yaml
4. Create Transit Gateway - transitVpc/03transitgateway.yaml
5. Create Transit Gateway Routes - transitVpc/transitGatewayRoutes.yaml
    requires transit gateway route table and attachment ids from step 4
### ready to create Tenant VPC
## Post creation steps
1. Ensure transit gateway resource is shared (there should be an api call here or something)
2. Manually add summary routes to public and private route tables pointing at the transit gateway,
at least until AWS adds this to CloudFormation.
3. Create outbound resolver rule if needed for services zone - post/10transitServiceResolver.yaml
## To Do

* create security groups for the subnet access control
* create a parameter for the public subnets in the transit vpc in other accounts
* move the defined parameters to imports in 02transitsubnets.yaml - these two files go together.
* ~refine the tgw cft to create tgw routes and route associations~