"""
This module creates returns the Cidr String from a deployed EC2::Subnet
as of this writing (2019-04-09), the EC2::Subnet resource does not return the Cidr as an attibrute
"""


try:
    # Init code goes here
    from crhelper import CfnResource
    import boto3
    import moo_helpers

    logger = moo_helpers.get_console_logger()

    # Initialise the aws cfn helper, all inputs are optional, this example shows the defaults
    helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')
except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    """
    Returns attributes for a subnet given a SubnetId in event
    'AvailabilityZone', 'AvailabilityZoneId', 'AvailableIpAddressCount', 'CidrBlock', 'DefaultForAz',
    'MapPublicIpOnLaunch', 'State', 'SubnetId', 'VpcId', 'OwnerId', 'AssignIpv6AddressOnCreation',
    'Ipv6CidrBlockAssociationSet', 'SubnetArn'
    :param event:
    :param context:
    :return:
    """
    logger.info("Got Create")
    subnet_id = event['ResourceProperties']['SubnetId']
    logger.info(f"Requesting attrs for subnet id: {subnet_id}")
    ec2client = boto3.client("ec2")
    response_data = ec2client.describe_subnets(
        Filters=[
            {'Name': 'subnet-id', 'Values': [subnet_id]}
        ],
    )['Subnets'][0]
    # To add response data update the helper.Data dict
    helper.Data.update(response_data)


@helper.update
def update(event, context):
    logger.info("Got Update, doing nothing")


@helper.delete
def delete(event, context):
    logger.info("Got Delete, doing nothing")
    # Delete never returns anything. Should not fail if the underlying resources are already deleted. Desired state.


def handler(event, context):
    helper(event, context)
