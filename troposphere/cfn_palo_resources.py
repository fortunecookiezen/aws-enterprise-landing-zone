from troposphere.cloudformation import AWSCustomObject


# Custom Resources
class PaloStaticRoute(AWSCustomObject):
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'DestinationCidrBlock': (str, True),
        'VirtualRouter': (str, True),
        'NextHopIp': (str, True),
        'PaloMgtIp': (str, True),
        'PaloUser': (str, True),
        'PaloPassword': (str, True)
    }

