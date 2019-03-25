from troposphere import Parameter, Output, Template
from troposphere import Cidr, Join, GetAtt, Ref, Tags, GetAZs, Select, ImportValue
from troposphere import FindInMap
import troposphere.ec2 as ec2
from troposphere.cloudformation import AWSCustomObject
import boto3
import logging
import sys

template = Template()
template.description = "Transit VPC with Palo Alto Firewalls"

azs = ("a", "b")
zones = ("untrusted", "trusted", "webdmz", "web")
pvt_cidrs = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
palo_ami_name = "PA-VM-AWS-8.0.13-8736f7a7-35b2-4e03-a8eb-6a749a987428-*"

# TODO: update this... more dynamically if possible
web_cidrs = ["192.168.0.0/24"]
#web_cidrs.append("192.168.1.0/24")


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
# Parameters - Environment
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

# Build Palo Alto AMI Map for all ec2 regions starting with "us-"
image_map = {}
for region in boto3.client("ec2").describe_regions()['Regions']:
    if region['RegionName'][:3] == "us-":
        ec2client = boto3.client("ec2", region_name=region['RegionName'])
        try:
            ami = ec2client.describe_images(
                Filters=[{"Name": "name", "Values": [palo_ami_name]}])['Images'][0]['ImageId']
            image_map[region['RegionName']] = {"AMI": ami}
        except IndexError as e:
            logging.info(f"No palo image found for region: {region['RegionName']}")
palo_ami_map = template.add_mapping('paloAmiMap', image_map)

# Amazon Linux 2 AMI
ami_amzn2 = template.add_parameter(
    Parameter(
        "amznLinux2Ami",
        Type="AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>",
        Default="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
    )
)

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

#############################
# Tags we'll apply to all resources

std_tags = Tags(
    Project=Ref(asi),
    Environment=Ref(env),
    Owner=Ref(owner)
)

################################
# VPC

vpc = template.add_resource(
    ec2.VPC(
        "vpc",
        CidrBlock=Ref(vpc_cidr),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "vpc"]))
    )
)

################################
# Subnets

subnets = {}
sn_count = len(azs) * len(zones)
count = 0
az_count = 0
for az in azs:
    subnets[az] = {}
    for zone in zones:
        subnet = template.add_resource(
            ec2.Subnet(
                "subnet" + zone.capitalize() + az.capitalize(),
                # Create /24 subnets (32 - 8 = 24)
                CidrBlock=Select(count, Cidr(Ref(vpc_cidr), sn_count, 8)),
                AvailabilityZone=Select(az_count % 2, GetAZs(Ref("AWS::Region"))),
                VpcId=Ref(vpc),
                Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "sn", zone, az]))
            )
        )
        subnets[az][zone] = subnet
        count += 1
    az_count += 1

################################
# Transit Gateways

# For each zone that we want a transit gateway
tgws = {}
for zone in ["trusted", "web"]:
    # Create a transit Gateway
    tgw = ec2.TransitGateway(
        "tgw" + zone.capitalize(),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tgw", zone]))
    )
    template.add_resource(tgw)
    tgws[zone] = tgw

    # Attach transit the gateway to all subnets (azs) that have this zone
    subnet_ids = []
    for az in azs:
        subnet_ids.append(Ref(subnets[az][zone]))
    tgw_attach = template.add_resource(
        ec2.TransitGatewayAttachment(
            "tgwAttach" + zone.capitalize(),
            SubnetIds=subnet_ids,
            TransitGatewayId=Ref(tgw),
            VpcId=Ref(vpc)
        )
    )


##################################
# Palo Instances

palo_nics = {}
for az in azs:
    palo_nics[az] = {}
    palo_inst = ec2.Instance(
        "paloInst" + az.capitalize(),
        ImageId=Ref(ami_amzn2),
        InstanceType="c4.xlarge",
        #ImageId=FindInMap("paloAmiMap", Ref("AWS::Region"), "AMI"),
        #InstanceType="c4.xlarge",
        # SecurityGroups="", # TODO add security group for mgt interface
        # KeyName="", # TODO add ssh key
        # UserData="", # TODO userdata for palo bootstrap
        SourceDestCheck=False,
        SubnetId=Ref(subnets[az]["trusted"]),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az, "rt"]))
    )
    template.add_resource(palo_inst)
    # Add an additional network interface for each zone
    nicIndex = 1
    for zone in zones:
        palo_nic = template.add_resource(
            ec2.NetworkInterface(
                "paloNic" + zone.capitalize() + az.capitalize(),
                SubnetId=Ref(subnets[az][zone]),
                # SecurityGroups="", # TODO add security group for mgt interface
            )
        )
        palo_nics[az][zone] = palo_nic
        pal_nic_attach = template.add_resource(
            ec2.NetworkInterfaceAttachment(
                "paloNicAttach" + zone.capitalize() + az.capitalize(),
                NetworkInterfaceId=Ref(palo_nic),
                InstanceId=Ref(palo_inst),
                DeviceIndex=nicIndex
            )
        )
        nicIndex += 1

####################################
# Internet Gateway

igw = ec2.InternetGateway(
    "igw",
    Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "igw"]))
)
template.add_resource(igw)

# Attach Internet Gateway to VPC
igw_attach = ec2.VPCGatewayAttachment(
    "igwAttach",
    InternetGatewayId=Ref(igw),
    VpcId=Ref(vpc)
)
template.add_resource(igw_attach)


#####################################
# Untrusted Zone - Routing

zone = "untrusted"

# Route Table
rtb = ec2.RouteTable(
    "RouteTable" + zone.capitalize(),
    VpcId=Ref(vpc),
    Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, "rt"]))
)
template.add_resource(rtb)

