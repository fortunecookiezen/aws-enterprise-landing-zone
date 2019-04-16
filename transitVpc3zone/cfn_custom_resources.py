from troposphere.cloudformation import AWSCustomObject


# Custom Resources
class VpcTgwRouteLambda(AWSCustomObject):
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'DestinationCidrBlock': (str, True),
        'TransitGatewayId': (str, True),
        'RouteTableId': (str, True)
    }


class VpcTgwAttributesLambda(AWSCustomObject):
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'TransitGatewayId': (str, True),
    }


class VpcSubnetAttributesLambda(AWSCustomObject):
    """
    Returns attributes for a subnet given a SubnetId in event
    'AvailabilityZone', 'AvailabilityZoneId', 'AvailableIpAddressCount', 'CidrBlock', 'DefaultForAz',
    'MapPublicIpOnLaunch', 'State', 'SubnetId', 'VpcId', 'OwnerId', 'AssignIpv6AddressOnCreation',
    'Ipv6CidrBlockAssociationSet', 'SubnetArn'
    """
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'SubnetId': (str, True),
    }


class SubnetIpGeneratorLambda(AWSCustomObject):
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'CidrBlock': (str, True),
        'Position': (int, True),
    }
