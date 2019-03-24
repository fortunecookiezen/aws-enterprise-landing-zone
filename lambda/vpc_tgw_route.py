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

logger = helpers.get_console_logger()


def create_tgw_route(DestinationCidrBlock, TransitGatewayId, RouteTableId):
    """
    Creates a route to a transit gateway
    :param DestinationCidrBlock: (String) The IPv4 CIDR address block used for the destination match.
    :param TransitGatewayId: (String) The ID of a transit gateway.
    :param RouteTableId: (String) The ID of the route table for the route.
    :return: (Boolean) Returns true if the request succeeds; otherwise, it returns an error.
    """
    logger.info(f"Creating Route DestinationCidrBlock: {DestinationCidrBlock}, TransitGatewayId: {TransitGatewayId} "
                f"RouteTableId: {RouteTableId}")
    result = {}
    try:
        ec2client = boto3.client("ec2")
        result = ec2client.create_route(
            DestinationCidrBlock=DestinationCidrBlock,
            TransitGatewayId=TransitGatewayId,
            RouteTableId=RouteTableId
        )
    except Exception as e:
        logger.error(e)
        result['Return'] = False
        result['Error'] = e
    return result


def delete_tgw_route(DestinationCidrBlock, RouteTableId):
    """
    :param DestinationCidrBlock: (String) The IPv4 CIDR address block used for the destination match.
    :param RouteTableId: (String) The ID of the route table for the route.
    :return: (Boolean) Returns true if the request succeeds; otherwise, it returns an error.
    """
    logger.info(f"Deleting Route DestinationCidrBlock: {DestinationCidrBlock}, RouteTableId: {RouteTableId}")
    result = {}
    try:
        ec2client = boto3.client("ec2")
        result = ec2client.delete_route(
            DestinationCidrBlock=DestinationCidrBlock,
            RouteTableId=RouteTableId
        )
        # delete_route does not provide a result["Return"] attribute like the create_route method. So create it here
        if result['ResponseMetadata']['HTTPStatusCode'] == 200:
            result['Return'] = True
        else:
            result['Return'] = False
    except Exception as e:
        logger.error(e)
        result['Return'] = False
        result['Error'] = e
    return result


def lambda_handler(event, context):
    logger.info(f"event: {event}")
    logger.info(f"context: {context}")
    logger.info(f"RequestType: {event['RequestType']}")

    result = {'Return': False}

    # CREATE
    if event['RequestType'] == 'Create':
        result = create_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            TransitGatewayId=event['ResourceProperties']['TransitGatewayId'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )

    # UPDATE
    elif event['RequestType'] == 'Update':
        # There is no update_route method. We'll try to delete it, then create it.
        # But since we aren't passed the old route information, the delete will probably
        # fail and will create a new route below without deleting the old route
        result = delete_tgw_route(
            DestinationCidrBlock=event['ResourceProperties']['DestinationCidrBlock'],
            RouteTableId=event['ResourceProperties']['RouteTableId']
        )

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
    response = cfnresponse.FAILED
    try:
        if result['Return'] == True:
            response = cfnresponse.SUCCESS
    except Exception as e:
        logger.error(e)
    cfnresponse.send(event, context, response, result, "CustomResourcePhysicalID")