# Default Route to Internet Gateway
rte = ec2.Route(
    "DefaultRoute" + zone.capitalize(),
    DestinationCidrBlock="0.0.0.0/0",
    GatewayId=Ref(igw),
    RouteTableId=Ref(rtb)
)
template.add_resource(rte)

# Associate Route Table to Subnet
for az in azs:
    rtb_assoc = ec2.SubnetRouteTableAssociation(
        "RouteTableAssoc" + zone.capitalize() + az.capitalize(),
        RouteTableId=Ref(rtb),
        SubnetId=Ref(subnets[az][zone])
    )
    template.add_resource(rtb_assoc)

#############################
# WebDMZ Zone - Routing
zone = "webdmz"

for az in azs:
    # Route Table
    rtb = ec2.RouteTable(
        "RouteTable" + zone.capitalize() + az.capitalize(),
        VpcId=Ref(vpc),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az, "rt"]))
    )
    template.add_resource(rtb)

    # Default Route to Internet Gateway
    rte = ec2.Route(
        "DefaultRoute" + zone.capitalize() + az.capitalize(),
        DestinationCidrBlock="0.0.0.0/0",
        GatewayId=Ref(igw),
        RouteTableId=Ref(rtb)
    )
    template.add_resource(rte)

    # Route to Private Cidrs via Palo Nic in this zone
    count = 0
    for pvt_cidr in pvt_cidrs:
        rte = ec2.Route(
            "Route" + str(count) + zone.capitalize() + az.capitalize(),
            DestinationCidrBlock=pvt_cidr,
            NetworkInterfaceId=Ref(palo_nics[az][zone]),
            RouteTableId=Ref(rtb)
        )
        template.add_resource(rte)
        count += 1

    # Associate Route Table to Subnet
    rtb_assoc = ec2.SubnetRouteTableAssociation(
        "RouteTableAssoc" + zone.capitalize() + az.capitalize(),
        RouteTableId=Ref(rtb),
        SubnetId=Ref(subnets[az][zone])
    )
    template.add_resource(rtb_assoc)

#############################
# Web Zone - Routing
zone = "web"

for az in azs:
    # Route Table
    rtb = ec2.RouteTable(
        "RouteTable" + zone.capitalize() + az.capitalize(),
        VpcId=Ref(vpc),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az,  "rt"]))
    )
    template.add_resource(rtb)

    # Default Route to Palo Nic in this zone
    rte = ec2.Route(
        "DefaultRoute" + zone.capitalize() + az.capitalize(),
        DestinationCidrBlock="0.0.0.0/0",
        NetworkInterfaceId=Ref(palo_nics[az][zone]),
        RouteTableId=Ref(rtb)
    )
    template.add_resource(rte)

    # Route to Web Cidrs via Tgw Interface in this zone
    count = 0
    for cidr in web_cidrs:
        rte = template.add_resource(
            VpcTgwRouteLambda(
                "Route" + zone.capitalize() + az.capitalize()
                # Include string-ified Cidr in the route resource name because there is no route_update() method in AWS.
                # Doing this forces delete/create anytime the route's cidr changes
                + cidr.replace('.', 'x').replace('/', 'z'),
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRouteLambdaArn"])),
                DestinationCidrBlock=cidr,
                TransitGatewayId=Ref(tgws[zone]),
                RouteTableId=Ref(rtb),
                DependsOn=["tgwAttach" + zone.capitalize()]
            )
        )
        count += 1

    # Associate Route Table to subnet
    rtb_assoc = ec2.SubnetRouteTableAssociation(
        "RouteTableAssoc" + zone.capitalize() + az.capitalize(),
        RouteTableId=Ref(rtb),
        SubnetId=Ref(subnets[az][zone])
    )
    template.add_resource(rtb_assoc)

#############################
# Trusted Zone - Routing
zone = "trusted"

for az in azs:
    # Route Table
    rtb = ec2.RouteTable(
        "RouteTable" + zone.capitalize() + az.capitalize(),
        VpcId=Ref(vpc),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az, "rt"]))
    )
    template.add_resource(rtb)

    # Default Route Palo Interface
    rte = ec2.Route(
        "DefaultRoute" + zone.capitalize() + az.capitalize(),
        DestinationCidrBlock="0.0.0.0/0",
        NetworkInterfaceId=Ref(palo_nics[az][zone]),
        RouteTableId=Ref(rtb)
    )
    template.add_resource(rte)

    # Route to Private Cidrs via Palo Nic in this zone
    count = 0
    for cidr in pvt_cidrs:
        rte = template.add_resource(
            VpcTgwRouteLambda(
                "Route" + zone.capitalize() + az.capitalize()
                # Include Cidr in resource name because there is no route_update() method in AWS.
                # Doing this forces delete/create every time the route's cidr changes
                + cidr.replace('.', 'x').replace('/', 'z'),
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRouteLambdaArn"])),
                DestinationCidrBlock=cidr,
                TransitGatewayId=Ref(tgws[zone]),
                RouteTableId=Ref(rtb),
                DependsOn=["tgwAttach" + zone.capitalize()]
            )
        )
        count += 1

    # Associate Route Table to Subnet
    rtb_assoc = ec2.SubnetRouteTableAssociation(
        "RouteTableAssoc" + zone.capitalize() + az.capitalize(),
        RouteTableId=Ref(rtb),
        SubnetId=Ref(subnets[az][zone])
    )
    template.add_resource(rtb_assoc)


# Create the output file
output = template.to_yaml()
outfile = sys.modules['__main__'].__file__.replace('.py', '.yaml')
fh = open(outfile, 'w')
logging.info(f"writing output to {outfile}")
fh.write(output)
