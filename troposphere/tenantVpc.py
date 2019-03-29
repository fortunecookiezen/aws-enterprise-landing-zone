from troposphere import Parameter, Output, Template
from troposphere import Cidr, Join, GetAtt, Ref, Tags, GetAZs, Select, ImportValue, Base64
from troposphere import FindInMap
import troposphere.ec2 as ec2
import troposphere.iam as iam
from troposphere.cloudformation import AWSCustomObject
import boto3
import logging
import sys
from awacs.aws import Action, Allow, PolicyDocument, Principal, Statement

template = Template()

######################################
# Lambda Helper

# Custom Resource
# TODO: add this to a local module that gets imported.
class VpcTgwRouteLambda(AWSCustomObject):
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'DestinationCidrBlock': (str, True),
        'TransitGatewayId': (str, True),
        'RouteTableId': (str, True)
    }


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
        Description="Stack Name of the deployed Palo Stack",
        Default="stack-01transitVpc"
    )
)
template.add_parameter_to_group(vpc_cidr, group_name)

zone = template.add_parameter(
    Parameter(
        "securityZone",
        Type="String",
        Description="Security zone to which we should connect the vpc",
        Default="trusted"
    )
)
template.add_parameter_to_group(vpc_cidr, group_name)

# Refer to lambda helpers stack (with function arns in output)
lambda_helpers_stack = template.add_parameter(
    Parameter(
        "LambdaHelpersStack",
        Description="Name of lambda Helpers CloudFormation stack",
        Type="String",
        MinLength=1,
        MaxLength=255,
        AllowedPattern="^[a-zA-Z][-a-zA-Z0-9]*$",
        Default="stack-lambdaHelpers"
    )
)
template.add_parameter_to_group(lambda_helpers_stack, group_name)


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

#############################
# Tags we'll apply to all resources

std_tags = Tags(
    Project=Ref(asi),
    Environment=Ref(env),
    Owner=Ref(owner)
)

#############################
# VPC

vpc = template.add_resource(
    ec2.VPC(
        "vpc",
        CidrBlock=Ref(vpc_cidr),
        EnableDnsHostnames=True,
        EnableDnsSupport=True,
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tenant", "vpc"]))
    )
)

#############################
# Subnet

subnet = template.add_resource(
    ec2.Subnet(
        "subnet",
        VpcId=Ref(vpc),
        CidrBlock=Ref(vpc_cidr),
        AvailabilityZone=Select(0, GetAZs(Ref("AWS::Region"))),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tenant", "subnet"]))
    )
)


# Transit Gateway Attach to subnet
tgw_attach = template.add_resource(
    ec2.TransitGatewayAttachment(
        "tgwAttach",
        SubnetIds=[Ref(subnet)],
        TransitGatewayId=ImportValue(Join("-", [Ref(palo_stack), "tgwId", Ref(zone)])),
        VpcId=Ref(vpc)
    )
)

# Subnet Route table
rtb = template.add_resource(
    ec2.RouteTable(
        "RouteTable",
        VpcId=Ref(vpc),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tenant", "rt"]))
    )
)

# Associate Route table with subnet
rtb_assoc = template.add_resource(
    ec2.SubnetRouteTableAssociation(
        "rtbAssoc",
        SubnetId=Ref(subnet),
        RouteTableId=Ref(rtb)
    )
)

# Add Default Route
cidr = "0.0.0.0/0"
rte = template.add_resource(
    VpcTgwRouteLambda(
        "Route"
        # Include Cidr in resource name because there is no route_update() method in AWS.
        # Doing this forces delete/create every time the route's cidr changes
        + cidr.replace('.', 'x').replace('/', 'z'),
        ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRouteLambdaArn"])),
        DestinationCidrBlock=cidr,
        TransitGatewayId=ImportValue(Join("-", [Ref(palo_stack), "tgwId", Ref(zone)])),
        RouteTableId=Ref(rtb),
        DependsOn=tgw_attach.title
    )
)


#############################
# SSM

# Endpoints Security Group
sg_ssm = template.add_resource(
    ec2.SecurityGroup(
        "ssnSg",
        GroupDescription="Ssm Security group",
        VpcId=Ref(vpc),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "ssm", "secgrp"]))
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
for ep_type in ["ec2", "ec2messages", "ssm", "ssmmessages"]:
    endpoint = template.add_resource(
        ec2.VPCEndpoint(
            "endpoint" + ep_type.capitalize(),
            VpcId=Ref(vpc),
            ServiceName=Join(".", ["com.amazonaws", Ref("AWS::Region"), ep_type]),
            VpcEndpointType="Interface",
            SecurityGroupIds=[Ref(sg_ssm)],
            PrivateDnsEnabled=True,
            SubnetIds=[Ref(subnet)],
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
s3_endpoint = template.add_resource(
    ec2.VPCEndpoint(
        "s3endpoint",
        VpcId=Ref(vpc),
        RouteTableIds=[Ref(rtb)],
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
# EC2 Instance

test_inst = template.add_resource(
    ec2.Instance(
        "testInst",
        ImageId=Ref(ami_amzn2),
        InstanceType='t3.micro',
        #SecurityGroupIds=[Ref(sg_bastion)],
        #KeyName=Ref(palo_ssh_keyname),
        IamInstanceProfile=Ref(profile_ssm_inst),
        SubnetId=Ref(subnet),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "test", "inst"]))
    )
)


########################################
# Create the template file

output = template.to_yaml()
outfile = sys.modules['__main__'].__file__.replace('.py', '.yaml')
fh = open(outfile, 'w')
logging.info(f"writing output to {outfile}")
fh.write(output)
