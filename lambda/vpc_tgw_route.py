"""
This module creates an EC2 VPC route to AWS transit gateway as it is not supported in cloud formation
as of this writing (2019-03-22)
https://www.reddit.com/r/aws/comments/7ad7el/cloudformation_experts_how_do_i_associate_aws/
https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-ec2-route.html
"""
import boto3
from .logger import get_console_logger

logger = get_console_logger()


def create_tgw_route(DestinationCidrBlock, TransitGatewayId, RouteTableId):
    """
    Creates a route to a transit gateway
    :param DestinationCidrBlock: (String) The IPv4 CIDR address block used for the destination match.
    :param TransitGatewayId: (String) The ID of a transit gateway.
    :param RouteTableId: (String) The ID of the route table for the route.
    :return: (Boolean) Returns true if the request succeeds; otherwise, it returns an error.
    """
    ec2client = boto3.client("ec2")
    logger.info(f"Creating Route DestinationCidrBlock: {DestinationCidrBlock}, TransitGatewayId: {TransitGatewayId} "
                f"RouteTableId: {RouteTableId}")
    return ec2client.create_route(
        DestinationCidrBlock=DestinationCidrBlock,
        TransitGatewayId=TransitGatewayId,
        RouteTableId=RouteTableId
    )


def delete_tgw_route(DestinationCidrBlock, RouteTableId):
    """
    :param DestinationCidrBlock: (String) The IPv4 CIDR address block used for the destination match.
    :param RouteTableId: (String) The ID of the route table for the route.
    :return: (Boolean) Returns true if the request succeeds; otherwise, it returns an error.
    """
    ec2client = boto3.client("ec2")
    logger.info(f"Deleting Route DestinationCidrBlock: {DestinationCidrBlock}, TransitGatewayId: {TransitGatewayId} "
                f"RouteTableId: {RouteTableId}")
    return ec2client.delete_route(
        DestinationCidrBlock=DestinationCidrBlock,
        RouteTableId=RouteTableId
    )


def lambda_handler(event, context):
    logger.debug(f"event: {event}")
    logger.debug(f"context: {context}")
    logger.info(f"RequestType: {event['RequestType']}")

    if event['RequestType'] == 'Create':
        return create_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            TransitGatewayId=event['ResourceProperties']['TransitGatewayId'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )
    elif event['RequestType'] == 'Update':
        delete_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )
        return create_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            TransitGatewayId=event['ResourceProperties']['TransitGatewayId'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )
    elif event['RequestType'] == 'Delete':
        return delete_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )
    else:
        raise ValueError(f"Unexpected event RequestType {event['RequestType']}")
