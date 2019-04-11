# subnet_ip_generator.py
"""
This lambda is designed to get a single IP address from a subnet given a specific position
This is nessesary because the cloudformation Fn::Cidr cannot generate a single IP.
This is useful if you need to get the 1st IP (i.e. the router) from a derived cidr range
"""

try:
    # Init code goes here
    from crhelper import CfnResource
    import ipaddress
    import moo_helpers

    logger = moo_helpers.get_console_logger()

    # Initialise the aws cfn helper, all inputs are optional, this example shows the defaults
    helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')

except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    """
    Creates an IP address at a specific position in a subnet
    takes a string CidrBlock (i.e. 10.250.0.0/24)
    and a integer position (i.e. 10)
    and returns the IP address for that position (10.250.0.10)
    :param event:
    :param context:
    :return:
    """
    logger.info("Got Create")
    cidr_block = event['ResourceProperties']['CidrBlock']
    position = event['ResourceProperties']['Position']
    logger.info(f"CidrBlock: {cidr_block}")
    logger.info(f"Position: {position}")
    ip_address = str(ipaddress.ip_network(cidr_block)[int(position)])
    logger.info(f"Returning IpAddress: {ip_address}")
    helper.Data.update({"IpAddress": ip_address})


@helper.update
def update(event, context):
    logger.info("Got Update")
    cidr_block = event['ResourceProperties']['CidrBlock']
    position = event['ResourceProperties']['Position']
    logger.info(f"CidrBlock: {cidr_block}")
    logger.info(f"Position: {position}")
    ip_address = str(ipaddress.ip_network(cidr_block)[int(position)])
    logger.info(f"Returning IpAddress: {ip_address}")
    helper.Data.update({"IpAddress": ip_address})


@helper.delete
def delete(event, context):
    logger.info("Got Delete. Doing nothing")


def handler(event, context):
    helper(event, context)
