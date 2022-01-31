## Pulumi Common Configuration Directory   
This common directory replaces the `vpc` directory as the main touchpoint for all of the Pulumi stacks
that are used in the project.

This is necessary since using different directories will result in failures encrypting/decrypting the
values in the main configuration file if different stacks are used. This is a stopgap workaround that
will be obsoleted at such time that Pulumi provides nested/included configuration files.