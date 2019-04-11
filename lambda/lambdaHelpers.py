import troposphere.awslambda as awslambda
import troposphere.iam as iam
from troposphere import GetAtt, Ref, Join
from troposphere import Parameter, Template, Output, Tags, Export

def get_template():
    template = Template()
    template.description = "Stack of helper lambda functions"

    #####################################
    # PARAMETERS

    group_name = "Environment Configuration"

    asi = template.add_parameter(
        Parameter(
            "ASI",
            Description="asi - must be lower-case, limit 4 characters",
            Type="String",
            MinLength=2,
            MaxLength=4,
            AllowedPattern="[a-z]*"
        )
    )
    template.add_parameter_to_group(asi, group_name)

    env = template.add_parameter(
        Parameter(
            "Environment",
            Description="environment (nonprod|prod) - must be lower-case, limit 7 characters",
            Type="String",
            MinLength=3,
            MaxLength=7,
            AllowedPattern="[a-z]*"
        )
    )
    template.add_parameter_to_group(env, group_name)

    owner = template.add_parameter(
        Parameter(
            "Owner",
            Type="String",
            Description="email address of the the Owner of this stack",
            Default="admin@root.com",
            AllowedPattern="^[\\w-\\+]+(\\.[\\w]+)*@[\\w-]+(\\.[\\w]+)*(\\.[a-z]{2,})$"
        )
    )
    template.add_parameter_to_group(owner, group_name)

    lambda_bucket = template.add_parameter(
        Parameter(
            "LambdaFunctionsBucketName",
            Description="Existing S3 bucket name which contains the Lambda functions in lambda.zip",
            Type="String"
        )
    )
    template.add_parameter_to_group(lambda_bucket, group_name)

    lambda_zip = template.add_parameter(
        Parameter(
            "LambdaZipFile",
            Description="Name of lambda zip file in S3 bucket",
            Type="String",
            Default="lambda.zip"
        )
    )
    template.add_parameter_to_group(lambda_zip, group_name)

    #############################
    # Tags we'll apply to all resources

    std_tags = Tags(
        Project=Ref(asi),
        Environment=Ref(env),
        Owner=Ref(owner)
    )

    ############################
    # Resources

    lambda_role = template.add_resource(
        iam.Role(
            "lambdaExecutionRole",
            RoleName=Join("-", ["lambdaExecutionRole", Ref("AWS::StackName")]),
            Path="/",
            AssumeRolePolicyDocument={
                "Version": "2012-10-17",
                "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": ["lambda.amazonaws.com"]},
                        "Action": ["sts:AssumeRole"]
                }]
            },
            ManagedPolicyArns=["arn:aws:iam::aws:policy/AWSLambdaExecute", ],
            Policies=[
                iam.Policy(
                    PolicyName=Join("-", ["lambdaExecutionPolicy", Ref("AWS::StackName")]),
                    PolicyDocument={
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "ec2:CreateRoute",
                                    "ec2:DeleteRoute",
                                    "ec2:DescribeSubnets"
                                    ],
                                "Resource": "*",
                            }
                        ]
                    }
                )
            ]
        )
    )

    lamda_vpc_tgw_rte = template.add_resource(
        awslambda.Function(
            "VpcTgwRoute",
            Description="Function to create a VPC route to transit gateway",
            Handler="vpc_tgw_route.lambda_handler",
            Role=GetAtt(lambda_role, "Arn"),
            Code=awslambda.Code(
                S3Bucket=Ref(lambda_bucket),
                S3Key=Ref(lambda_zip)
            ),
            Runtime="python3.6",
            Timeout=150,
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "VpcTgwRoute"]))
        )
    )

    lamda_subnet_attributes = template.add_resource(
        awslambda.Function(
            "VpcSubnetAttributes",
            Description="Function to get VPC subnet attributes",
            Handler="vpc_subnet_attributes.lambda_handler",
            Role=GetAtt(lambda_role, "Arn"),
            Code=awslambda.Code(
                S3Bucket=Ref(lambda_bucket),
                S3Key=Ref(lambda_zip)
            ),
            Runtime="python3.6",
            Timeout=150,
            Tags=std_tags + Tags(Name=Join("-", [Ref(asi), Ref(env), "VpcSubnetAttributes"]))
        )
    )

    lambda_arn = template.add_output(
        Output(
            "VpcTgwRouteLambdaArn",
            Description="The ARN of the VPC Transit Gateway Function",
            Value=GetAtt(lamda_vpc_tgw_rte, "Arn"),
            Export=Export(Join("-", [Ref("AWS::StackName"), lamda_vpc_tgw_rte.title]))
        )
    )

    lambda_arn = template.add_output(
        Output(
            "VpcSubnetAttributesLambdaArn",
            Description="The ARN of the VPC Subnet Attributes Function",
            Value=GetAtt(lamda_vpc_tgw_rte, "Arn"),
            Export=Export(Join("-", [Ref("AWS::StackName"), lamda_subnet_attributes.title]))
        )
    )

    return template


def print_template():
    print(template.to_yaml())
    #print(template.to_json())
