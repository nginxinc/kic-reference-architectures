## Sample Configurations
This directory contains a number of sample configurations that can be used with the 
[OTEL kubernetes operator](https://github.com/open-telemetry/opentelemetry-operator) that is installed as part of the
MARA project. 

Each configuration currently uses the `simplest` deployment, which uses an in-memory store for data being processed. 
This is obviously not suited to a production deployment, but it is intended to illustrate the steps required to work 
with the OTEL deployment.

## Commonality

### Listening Ports
Each of the sample files is configured to listen on the 
[OTLP protocol](https://opentelemetry.io/docs/reference/specification/protocol/otlp/). The listen ports configured are:
* grpc on port 9978
* http on port 9979

### Logging 
All the examples log to the container's stdout. However, the basic configuration is configured to only show the 
condensed version of the traces being received. In order to see the full traces, you need to set the logging level to
`DEBUG`. The basic-debug object is configured to do this automatically.

## Configurations
### `otel-collector.yaml.basic`
This is the default collector that only listens and logs summary spans to the container's stdout. 

### `otel-collector.yaml.basic`
This is a variant of the default collector that will output full spans to the container's stdout. 

### `otel-collector.yaml.full`
This is a more complex variant that contains multiple receivers, processors, and exporters. Please see the file for 
details.

### `otel-collector.yaml.lightstep`
This configuration file deploys lightstep as an ingester. Please note you will need to have a 
[lightstep](https://lightstep.com/) account to use this option, and you will need to add your lightstep access token 
to the file in the field noted.

## Usage
By default, the `otel-collector.yaml.basic` configuration is copied into the live `otel-collector.yaml`. The logic for
this project runs all files ending in `.yaml` as part of the configuration, so you simply need to either rename your 
chosen file to `otel-collector.yaml` or add ensuring only the files you want to use have the `.yaml` extension. 


