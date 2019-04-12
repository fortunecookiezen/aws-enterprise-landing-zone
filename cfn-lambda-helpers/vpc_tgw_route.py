"""
This module creates an EC2 VPC route to AWS transit gateway as it is not supported in cloud formation
as of this writing (2019-03-22)
https://www.reddit.com/r/aws/comments/7ad7el/cloudformation_experts_how_do_i_associate_aws/
https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-route.html

Note, that as of this writing 2019-03-23, the AWS lambda execution environment runs
boto3 version 1.7.74 
https://docs.aws.amazon.com/lambda/latest/dg/current-supported-versions.html

And that version doesnt support transitgateway vpc routes (which is the purpose of this function).
https://boto3.amazonaws.com/v1/documentation/api/1.7.74/reference/services/ec2.html#EC2.Client.create_route

But the latest version (1.9.120) does support transitgateway routes in vpc
https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.create_route

So, we have to ship own copy of boto3 in the zip file (in requirements.txt)
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


def tgw_route_exists(route_table_id, transit_gateway_id, destination_cidr_block):
    """
    Checks to see if a route with these parameters already exists
    :param string route_table_id:
    :param string transit_gateway_id:
    :param string destination_cidr_block:
    :return: True is route exists, else False
    """
    ec2client = boto3.client("ec2")
    route_tables = ec2client.describe_route_tables(
        Filters=[{'Name': 'route-table-id', 'Values': [route_table_id]}]
    )
    for route_table in route_tables['RouteTables']:
        if 'Routes' in route_table:
            for route in route_table['Routes']:
                if 'DestinationCidrBlock' in route and route['DestinationCidrBlock'] == destination_cidr_block:
                    if 'TransitGatewayId' in route and route['TransitGatewayId'] == transit_gateway_id:
                        return True
    return False


@helper.create
def create(event, context):
    logger.info("Got Create")
    destination_cidr_block = event['ResourceProperties']['DestinationCidrBlock']
    transit_gateway_id = event['ResourceProperties']['TransitGatewayId']
    route_table_id = event['ResourceProperties']['RouteTableId']
    logger.info(
        f"Creating Route DestinationCidrBlock: {destination_cidr_block}, TransitGatewayId: {transit_gateway_id} "
        f"RouteTableId: {route_table_id}")
    if tgw_route_exists(route_table_id, transit_gateway_id, destination_cidr_block):
        logger.warning(f"Specified route already exists. Not creating")
        return
    ec2client = boto3.client("ec2")
    ec2client.create_route(
        DestinationCidrBlock=destination_cidr_block,
        TransitGatewayId=transit_gateway_id,
        RouteTableId=route_table_id
    )


@helper.update
def update(event, context):
    # Technically there is no update of a route. A new resource gets created here and cfn will delete the old one
    logger.info("Got Update")
    destination_cidr_block = event['ResourceProperties']['DestinationCidrBlock']
    transit_gateway_id = event['ResourceProperties']['TransitGatewayId']
    route_table_id = event['ResourceProperties']['RouteTableId']
    logger.info(
        f"Updating Route DestinationCidrBlock: {destination_cidr_block}, TransitGatewayId: {transit_gateway_id} "
        f"RouteTableId: {route_table_id}")
    if tgw_route_exists(route_table_id, transit_gateway_id, destination_cidr_block):
        logger.warning(f"Identical route already exists. Not updating")
        return
    ec2client = boto3.client("ec2")
    ec2client.create_route(
        DestinationCidrBlock=destination_cidr_block,
        TransitGatewayId=transit_gateway_id,
        RouteTableId=route_table_id
    )


@helper.delete
def delete(event, context):
    logger.info("Got Delete")
    destination_cidr_block = event['ResourceProperties']['DestinationCidrBlock']
    route_table_id = event['ResourceProperties']['RouteTableId']
    transit_gateway_id = event['ResourceProperties']['TransitGatewayId']
    logger.info(f"Deleting Route DestinationCidrBlock: {destination_cidr_block}, RouteTableId: {route_table_id}")
    if not tgw_route_exists(route_table_id, transit_gateway_id, destination_cidr_block):
        logger.warning(f"Route does not exist. Not deleting")
        return
    ec2client = boto3.client("ec2")
    ec2client.delete_route(
        DestinationCidrBlock=destination_cidr_block,
        RouteTableId=route_table_id
    )


def handler(event, context):
    helper(event, context)
