import setuptools


with open("README.md") as fp:
    long_description = fp.read()


setuptools.setup(
    name="cdk_environment_setup",
    version="0.0.1",
    description="A CDK Python app to deploy environments such as alarms and DynamoDB Tables",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Johnny",
    package_dir={"": "cdk_environment_setup"},
    packages=setuptools.find_packages(where="cdk_environment_setup"),
    install_requires=[
        "aws-cdk.core==1.54.0",
        "aws-cdk.aws_iam==1.54.0",
        "aws-cdk.aws_sqs==1.54.0",
        "aws-cdk.aws_sns==1.54.0",
        "aws-cdk.aws_sns_subscriptions==1.54.0",
        "aws-cdk.aws_s3==1.54.0",
        "aws-cdk.aws_cloudwatch==1.54.0",
        "aws-cdk.aws_dynamodb==1.54.0",
    ],
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: JavaScript",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Utilities",
        "Typing :: Typed",
    ],
)
