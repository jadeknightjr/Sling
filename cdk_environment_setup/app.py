#!/usr/bin/env python3

from aws_cdk import core

from cdk_environment_setup.cdk_environment_setup_stack import CdkEnvironmentSetupStack


app = core.App()
CdkEnvironmentSetupStack(
    app, "sling-environment-setup", env={"region": "us-west-2"}
)

app.synth()
