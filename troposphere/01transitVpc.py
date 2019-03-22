from troposphere import Parameter, Output, Template
from troposphere import Cidr, Join, GetAtt, Ref, Tags, GetAZs, Select
from troposphere import FindInMap
import troposphere.ec2 as ec2
import boto3
import logging

template = Template()
template.description = "Transit VPC with Palo Alto Firewalls"

azs = ("a", "b")
zones = ("untrusted", "trusted", "webdmz", "web")
pvt_cidrs = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
palo_ami_name = "PA-VM-AWS-8.0.13-8736f7a7-35b2-4e03-a8eb-6a749a987428-*"

# TODO: update this... more dynamically if possible
web_cidrs = ["192.168.0.0/24"]

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

vpcCidr = template.add_parameter(
    Parameter(
        "vpccidr",
        Type="String",
        Description="Cidr Range for Transit VPC - must be /21 or larger",
        AllowedPattern='^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\/(1[6-9]|2[0-8]))$'
    )
)
template.add_parameter_to_group(vpcCidr, group_name)

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

#############################
# Tags we'll apply to all resources

std_tags = Tags(
    Project=Ref(asi),
    Environment=Ref(env),
    Owner=Ref(owner)
)

################################
# VPC

vpc = ec2.VPC(
    "vpc",
    CidrBlock=Ref(vpcCidr),
    Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "vpc"]))
)
template.add_resource(vpc)

################################
# Subnets

subnets = {}
count = 1
for az in azs:
    subnets[az] = {}
    for zone in zones:
        subnet = ec2.Subnet(
            "sn" + zone.capitalize() + az.capitalize(),
            CidrBlock=Cidr(Ref(vpcCidr), count, 3),
            AvailabilityZone=Select(count % 2, GetAZs()),
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "sn", zone, az]))
        )
        template.add_resource(subnet)
        subnets[az][zone] = subnet
        count += count

################################
# Transit Gateways

# For each zone that we want a transit gateway
tgws = {}
for zone in ["trusted", "web"]:
    # Create a transit Gateway
    tgw = ec2.TransitGateway(
        "Tgw" + zone,
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tgw", zone]))
    )
    template.add_resource(tgw)
    tgws[zone] = tgw

    # Attach transit the gateway to all subnets (azs) that have this zone
    subnet_ids = []
    for az in azs:
        subnet_ids.append(Ref(subnets[az][zone]))
    tgw_attach = ec2.TransitGatewayAttachment(
        "tgwAttach" + zone.capitalize(),
        SubnetIds=subnet_ids,
        TransitGatewayId=Ref(tgw),
        VpcId=Ref(vpc)
    )
    template.add_resource(tgw_attach)


##################################
# Palo Instances

palo_nics = {}
for az in azs:
    palo_nics[az] = {}
    palo_inst = ec2.Instance(
        "paloInst" + az.capitalize(),
        ImageId=Ref(ami_amzn2),
        InstanceType="t2.micro",
        #ImageId=FindInMap("paloAmiMap", Ref("AWS::Region"), "AMI"),
        #InstanceType="c4.xlarge",
        # SecurityGroups="", # TODO add security group for mgt interface
        # KeyName="", # TODO add ssh key
        # UserData="", # TODO userdata for palo bootstrap
        SourceDestCheck=False,
        SubnetId=Ref(subnets[az]["trusted"]),
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone + az + "-rt"]))
    )
    template.add_resource(palo_inst)
    # Add an additional network interface for each zone
    for zone in zones:
        palo_nic = ec2.NetworkInterface(
            "paloNic" + zone.capitalize() + az.capitalize(),
            SubnetId=Ref(subnets[az][zone]),
            # SecurityGroups="", # TODO add security group for mgt interface
        )
        palo_nics[az][zone] = palo_nic
        template.add_resource(palo_nic)

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
    Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone + "-rt"]))
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
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone + az + "-rt"]))
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
            "PvtRoute" + str(count) + zone.capitalize() + az.capitalize(),
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
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone + az + "-rt"]))
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
    for web_cidr in web_cidrs:
        rte = ec2.Route(
            "PvtRoute" + str(count) + zone.capitalize() + az.capitalize(),
            DestinationCidrBlock=web_cidr,
            GatewayId=Ref(tgws[zone]),
            RouteTableId=Ref(rtb)
        )
        template.add_resource(rte)
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
        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone + az + "-rt"]))
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
    for pvt_cidr in pvt_cidrs:
        rte = ec2.Route(
            "PvtRoute" + str(count) + zone.capitalize() + az.capitalize(),
            DestinationCidrBlock=pvt_cidr,
            GatewayId=Ref(tgws[zone]),
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


# Yaml doesnt like the Cidr(GetAtt(Ref(vpc), xxx), x, x) function
#print(template.to_yaml()) # Just pipe output to | yq -y .
print(template.to_json())
