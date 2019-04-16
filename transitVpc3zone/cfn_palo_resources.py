from troposphere.cloudformation import AWSCustomObject


# Custom Resources
class PaloStaticRoute(AWSCustomObject):
    """
    Manages a palo static route
    :prop string ServiceToken: ARN of the function that handles this Custom resource
    :prop string PaloMgtIp: The IP or host name of the palo management interface
    :prop string PaloUser: The administrative user name for palo management operations
    :prop string PaloPass: The administrative users password
    :prop string VirtualRouter: the name of the virtual router to install the route (default: 'default')
    :prop string DestinationCidrBlock: string the network/ip that we want to route (ex. '10.250.0.0/24')
    :prop string NextHopIp: The IP address of the router to whom we should pass destination traffic (ex. '20.250.0.1')
    :prop string Interface: The physical interface on the palo to send the traffic (ex. ethernet1/1)
    """
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'PaloMgtIp': (str, True),
        'PaloUser': (str, True),
        'PaloPassword': (str, True),
        'VirtualRouter': (str, False),  # default = 'default'
        'DestinationCidrBlock': (str, True),
        'NextHopIp': (str, True),
        'Interface': (str, True),
    }


class PaloSecurityPolicy(AWSCustomObject):
    """
    Manages a palo alto Security Policy (aka firewall rule)
    Any optional value not set defaults to ['any']
    :prop string ServiceToken: ARN of the function that handles this Custom resource
    :prop string PaloMgtIp: The IP or host name of the palo management interface
    :prop string PaloUser: The administrative user name for palo management operations
    :prop string PaloPass: The administrative users password
    :prop string VsysName: The name of the palo virtual system to perform operations (default: 'vsys1')
    :prop string RuleName: The name of the palo rule to create (max 63 chars).
    :prop string RuleDescription: The description of the palo rule to create (max 1023 chars).
    :prop list SourceCidrs: A list of cidrs from which we will match traffic (default: ['any'])
                                                                            (ex. ['10.250.0.0/24', '10.250.1.1'])
    :prop list SourceZones: A list of palo security zones from which we will match traffic (default: ['any'])
                                                                            (ex. ['trusted', 'web'])
    :prop list DestinationCidrs: A list of cidrs to which we will match traffic to go (default: ['any'])
    :prop list DestinationZone: A list of palo security zones to which we will match traffic to go (default: ['any'])
    :prop list Applications: A list of allowed palo predefined applications to match (default: [] allows all apps)
                              see https://applipedia.paloaltonetworks.com/  (ex. ['google-hangouts', 'slack']
    :prop list Services: A list of allowed palo predefined services to match (default: ['application-default'])
    :prop string Action: [allow|deny] whether to allow or deny matching traffic. (default: 'allow')
    """
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'PaloUser': (str, True),
        'PaloPassword': (str, True),
        'PaloMgtIp': (str, True),
        'RuleName': (str, True),
        'VsysName': (str, False),           # default 'vsys1'
        'SourceCidrs': (list, False),       # default ['any'] (match any source cidr)
        'SourceZones': (list, False),       # default ['any'] (match any source zone)
        'DestinationCidrs': (list, False),  # default ['any'] (match any destination cidr)
        'DestinationZones': (list, False),  # default ['any'] (match any destination zone)
        'Applications': (list, False),      # default [] (match all applications)
        'Services': (list, False),          # default ['application-default'] (any port/protocol)
        'Users': (list, False),             # default ['any']
        'Action': (str, False),             # default 'allow' (allows matching traffic)
    }


class PaloService(AWSCustomObject):
    """
    Manages a palo alto Service Object.
    Describes the destination protocol and ports for an application service
    Used in a palo alto security policy
    :prop string ServiceToken: ARN of the function that handles this Custom resource
    :prop string PaloMgtIp: The IP or host name of the palo management interface
    :prop string PaloUser: The administrative user name for palo management operations
    :prop string PaloPass: The administrative users password
    :prop string VsysName: The name of the palo virtual system to perform operations (default: 'vsys1')
    :prop string ServiceName: The name of the service (less than 64 chars)
    :prop string ServiceDescription: The description of the service (less than 1024 chars)
    :prop string DestinationPorts: The destination ports (ex. '80,443,1024-8000')
    :prop string Protocol: The protocol for the service [tcp|udp|stcp] (default: 'tcp')
    """
    resource_type = "Custom::CustomResource"
    props = {
        'ServiceToken': (str, True),
        'PaloUser': (str, True),
        'PaloPassword': (str, True),
        'PaloMgtIp': (str, True),
        'VsysName': (str, False),  # default 'vsys1'
        'ServiceName': (str, True),
        'ServiceDescription': (str, False),  # default = ''
        'DestinationPorts': (str, True),  # ex, '80,1024-1025'
        'Protocol': (str, True),  # tcp, udp or stcp
    }

