from troposphere import Template, Parameter, ImportValue, Ref
import cfn_palo_resources
import cfn_custom_resources


pvt_cidrs = ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']
azs = ['a', 'b']
azs = ['a']


def get_template():
    template = Template()
    template.description = "Static Routes for Palo Alto"

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

    # TODO: This needs to be dynamic based on the cidr of the subnet
    palo_nexthop_ip = template.add_parameter(
        Parameter(
            "paloNextHopIp",
            Description="IP of the router on the Trusted Subnet",
            Type="String",
            MinLength=1,
            MaxLength=255,
            Default="10.250.1.1"
        )
    )

    template.add_parameter_to_group(lambda_helpers_stack, group_name)
    for az in azs:
        subnet_attr = template.add_resource(
            cfn_custom_resources.VpcSubnetAttributesLambda(
                "subnetAttrs" + "Trusted" + az.capitalize(),
                ServiceToken=ImportValue(Join("-", [Ref(lambda_helpers_stack), "VpcSubnetAttributes"])),
                SubnetId=ImportValue(transit_vpc_stack + "subnetId" + az.capitalize() + "Trusted"),
            )
        )
        for pvt_cidr in pvt_cidrs:
            palo_route = template.add_resource(
                cfn_palo_resources.PaloStaticRoute(
                    "paloRoute" + az.capitalize() + pvt_cidr.replace(".", "x").replace("/", "y"),
                    ServiceToken=ImportValue(Join("-", [Ref(palo_helpers_stack), "VpcSubnetAttributes"])),
                    DestinationCidrBlock=pvt_cidr,
                    VirtualRouter=palo_virtual_router,
                    NextHopIp=palo_nexthop_ip,  # TODO: Make this dynamic from the subnet_attr
                    PaloMgtIp=ImportValue(palo_helpers_stack + "-palo" + az.capitalize() + "mgtIp"),
                    PaloUser=palo_user,
                    PaloPassword=palo_pass,
                )
            )
