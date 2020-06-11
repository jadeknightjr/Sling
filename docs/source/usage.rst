Usage
=====
Now that you have Sling set up, you can now manage the merging of a GitHub 
repository. But how do you do this?

GitHub Credentials
------------------
Sling needs your login credentials to do the merging for you. These must be saved in
AWS Secrets Manager. The url of your AWS Secrets Manager must be placed in your config file. Note that the key
values for your Secrets Manager must be **github_username** and **github_password**. Please
ensure that your logic credentials are valid, or Sling will not work. Your config 
file should have the name of the repository as well as the owner of the repository in it. 
This repository will be a service that Sling cares about, thus put an appropriate 
name for it in your Config.

Now you are ready to create the locks and services for your application. You could 
manually create the entries in the table, but a better way would be to use our API to create
entries for our table. You can do it quickly by deploying chalice locally.

.. code-block:: bash

    chalice local

Now run the following commands

.. code-block:: bash

    echo '{"ServiceName": "MyRelease", "ServiceTableName": "RegisteredServices"}' | http POST localhost:8000/register_service
    echo '{"LockName": "MyLock", "LockTableName": "LockTable"}' | http POST localhost:8000/register_lock

If you check your DynamoDB tables, you will see that we have created a new lock and service. Please ensure that
the values you have in your config match up to those you put in your api calls.

Now your application is set up to automatically merge. If you haven't set the environmental
variable PRM_BOT_RUNTIME, then we will use the default runtime of 300 minutes, meaning the bot will 
run every 5 hours.

