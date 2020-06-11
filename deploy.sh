#!/bin/bash
pip install -r requirements.txt

# Flags
SERVICE_TABLE_NAME=""
LOCK_TABLE_NAME=""
CONFIG_FLAG=false       # Do you want deploy.sh to edit Chalice's config file
DESTROY_FLAG=false      # Do you want to destroy previous deployments of application, before redeployment.
                        # Highly recommend having CONFIG_FLAG set to same as DESTROY_FLAG

while getopts :s:l:cd options; do
    case $options in 
        s) SERVICE_TABLE_NAME=$OPTARG;;
        l) LOCK_TABLE_NAME=$OPTARG;;
        c) CONFIG_FLAG=true;;
        d) DESTROY_FLAG=true;;
        ?) echo "You provided an unknown flag: $OPTARG ";;
    esac
done

cd cdk_environment_setup
pip install -r requirements.txt
if [ "$DESTROY_FLAG" = true ] ; then
    echo -e "Destroying previous Alarms and Tables"
    yes | cdk destroy
fi
echo -e "Deploying Alarms via AWS CDK\n"
cdk bootstrap
cdk deploy
cd ..   

if [ "$DESTROY_FLAG" = true ] ; then
    echo -e "Deleting previous Chalice Components\n" 
    chalice delete
fi
echo -e "Deploying Chalice component of Chalice\n" 

if [ "$CONFIG_FLAG" = true ] ; 
then
    REST_API_URL=$(chalice deploy | grep -o 'URL: .*' | cut -f2- -d:);

    # jq is necessary to edit config, json file.
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # From Ubuntu 16.04LTS and onwards
        # sudo apt-get update
        # sudo apt-get install jq

        # If your LInux system is CentOS-based, do the below command
        y | sudo yum install jq
    fi
    jq -c '.api_route = $newVal' --arg newVal "$REST_API_URL" chalicelib/settings/config.json  | jq . > tmp.$$.json && mv tmp.$$.json chalicelib/settings/config.json

else
    chalice deploy
fi
#If you don't run again, you may run into an issue with the kms Iam Policy.
chalice deploy
