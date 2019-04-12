from troposphere import Template, Parameter, ImportValue, Ref, Join, GetAtt
import cfn_palo_resources
import cfn_custom_resources


azs = ['a', 'b']
azs = ['a']

trusted_palo_interface = 'ethernet1/2'
pvt_cidrs = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']


def get_template():
    template = Template()
    template.description = "Static Routes for Palo Alto Transit VPC"

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

    palo_helpers_stack = template.add_parameter(
        Parameter(
            "PaloHelpersStack",
            Description="Name of palo Helpers CloudFormation stack",
            Type="String",
            MinLength=1,
            MaxLength=255,
            AllowedPattern="^[a-zA-Z][-a-zA-Z0-9]*$",
        )
    )

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

    transit_vpc_stack = template.add_parameter(
        Parameter(
            "TransitVpcStack",
            Description="Name of transit VPC CloudFormation stack",
            Type="String",
            MinLength=1,
            MaxLength=255,
            AllowedPattern="^[a-zA-Z][-a-zA-Z0-9]*$",
        )
    )

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

    for az in azs:
        subnet_attr = template.add_resource(
            cfn_custom_resources.VpcSubnetAttributesLambda(
                "subnetAttrs" + "Trusted" + az.capitalize(),
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcSubnetAttributes"])),
                SubnetId=ImportValue(Join("-", [Ref(transit_vpc_stack), "subnetId" + az.capitalize() + "Trusted"])),
            )
        )
        subnet_router_ip = template.add_resource(
            cfn_custom_resources.SubnetIpGeneratorLambda(
                "subnetRouterIp" + "Trusted" + az.capitalize(),
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "SubnetIpGenerator"])),
                CidrBlock=GetAtt(subnet_attr, "CidrBlock"),
                Position=1
            )
        )
        for pvt_cidr in pvt_cidrs:
            palo_route = template.add_resource(
                cfn_palo_resources.PaloStaticRoute(
                    "paloRoute" + az.capitalize() + pvt_cidr.replace(".", "x").replace("/", "y"),
                    ServiceToken=ImportValue(Join("-", [Ref(palo_helpers_stack), "VpcSubnetAttributes"])),
                    DestinationCidrBlock=pvt_cidr,
                    VirtualRouter=Ref(palo_virtual_router),
                    NextHopIp=GetAtt(subnet_router_ip, "IpAddress"),
                    PaloMgtIp=ImportValue(Join("-", [Ref(transit_vpc_stack), "palo" + az.capitalize() + "mgtIp"])),
                    PaloUser=Ref(palo_user),
                    PaloPassword=Ref(palo_pass),
                )
            )
    return template
