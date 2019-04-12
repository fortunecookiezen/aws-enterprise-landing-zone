# vpc_tgw_attributes
"""
This lambda gets more details about a transit gateway than the cfn resource returns.
Specifically, it returns the main route table for a tgw so that routes can be added to it
"""

from crhelper import CfnResource
# Initialise the aws cfn helper, all inputs are optional, this example shows the defaults
helper = CfnResource(json_logging=False, log_level='DEBUG', boto_level='CRITICAL')

try:
    # Init code goes here
    import boto3
    import moo_helpers
    logger = moo_helpers.get_console_logger()


except Exception as e:
    helper.init_failure(e)


@helper.create
def create(event, context):
    """
    returns attributes about transit gateway. Removes Tags and merges Options into main dict
    'TransitGatewayId', 'TransitGatewayArn', 'State', 'OwnerId', 'Description',
    'AmazonSideAsn', 'AutoAcceptSharedAttachments', 'DefaultRouteTableAssociation', 'AssociationDefaultRouteTableId',
    'DefaultRouteTablePropagation', 'PropagationDefaultRouteTableId', 'VpnEcmpSupport', 'DnsSupport'
    :param event:
    :param context:
    :return:
    """
    logger.info("Got Create")
    transit_gateway_id = event['ResourceProperties']['TransitGatewayId']
    logger.info(f"requesting attributes for transit gateway id: {transit_gateway_id}")
    client = boto3.client("ec2")
    transit_gateways = client.describe_transit_gateways(
        Filters=[
            {'Name': 'transit-gateway-id', 'Values': [transit_gateway_id]}
        ]
    )
    for transit_gateway in transit_gateways['TransitGateways']:
        # Remove datetime object that is not json serializable and provides no value to cfn resource
        del transit_gateway['CreationTime']
        # Remove tags which are a dict and provide no value to cfn resource
        del transit_gateway['Tags']
        # separate options dict
        options = transit_gateway.pop('Options')
        # return combined list of attributes
        helper.Data.update({**transit_gateway, **options})


@helper.update
def update(event, context):
    logger.info("Got Update, doing nothing")
    # If the update resulted in a new resource being created, return an id for the new resource. CloudFormation will send
    # a delete event with the old id when stack update completes


@helper.delete
def delete(event, context):
    logger.info("Got Delete, doing nothing")
    # Delete never returns anything. Should not fail if the underlying resources are already deleted. Desired state.


def handler(event, context):
    helper(event, context)
