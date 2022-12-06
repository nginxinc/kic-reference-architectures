# MARA Sumologic Integration Preview
This branch contains the beta code for the MARA/Sumo Logic integration using 
the Sumo 3.0 Helm Chart. This version uses the 
[Sumo Logic collector](https://help.sumologic.com/docs/send-data/sumo-distribution-opentelemetry/) 
built on top of Open Telemetry (OTEL). This provides one collector for metrics,
traces, and logs. 

Going forward, MARA will be moving away from proprietary solutions towards those
that support OTEL. This will demonstrate how instrumenting applications and 
environments to the OTEL spec provides the flexibility to change monitoring/alerting 
platforms if required.

## Requirements
In order to deploy this version of MARA you need to have a Sumo Logic account and have
generated an API token. This token - the key and id - will need to be added to MARA
at configuration time.

To enable the Sumologic integration branch, you will need to insert the value 
`SUMO=True` into the `./config/pulumi/environment` file. This instructs the 
installer to use the Sumo specific code path.

## Deployment Differences
When deploying Sumo, the following projects are not deployed:
- Grafana
- Prometheus
- Logstore
- Logagent

The following project is deployed instead:
- Sumo

*Note: The Sumo project does install a prometheus collector that is used for metrics 
aggregation. We are still determining the best way to deploy prometheus along with the
various OTEL solutions in order to provide the most flexibility to users.*

The installer will prompt you for your Sumo access id and access key at installation 
time, along with the name for your cluster. 

There are two areas where the Bank of Sirius application needs to be configured in 
order to properly interact with Sumo. These are:
- The prom_namespace variable for the postgres/prometheus collectors in the BoS project.
- The trace_endpoint variable for where the OTEL traces are sent.

These values are prompted for by the installer when running in Sumo mode; **accept the 
defaults unless you really know what you are doing**. These values are passed through 
to the Bank of Sirius application using the MARA secrets project, which leverages 
the Kubernetes secret store to provide secure access to them.

## Known Working Environments
This branch should deploy on any environment that currently works with MARA.

## Known Issues
There are several known issues that you may run into while running this version of MARA. 

### Failures Standing up Sumo Project
If this project keeps failing out with helm errors, there is a fairly good chance that 
you have an invalid access_id and/or access_key. You can check these values by:
- Ensuring you have Pulumi on your path; if not you can always source the venv created 
   by the MARA project: `source ./pulumi/python/venv/bin/activate`
- Changing to `pulumi/python/kubernetes/secrets`.
- Listing secrets by running `pulumi config --show-secrets`
- If you need to change a secret you can do so by running 
  `pulumi config set --secret namespace:variable`

### Undefined Problems with runner.sh
The code used to switch to Sumo is relatively simple and not exceptionally well tested. 
If you run into problems, it is usually best to destroy your deployment and retry.

### Issues Reverting to "normal" Deployment
To stop deploying with Sumo and instead use the existing monitoring you need to destroy 
the project, remove the `SUMO=True` line from the `config/pulumi/environment` file, and 
then redeploy. Note that you need to completely remove the SUMO line - you cannot currently 
set it to False and expect it to work.
