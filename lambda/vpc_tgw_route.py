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

So, we have to ship own copy of boto3 in the zip file
"""

import boto3
import cfnresponse
import helpers

from botocore.exceptions import ClientError

logger = helpers.get_console_logger()


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
    result = ec2client.create_route(
        DestinationCidrBlock=DestinationCidrBlock,
        TransitGatewayId=TransitGatewayId,
        RouteTableId=RouteTableId
    )
    return result


def delete_tgw_route(DestinationCidrBlock, RouteTableId):
    """
    :param DestinationCidrBlock: (String) The IPv4 CIDR address block used for the destination match.
    :param RouteTableId: (String) The ID of the route table for the route.
    :return: (Boolean) Returns true if the request succeeds; otherwise, it returns an error.
    """
    ec2client = boto3.client("ec2")
    logger.info(f"Deleting Route DestinationCidrBlock: {DestinationCidrBlock}, RouteTableId: {RouteTableId}")
    result = ec2client.delete_route(
        DestinationCidrBlock=DestinationCidrBlock,
        RouteTableId=RouteTableId
    )
    return result


def lambda_handler(event, context):
    logger.debug(f"event: {event}")
    logger.debug(f"context: {context}")
    logger.info(f"RequestType: {event['RequestType']}")

    # CREATE
    if event['RequestType'] == 'Create':
        result = create_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            TransitGatewayId=event['ResourceProperties']['TransitGatewayId'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )

    # UPDATE
    elif event['RequestType'] == 'Update':
        # There is no update_route method. We'll delete it, then create it.
        try:
            result = delete_tgw_route(
                DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
                RouteTableId=event['ResourceProperties']['RouteTableId']
            )
        except ClientError as e:
            # If the route doesnt exist, it will throw a ClientError except. Log it and keep moving
            logger.error(e)

        result = create_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            TransitGatewayId=event['ResourceProperties']['TransitGatewayId'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )

    # DELETE
    elif event['RequestType'] == 'Delete':
        result = delete_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )

    # Send Result back to Cloudformation
    logger.info(f"{event['RequestType']} Route result - {result}")
    if result['Return'] != True:
        response = cfnresponse.FAILED
    else:
        response = cfnresponse.SUCCESS
    cfnresponse.send(event, context, response, result, "CustomResourcePhysicalID")
