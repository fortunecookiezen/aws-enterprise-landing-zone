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
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'SubnetId': (str, True),
    }
