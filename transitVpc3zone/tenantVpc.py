from troposphere import Parameter, Output, Template
from troposphere import Cidr, Join, GetAtt, Ref, Tags, GetAZs, Select, ImportValue, Condition, Equals
import troposphere.ec2 as ec2
import troposphere.iam as iam
import logging
import sys
from awacs.aws import Action, Allow, PolicyDocument, Principal, Statement
import cfn_custom_resources
import cfn_palo_resources
import string
import random

# TODO: these should be arguments passed to get_template
azs = ['a', 'b']
azs = ['a']
subnet_layers = ['web', 'app', 'db']
subnet_bits = 5  # (32 - 5 = /27


def get_template():
    template = Template()
    template.description = "Test Tenant VPC for Palo Transit VPC"

    #######################################
    # Parameters - Environment Configuration

    group_name = "Environment Configuration"

    asi = template.add_parameter(
        Parameter(
            "ASI",
            Description="asi - must be lower-case, limit 4 characters",
            Type="String",
            MinLength=2,
            MaxLength=4,
            AllowedPattern="[a-z]*"
        )
    )
    template.add_parameter_to_group(asi, group_name)

    env = template.add_parameter(
        Parameter(
            "Environment",
            Description="environment (nonprod|prod) - must be lower-case, limit 7 characters",
            Type="String",
            MinLength=3,
            MaxLength=7,
            AllowedPattern="[a-z]*"
        )
    )
    template.add_parameter_to_group(env, group_name)

    owner = template.add_parameter(
        Parameter(
            "Owner",
            Type="String",
            Description="email address of the the Owner of this stack",
            Default="admin@root.com",
            AllowedPattern="^[\\w-\\+]+(\\.[\\w]+)*@[\\w-]+(\\.[\\w]+)*(\\.[a-z]{2,})$"
        )
    )
    template.add_parameter_to_group(owner, group_name)

    # Network Configuration
    group_name = "Network Configuration"
    vpc_cidr = template.add_parameter(
        Parameter(
            "vpcCidr",
            Type="String",
            Description="Cidr Range for Transit VPC - must be /21 or larger",
            AllowedPattern='^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\/(1[6-9]|2[0-8]))$'
        )
    )
    template.add_parameter_to_group(vpc_cidr, group_name)

    palo_stack = template.add_parameter(
        Parameter(
            "paloStack",
            Type="String",
            Description="Name of the deployed Palo Stack",
        )
    )
    template.add_parameter_to_group(palo_stack, group_name)

    security_zone = template.add_parameter(
        Parameter(
            "securityZone",
            Type="String",
            Description="Security zone to which we should connect the vpc (web or trusted)",
        )
    )
    template.add_parameter_to_group(security_zone, group_name)

    # Lambda Helpers Section
    group_name = "Lambda Helper Stacks"

    palo_helpers_stack = template.add_parameter(
        Parameter(
            "paloHelpersStack",
            Type="String",
            Description="Name of deployed Palo Lambda Helpers Stack",
        )
    )
    template.add_parameter_to_group(palo_helpers_stack, group_name)

    # Refer to lambda helpers stack (with function arns in output)
    lambda_helpers_stack = template.add_parameter(
        Parameter(
            "LambdaHelpersStack",
            Description="Name of deployed CloudFormation lambda Helpers stack",
            Type="String",
        )
    )
    template.add_parameter_to_group(lambda_helpers_stack, group_name)

    # Palo Credentials
    group_name = "Palo Credentials"
    palo_user = template.add_parameter(
        Parameter(
            "paloUser",
            Description="Administrative username for Palo",
            Type="String",
            MinLength=1,
            MaxLength=255,
            Default="admin"
        )
    )
    template.add_parameter_to_group(palo_user, group_name)

    palo_pass = template.add_parameter(
        Parameter(
            "paloPass",
            Description="Password for administrative user on Palo",
            Type="String",
            MinLength=1,
            MaxLength=255,
            # TODO: Look this up in secrets manager
        )
    )
    template.add_parameter_to_group(palo_pass, group_name)

    palo_virtual_router = template.add_parameter(
        Parameter(
            "paloVirtualRouter",
            Description="Name of the Palo Virtual Router",
            Type="String",
            MinLength=1,
            MaxLength=255,
            Default="default"
        )
    )
    template.add_parameter_to_group(palo_virtual_router, group_name)

    palo_web_interface = template.add_parameter(
        Parameter(
            "paloWebInterface",
            Description="Name of the Palo Interface connected to the Web Subnet",
            Type="String",
            MinLength=1,
            MaxLength=255,
            Default="ethernet1/3"
        )
    )
    template.add_parameter_to_group(palo_virtual_router, group_name)
    ####################
    # Data Lookup

    # Amazon Linux 2 AMI
    ami_amzn2 = template.add_parameter(
        Parameter(
            "amznLinux2Ami",
            Type="AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
            Default="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
        )
    )

    ####################
    # Conditions

    is_web_zone = template.add_condition(
            "IsWebZone",
            Equals(Ref(security_zone), "web")
    )

    #############################
    # Tags we'll apply to all resources

    std_tags = Tags(
        Project=Ref(asi),
        Environment=Ref(env),
        Owner=Ref(owner),
        SecurityZone=Ref(security_zone),
    )

    #############################
    # VPC

    vpc = template.add_resource(
        ec2.VPC(
            "vpc",
            CidrBlock=Ref(vpc_cidr),
            EnableDnsHostnames=True,
            EnableDnsSupport=True,
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), Ref(security_zone), "Tenant", "vpc"]))
        )
    )

    #############################
    # Subnet

    subnets = {}
    route_tables = {}
    count = 0
    az_count = 0
    subnet_count = len(azs) * len(subnet_layers)
    tgw_attachments = {}
    for az in azs:
        tgw_attachments[az] = {}
        subnets[az] = {}
        route_tables[az] = {}
        for subnet_layer in subnet_layers:
            # Create a Subnet for each subnet_layer / az
            subnet = template.add_resource(
                ec2.Subnet(
                    "Subnet" + az.capitalize() + subnet_layer.capitalize(),
                    VpcId=Ref(vpc),
                    CidrBlock=Select(count, Cidr(Ref(vpc_cidr), subnet_count, subnet_bits)),
                    AvailabilityZone=Select(az_count % 2, GetAZs(Ref("AWS::Region"))),
                    Tags=std_tags + Tags(Name=Join("-", [
                        Ref(asi), Ref(env), Ref(security_zone), "Tenant", "subnet" + az.capitalize(),
                        subnet_layer.capitalize()]))
                )
            )
            subnets[az][subnet_layer] = subnet

            # Create a Subnet Route table for each subnet
            rtb = template.add_resource(
                ec2.RouteTable(
                    "RouteTable" + az.capitalize() + subnet_layer.capitalize(),
                    VpcId=Ref(vpc),
                    Tags=std_tags + Tags(Name=Join("-", [
                        Ref(asi), Ref(env), Ref(security_zone), "Tenant", "rtetbl" + az.capitalize(),
                        subnet_layer.capitalize()]))
                )
            )
            route_tables[az][subnet_layer] = rtb

            # Associate Route table with subnet
            rtb_assoc = template.add_resource(
                ec2.SubnetRouteTableAssociation(
                    "rtbAssoc" + az.capitalize() + subnet_layer.capitalize(),
                    SubnetId=Ref(subnet),
                    RouteTableId=Ref(rtb)
                )
            )

            # Transit Gateway Attach to first subnets in subnet_layers (should be 'web')
            if subnet_layer == subnet_layers[0]:
                tgw_attach = template.add_resource(
                    ec2.TransitGatewayAttachment(
                        "tgwAttach" + az.capitalize() + subnet_layer.capitalize(),
                        SubnetIds=[Ref(subnet)],
                        # transitVpc-tgwId-web
                        TransitGatewayId=ImportValue(Join("-", [Ref(palo_stack), "tgwId", Ref(security_zone)])),
                        VpcId=Ref(vpc)
                    )
                )
                tgw_attachments[az] = tgw_attach

            # Add Default Route to all route tables to the transit gateway attachment
            default_cidr = '0.0.0.0/0'
            rte = template.add_resource(
                cfn_custom_resources.VpcTgwRouteLambda(
                    # Add destination to the resource name so anytime the destination cidr changes,
                    # The route will be deleted/created (there is no update route method in aws api)
                    "DefaultSubnetRoute" + az.capitalize() + subnet_layer.capitalize()
                    + default_cidr.replace(".", "x").replace("/", "y"),
                    # cfn-lambda-helpers-prd-VpcTgwRoute
                    ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRoute"])),
                    DestinationCidrBlock=default_cidr,
                    # transitVpc-tgwId-web
                    TransitGatewayId=ImportValue(Join("-", [Ref(palo_stack), "tgwId", Ref(security_zone)])),
                    RouteTableId=Ref(rtb),
                    DependsOn=tgw_attachments[az].title
                )
            )
            count += 1

        # For each AZ, create route in the transit VPC Web Subnet(s) to this VPC cidr via Web Transit Gateway
        # This is only necessary for "web" VPCs so Conditional is_web_zone is checked in each of the following

        # Get attributes from the current AZ web subnet in the transit vpc
        transit_vpc_web_subnet_attrs = template.add_resource(
            cfn_custom_resources.VpcSubnetAttributesLambda(
                "transitVpcSubnetAttrsWeb" + az.capitalize(),
                # cfn-lambda-helpers-prd-VpcSubnetAttributes
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcSubnetAttributes"])),
                Condition=is_web_zone,
                # export example: transitVpc-subnetIdAWeb
                SubnetId=ImportValue(Join("-", [Ref(palo_stack), "subnetId" + az.capitalize() + "Web"])),
            )
        )
        # Generate the IP address of the AWS router in the current AZ transit vpc web subnet
        web_subnet_router_ip = template.add_resource(
            cfn_custom_resources.SubnetIpGeneratorLambda(
                "transitVpcSubnetRouterIpWeb" + az.capitalize(),
                # export example: cfn-lambda-helpers-prd-SubnetIpGenerator
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "SubnetIpGenerator"])),
                Condition=is_web_zone,
                CidrBlock=GetAtt(transit_vpc_web_subnet_attrs, "CidrBlock"),
                Position=1
            )
        )
        # Create a static route in the transit VPC current AZ web subnet to this VPC
        transit_vpc_route = template.add_resource(
            cfn_custom_resources.VpcTgwRouteLambda(
                "TransitRouteWeb" + az.capitalize() +
                # Since we dont know the cidr until runtime, create a random resource name so that the
                # route is always updated
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
                # cfn-lambda-helpers-prd-VpcTgwRoute
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRoute"])),
                Condition=is_web_zone,
                DestinationCidrBlock=Ref(vpc_cidr),
                # transitVpc-tgwId-web
                TransitGatewayId=ImportValue(Join("-", [Ref(palo_stack), "tgwId", Ref(security_zone)])),
                # transitVpc-routeTableAWeb
                RouteTableId=ImportValue(Join("-", [Ref(palo_stack), "routeTable" + az.capitalize() + "Web"])),
                DependsOn=tgw_attachments[az].title
            )
        )
        # Create a static route in the transit VPC current AZ Palo to this vpc
        palo_static_route = template.add_resource(
            cfn_palo_resources.PaloStaticRoute(
                "paloStaticRouteWeb" + az.capitalize() +
                # Since we dont know the vpc cidr until runtime, create a random resource name so that the
                # route is always updated
                ''.join(random.choices(string.ascii_uppercase + string.digits, k=10)),
                # palo-lambda-helpers-prd-PaloStaticRoute
                ServiceToken=ImportValue(Join("-", [Ref(palo_helpers_stack), "PaloStaticRoute"])),
                Condition=is_web_zone,
                # transitVpc-paloAmgtIp
                PaloMgtIp=ImportValue(Join("-", [Ref(palo_stack), "palo" + az.capitalize() + "mgtIp"])),
                PaloUser=Ref(palo_user),
                PaloPassword=Ref(palo_pass),
                VirtualRouter=Ref(palo_virtual_router),
                DestinationCidrBlock=Ref(vpc_cidr),
                NextHopIp=GetAtt(web_subnet_router_ip, "IpAddress"),
                Interface=Ref(palo_web_interface)
            )
        )
        az_count += 1

    #############################
    # SSM

    # Endpoints Security Group
    sg_ssm = template.add_resource(
        ec2.SecurityGroup(
            "ssnSg",
            GroupDescription="Ssm Security group",
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), Ref(security_zone), "Tenant", "ssm", "secgrp"]))
        )
    )
    template.add_resource(
        ec2.SecurityGroupIngress(
            "sgRuleSsm443",
            IpProtocol='tcp',
            FromPort=443,
            ToPort=443,
            CidrIp="0.0.0.0/0",
            GroupId=GetAtt(sg_ssm, "GroupId"),
        )
    )

    # SSM Endpoints
    # Create a list of all web layer subnet Refs for the ssm endpoints
    endpoint_subnet_refs = []
    for az in subnets:
        endpoint_subnet_refs.append(Ref(subnets[az][subnet_layers[0]]))

    for ep_type in ["ec2", "ec2messages", "ssm", "ssmmessages"]:
        endpoint = template.add_resource(
            ec2.VPCEndpoint(
                "endpoint" + ep_type.capitalize(),
                VpcId=Ref(vpc),
                ServiceName=Join(".", ["com.amazonaws", Ref("AWS::Region"), ep_type]),
                VpcEndpointType="Interface",
                SecurityGroupIds=[Ref(sg_ssm)],
                PrivateDnsEnabled=True,
                SubnetIds=endpoint_subnet_refs,
            )
        )

    role_ssm_inst = template.add_resource(
        iam.Role(
            "ssmInstanceRole",
            RoleName=Join("-", ["ssmInstanceRole", Ref("AWS::StackName")]),
            Path="/",
            AssumeRolePolicyDocument=PolicyDocument(
                Statement=[
                    Statement(
                        Effect=Allow,
                        Action=[Action("sts", "AssumeRole")],
                        Principal=Principal("Service", "ec2.amazonaws.com")
                    )
                ]
            ),
            ManagedPolicyArns=["arn:aws:iam::aws:policy/service-role/AmazonEC2RoleforSSM"]
        )
    )

    # SSM Instance Profile
    profile_ssm_inst = template.add_resource(
        iam.InstanceProfile(
            "ssmInstanceProfile",
            Roles=[Ref(role_ssm_inst)]
        )
    )

    ##############################
    # S3 Endpoint
    endpoint_route_table_refs = []
    for az in route_tables:
        for subnet_layer in subnet_layers:
            endpoint_route_table_refs.append(Ref(route_tables[az][subnet_layer]))
    s3_endpoint = template.add_resource(
        ec2.VPCEndpoint(
            "s3endpoint",
            VpcId=Ref(vpc),
            RouteTableIds=endpoint_route_table_refs,
            ServiceName=Join("", ["com.amazonaws.", Ref("AWS::Region"), ".s3"]),
            VpcEndpointType="Gateway",
            PolicyDocument=PolicyDocument(
                Statement=[
                    Statement(
                        Action=[Action("*")],
                        Effect=Allow,
                        Resource=["*"],
                        Principal=Principal("*")
                    )
                ]
            )
        )
    )

    #############################
    # EC2 test Instance
    for az in azs[0]:
        test_inst = template.add_resource(
            ec2.Instance(
                "testInst",
                ImageId=Ref(ami_amzn2),
                InstanceType='t3.micro',
                #SecurityGroupIds=[Ref(sg_bastion)],
                #KeyName=Ref(palo_ssh_keyname),
                IamInstanceProfile=Ref(profile_ssm_inst),
                SubnetId=Ref(subnets[az][subnet_layers[0]]),
                Tags=std_tags + Tags(Name=Join("-", [
                    Ref(asi), Ref(env), Ref(security_zone), "Tenant", subnet_layers[0], az.capitalize(), "inst"]))
            )
        )
        return template


def show_template():
    ########################################
    # Create the template file

    template = get_template()
    print(template.to_yaml())
