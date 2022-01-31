## Pulumi Configuration Directory
This directory contains the yaml configuration files used for the pulumi installation. The file 
[`Pulumi.stackname.yaml.example`](./Pulumi.stackname.yaml.example) contains the list of variables that
this installation understands.

Many of the variables have defaults that are enforced through the Pulumi code for each project, however
there are certain variables that are required. When the process reaches one of these variables and it
is not set the process will abort with an error message.