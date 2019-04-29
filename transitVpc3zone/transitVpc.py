from troposphere import Template, Parameter, Output, Export
from troposphere import Cidr, Join, GetAtt, Ref, Tags, GetAZs, Select, ImportValue, Base64
from troposphere import FindInMap
import troposphere.ec2 as ec2
import troposphere.iam as iam
import boto3
import logging
import sys
import string
from awacs.aws import Action, Allow, PolicyDocument, Principal, Statement

import cfn_custom_resources


def get_template():
    template = Template()
    template.description = "Transit VPC with Palo Alto Firewalls"

    azs = ['a', 'b']
    azs = ['a']

    create_bastion = True
    pvt_cidrs = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
    palo_ami_name = "PA-VM-AWS-9.*.*-8736f7a7-35b2-4e03-a8eb-6a749a987428-*"
    zones = ["dmz", "trusted", "web"]

    if create_bastion:
        zones.append("bastion")

    # TODO: update this... more dynamically if possible
    web_cidrs = []
    #web_cidrs.append("192.168.0.0/24")
    #web_cidrs.append("192.168.1.0/24")


    #######################################
    # Parameters - Environment Configuration

    group_name = "Environment Configuration"

    asi = template.add_parameter(
        Parameter(
            "ASI",
            Description="asi - must be lower-case, limit 4 characters",
            Type="String",
            MinLength=2,
            MaxLength=5,
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

    # Refer to lambda helpers stack (with function arns in output)
    lambda_helpers_stack = template.add_parameter(
        Parameter(
            "LambdaHelpersStack",
            Description="Name of lambda Helpers CloudFormation stack",
            Type="String",
            MinLength=1,
            MaxLength=255,
            AllowedPattern="^[a-zA-Z][-a-zA-Z0-9]*$",
        )
    )
    template.add_parameter_to_group(lambda_helpers_stack, group_name)

    #################################
    # Parameters - Palo configuration

    group_name = "Palo Configuration"

    palo_instance_type = template.add_parameter(
        Parameter(
            "paloInstanceType",
            Type="String",
            Description="Type of Instance for Palo VMs",
            Default="c5.xlarge"
        )
    )
    template.add_parameter_to_group(vpc_cidr, group_name)

    palo_mgt_trusted_cidr = template.add_parameter(
        Parameter(
            "paloMgtTrustedCidr",
            Type="String",
            Description="Cidr range that we trust to access the palo management interface",
            Default='0.0.0.0/0'
        )
    )
    template.add_parameter_to_group(vpc_cidr, group_name)

    palo_ssh_keyname = template.add_parameter(
        Parameter(
            "paloSshKeyName",
            ConstraintDescription='must be the name of an existing EC2 KeyPair.',
            Description='Name of an existing EC2 KeyPair to enable SSH access to the instance',
            Type='AWS::EC2::KeyPair::KeyName',
        )
    )
    template.add_parameter_to_group(vpc_cidr, group_name)

    palo_bootstrap_bucket = template.add_parameter(
        Parameter(
            "paloBootstrapBucket",
            Description="the name of the bucket in this region that contains the palo bootstrap data",
            Type="String"
        )
    )
    template.add_parameter_to_group(vpc_cidr, group_name)

    ##############################
    # AMI Maps

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

    vpc = template.add_resource(
        ec2.VPC(
            "vpc",
            CidrBlock=Ref(vpc_cidr),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "transit", "vpc"]))
        )
    )

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

    ################################
    # Subnets

    subnets = {}
    subnet_attrs = {}
    sn_count = len(azs) * len(zones)
    count = 0
    az_count = 0
    for az in azs:
        subnets[az] = {}
        subnet_attrs[az] = {}
        for zone in zones:
            map_public_ip_on_launch = False
            if zone == "dmz" or zone == "bastion":
                map_public_ip_on_launch = True
            subnet = template.add_resource(
                ec2.Subnet(
                    "subnet" + zone.capitalize() + az.capitalize(),
                    # Create /24 subnets (32 - 8 = 24)
                    CidrBlock=Select(count, Cidr(Ref(vpc_cidr), sn_count, 8)),
                    AvailabilityZone=Select(az_count % 2, GetAZs(Ref("AWS::Region"))),
                    VpcId=Ref(vpc),
                    MapPublicIpOnLaunch=map_public_ip_on_launch,
                    Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "sn", zone, az]))
                )
            )
            subnets[az][zone] = subnet
            # Create a subnet attributes custom object (so that we can get the derived subnet cidr)
            subnet_attr = template.add_resource(
                cfn_custom_resources.VpcSubnetAttributesLambda(
                    "subnetAttrs" + zone.capitalize() + az.capitalize(),
                    ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcSubnetAttributes"])),
                    SubnetId=Ref(subnet),
                )
            )
            subnet_attrs[az][zone] = subnet_attr
            count += 1
        az_count += 1

    ################################
    # Transit Gateways

    # For each backend zone create a transit gateway
    tgws = {}
    for zone in ["trusted", "web"]:
        # Create a transit Gateway
        tgw = template.add_resource(
            ec2.TransitGateway(
                "tgw" + zone.capitalize(),
                Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tgw", zone]))
            )
        )
        tgws[zone] = tgw

        # Create a transit Gateway Attributes custom resource
        tgw_attrs = template.add_resource(
            cfn_custom_resources.VpcTgwAttributesLambda(
                "tgwAttrs" + zone.capitalize(),
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwAttributes"])),
                TransitGatewayId=Ref(tgw),
            )
        )

        # Create a transit gateway route table
        #tgw_rte_tble = template.add_resource(
        #    ec2.TransitGatewayRouteTable(
        #        "tgwRteTable" + zone.capitalize(),
        #        TransitGatewayId=Ref(tgw),
        #        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "tgwRteTbl", zone]))
        #    )
        #)

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

        # Propagate network interface to route table
        #tgw_prop = template.add_resource(
        #    ec2.TransitGatewayRouteTablePropagation(
        #        "tgwPropagate" + zone.capitalize(),
        #        TransitGatewayAttachmentId=Ref(tgw_attach),
        #        TransitGatewayRouteTableId=Ref(tgw_rte_tble)
        #    )
        #)

        # Add a default route to the transit gateway's default Route Table to the palo vpc
        tgw_route = template.add_resource(
            ec2.TransitGatewayRoute(
                "tgwDefaultRoute" + zone.capitalize(),
                DestinationCidrBlock="0.0.0.0/0",
                TransitGatewayAttachmentId=Ref(tgw_attach),
                TransitGatewayRouteTableId=GetAtt(tgw_attrs, 'AssociationDefaultRouteTableId')
            )
        )

    ###############################
    # Security Groups

    # Palo Management Interface Security Group
    sg_palo_mgt = template.add_resource(
        ec2.SecurityGroup(
            "paloMgtSg",
            GroupDescription="Palo Management Interface Security group",
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "palomgt", "secgrp"]))
        )
    )
    for port in ['22', '443']:
        template.add_resource(
            ec2.SecurityGroupIngress(
                "sgRulePaloMgt" + str(port),
                IpProtocol='tcp',
                FromPort=port,
                ToPort=port,
                CidrIp=Ref(palo_mgt_trusted_cidr),
                GroupId=GetAtt(sg_palo_mgt, "GroupId"),
            )
        )
    template.add_resource(
        ec2.SecurityGroupIngress(
            "sgRulePaloMgtIcmp",
            IpProtocol='icmp',
            FromPort=0,
            ToPort=0,
            CidrIp=Ref(palo_mgt_trusted_cidr),
            GroupId=GetAtt(sg_palo_mgt, "GroupId"),
            )
    )

    # Palo Network Interface Security Group
    sg_palo_if = template.add_resource(
        ec2.SecurityGroup(
            "paloIfSg",
            GroupDescription="Palo Network Interface Security group",
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "paloif", "secgrp"]))
        )
    )
    template.add_resource(
        ec2.SecurityGroupIngress(
            "sgRulePaloIf" + str(port),
            IpProtocol='-1',
            FromPort=0,
            ToPort=65535,
            GroupId=GetAtt(sg_palo_if, "GroupId"),
            CidrIp='0.0.0.0/0'
        )
    )

    # Bastion Security Group
    if create_bastion:
        sg_bastion = template.add_resource(
            ec2.SecurityGroup(
                "bastionSg",
                GroupDescription="Bastion Host Security group",
                VpcId=Ref(vpc),
                Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "bastion", "secgrp"]))
            )
        )
        for port in ["22"]:
            template.add_resource(
                ec2.SecurityGroupIngress(
                    "sgRuleBastionIf" + str(port),
                    IpProtocol='tcp',
                    FromPort=port,
                    ToPort=port,
                    GroupId=GetAtt(sg_bastion, "GroupId"),
                    CidrIp='0.0.0.0/0'
                )
            )

    ##########################
    # Palo Instance Profile

    role_palo_inst = template.add_resource(
        iam.Role(
            "paloInstanceRole",
            RoleName=Join("-", ["paloInstanceRole", Ref("AWS::StackName")]),
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
            Policies=[
                iam.Policy(
                    PolicyName=Join("-", ["paloEc2Policy", Ref("AWS::StackName")]),
                    PolicyDocument=PolicyDocument(
                        Statement=[
                            Statement(
                                Effect=Allow,
                                Action=[
                                    Action("s3", "List*"),
                                    Action("s3", "Get*"),
                                    Action("s3", "Head*"),
                                ],
                                Resource=[
                                    Join("", ["arn:aws:s3:::", Ref(palo_bootstrap_bucket)]),
                                    Join("", ["arn:aws:s3:::", Ref(palo_bootstrap_bucket), "/*"])
                                ]
                            ),
                            Statement(
                                Effect=Allow,
                                Action=[Action("cloudwatch", "PutMetricData")],
                                Resource=["*"]
                            )
                        ]
                    )
                )
            ]
        )
    )

    profile_palo_inst = template.add_resource(
        iam.InstanceProfile(
            "paloInstanceProfile",
            Roles=[Ref(role_palo_inst)]
        )
    )

    ##################################
    # Palo Instances

    palo_nics = {}
    for az in azs:
        palo_nics[az] = {}
        palo_inst = ec2.Instance(
            "paloInst" + az.capitalize(),
            ImageId=FindInMap("paloAmiMap", Ref("AWS::Region"), "AMI"),
            InstanceType=Ref(palo_instance_type),
            SecurityGroupIds=[Ref(sg_palo_mgt)],
            KeyName=Ref(palo_ssh_keyname),
            UserData=Base64(Join("", ["vmseries-bootstrap-aws-s3bucket=", Ref(palo_bootstrap_bucket)])),
            IamInstanceProfile=Ref(profile_palo_inst),
            DependsOn=profile_palo_inst.title,
            SubnetId=Ref(subnets[az]["trusted"]),
            # Set IP address to 11th IP in subnet Cidr
            # cidr function cant return a /32
            #PrivateIpAddress=Select(11, Cidr(GetAtt(subnet_attrs[az]['trusted'], 'CidrBlock'), 20, 1)),
            SourceDestCheck=True,
            # Define root ebs volume manually so that we can set DeleteOnTermination = True
            BlockDeviceMappings=[
                ec2.BlockDeviceMapping(
                    DeviceName="/dev/xvda",
                    Ebs=ec2.EBSBlockDevice(
                        VolumeSize=60,
                        VolumeType="gp2",
                        DeleteOnTermination=True
                    )
                )
            ],
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "palo", az.capitalize(), "inst"]))
        )
        template.add_resource(palo_inst)
        # Add an additional network interface for each zone except bastion zone
        nic_index = 1
        for zone in zones:
            if zone != "bastion":
                palo_nic = template.add_resource(
                    ec2.NetworkInterface(
                        "paloNic" + zone.capitalize() + az.capitalize(),
                        SubnetId=Ref(subnets[az][zone]),
                        SourceDestCheck=False,
                        GroupSet=[GetAtt(sg_palo_if, "GroupId")],
                        DependsOn=palo_inst.title,
                        # Set IP address to 10th IP in subnet Cidr
                        # cidr function cant return a /32
                        #PrivateIpAddress=Select(10, Cidr(GetAtt(subnet_attrs[az][zone], 'CidrBlock'), 20, 0)),
                        Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az, "eni"]))
                    )
                )
                palo_nics[az][zone] = palo_nic
                palo_nic_attach = template.add_resource(
                    ec2.NetworkInterfaceAttachment(
                        "paloNicAttach" + zone.capitalize() + az.capitalize(),
                        NetworkInterfaceId=Ref(palo_nic),
                        InstanceId=Ref(palo_inst),
                        DeviceIndex=nic_index,
                        # Force nics to attach to instance in order so that they get os ethX numbers consistently
                        DependsOn=last_nic_attach.title if nic_index > 1 else palo_inst.title
                    )
                )
                nic_index += 1
                last_nic_attach = palo_nic_attach
                if zone == "dmz":
                    # Create an elastic IP for the public interface
                    palo_eip = template.add_resource(
                        ec2.EIP(
                            "paloEip" + zone.capitalize() + az.capitalize(),
                            Domain="vpc",
                            DependsOn=igw.title
                        )
                    )
                    # Associate the public EIP with the dmz nic
                    palo_eip_assoc = template.add_resource(
                        ec2.EIPAssociation(
                            "paloEipAssoc" + zone.capitalize() + az.capitalize(),
                            AllocationId=GetAtt(palo_eip, "AllocationId"),
                            NetworkInterfaceId=Ref(palo_nic)
                        )
                    )

    ###################################
    # Bastion Instance

    if create_bastion:
        az = azs[0]
        zone = "bastion"
        bastion_inst = template.add_resource(
            ec2.Instance(
                "bastionInst" + az.capitalize(),
                ImageId=Ref(ami_amzn2),
                InstanceType='t3.micro',
                SecurityGroupIds=[Ref(sg_bastion)],
                IamInstanceProfile=Ref(profile_palo_inst),
                KeyName=Ref(palo_ssh_keyname),
                SubnetId=Ref(subnets[az][zone]),
                Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "bastion", az.capitalize(), "inst"]))
            )
        )

    #############################
    # Routing - DMZ Zone
    route_tables = {}
    zone = "dmz"

    for az in azs:
        route_tables[az] = {}
        # Route Table
        rtb = ec2.RouteTable(
            "RouteTable" + zone.capitalize() + az.capitalize(),
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az, "rt"]))
        )
        template.add_resource(rtb)
        route_tables[az][zone] = rtb

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
    # Routing - Web Zone
    zone = "web"

    for az in azs:
        # Route Table
        rtb = ec2.RouteTable(
            "RouteTable" + zone.capitalize() + az.capitalize(),
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az,  "rt"]))
        )
        template.add_resource(rtb)
        route_tables[az][zone] = rtb

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
                cfn_custom_resources.VpcTgwRouteLambda(
                    "Route" + zone.capitalize() + az.capitalize()
                    # Include string-ified Cidr in the resource name because there is no route_update() method in AWS.
                    # Doing this forces delete/create anytime the route's cidr changes
                    + cidr.replace('.', 'x').replace('/', 'z'),
                    ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRoute"])),
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
    # Routing - Trusted Zone
    zone = "trusted"

    for az in azs:
        # Route Table
        rtb = ec2.RouteTable(
            "RouteTable" + zone.capitalize() + az.capitalize(),
            VpcId=Ref(vpc),
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), zone, az, "rt"]))
        )
        template.add_resource(rtb)
        route_tables[az][zone] = rtb

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
                cfn_custom_resources.VpcTgwRouteLambda(
                    "Route" + zone.capitalize() + az.capitalize()
                    # Include Cidr in resource name because there is no route_update() method in AWS.
                    # Doing this forces delete/create every time the route's cidr changes
                    + cidr.replace('.', 'x').replace('/', 'z'),
                    ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcTgwRoute"])),
                    DestinationCidrBlock=cidr,
                    TransitGatewayId=Ref(tgws[zone]),
                    RouteTableId=Ref(rtb),
                    DependsOn=["tgwAttach" + zone.capitalize()]
                )
            )
            count += 1

        # Route to Web Cidrs via Tgw Interface in this zone
        count = 0
        for cidr in web_cidrs:
            rte = template.add_resource(
                ec2.Route(
                    "Route" + zone.capitalize() + az.capitalize()
                    # Include string-ified Cidr in the route resource name because there is no route_update() method in AWS.
                    # Doing this forces delete/create anytime the route's cidr changes
                    + cidr.replace('.', 'x').replace('/', 'z'),
                    DestinationCidrBlock=cidr,
                    NetworkInterfaceId=Ref(palo_nics[az][zone]),
                    RouteTableId=Ref(rtb),
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

    #############################
    # Routing - Bastion Zone

    if create_bastion:
        zone = "bastion"

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

            # Associate Route Table to Subnet
            rtb_assoc = ec2.SubnetRouteTableAssociation(
                "RouteTableAssoc" + zone.capitalize() + az.capitalize(),
                RouteTableId=Ref(rtb),
                SubnetId=Ref(subnets[az][zone])
            )
            template.add_resource(rtb_assoc)

    ##################################
    # s3 endpoint in VPC

    # Get a list of ec2.RouteTable object names in template
    route_table_names = list(filter(lambda x: type(template.resources[x]) is ec2.RouteTable, template.resources))

    s3_endpoint = template.add_resource(
        ec2.VPCEndpoint(
            "s3endpoint",
            VpcId=Ref(vpc),
            RouteTableIds=list(map(lambda x: Ref(template.resources[x]), route_table_names)),
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

    ##############################
    # Outputs

    # export the bastion public IP
    if create_bastion:
        template.add_output(
            Output(
                "bastionPublicIp",
                Description="Public IP of Bastion instance",
                Value=GetAtt(bastion_inst, "PublicIp")
            )
        )

    # export the vpc id
    template.add_output(
        Output(
            "vpcId",
            Description="The ID of the transit VPC",
            Value=Ref(vpc),
            Export=Export(
                Join('-', [
                    Ref("AWS::StackName"),
                    "vpcId"
                ])
            )
        )
    )

    for az in azs:
        for zone in zones:
            # Export the route table Ids
            if zone in route_tables[az]:
                template.add_output(
                    Output(
                        "routeTableId" + az.capitalize() + zone.capitalize(),
                        Description=f"The Route Table ID for az: {az}, zone: {zone}",
                        Value=Ref(route_tables[az][zone]),
                        Export=Export(
                            Join('-', [
                                Ref("AWS::StackName"),
                                "routeTable" + az.capitalize() + zone.capitalize(),
                                ])
                        )

                    )
                )
            # Export all the subnet IDs
            if zone in subnets[az]:
                template.add_output(
                    Output(
                        "subnetId" + az.capitalize() + zone.capitalize(),
                        Description=f"The Subnet ID for az: {az}, zone: {zone}",
                        Value=Ref(subnets[az][zone]),
                        Export=Export(
                            Join('-', [
                                Ref("AWS::StackName"),
                                "subnetId" + az.capitalize() + zone.capitalize(),
                            ])
                        )

                    )
                )

        # Export the palo management IPs
        template.add_output(
            Output(
                "palo" + az.capitalize() + "mgtIp",
                Description="Management IP of Palo" + az.capitalize(),
                Value=GetAtt("paloInst" + az.capitalize(), "PrivateIp"),
                Export=Export(
                    Join('-', [
                        Ref("AWS::StackName"),
                        "palo" + az.capitalize() + "mgtIp",
                    ])
                )
            )
        )

    # export the transit gateway IDs for trusted and web transit gateways
    for zone in ["trusted", "web"]:
        template.add_output(
            Output(
                "tgwId" + zone.capitalize(),
                Description="TransitGatewayId for security zone: " + zone,
                Value=Ref(tgws[zone]),
                Export=Export(Join("-", [Ref("AWS::StackName"), "tgwId", zone]))
            )
        )

    return template


def write_template(template):
    ########################################
    # Create the template file

    output = template.to_yaml()
    outfile = sys.modules['__main__'].__file__.replace('.py', '.yaml')
    fh = open(outfile, 'w')
    logging.info(f"writing output to {outfile}")
    fh.write(output)
