#!/usr/bin/env bash
#
# This is a simple shell script that sets up port forwards locally for
# the various benchmarking/monitoring tooling that is part of the 
# deployment. This should be run on the same machine as your web browser,
# then you will be able to connect to the localhost ports to get to the
# services.
#
# This script is designed to clean itself up once a Ctrl-C is issued.
#

PID01=$(mktemp)
PID02=$(mktemp)
PID03=$(mktemp)
PID04=$(mktemp)
PID05=$(mktemp)

# this function is called when Ctrl-C is sent
function trap_ctrlc ()
{
    # perform cleanup here
    echo "Ctrl-C caught...performing clean up"

    echo "Doing cleanup"

    echo "Kill forwards"
    kill $(cat $PID01)
    kill $(cat $PID02)
    kill $(cat $PID03)
    kill $(cat $PID04)
    kill $(cat $PID05)

    echo "Remove temp files"
    rm $PID01
    rm $PID02
    rm $PID03
    rm $PID04
    rm $PID05

    # exit shell script with error code 2
    # if omitted, shell script will continue execution
    exit 2
}

# initialise trap to call trap_ctrlc function
# when signal 2 (SIGINT) is received
trap "trap_ctrlc" 2

## Kibana Tunnel
kubectl port-forward service/elastic-kibana --namespace logstore 5601:5601 &
echo $! > $PID01

## Grafana Tunnel
kubectl port-forward service/grafana --namespace grafana 3000:80 &
echo $! > $PID02

## Loadgenerator Tunnel
kubectl port-forward service/loadgenerator --namespace bos 8089:8089 &
echo $! > $PID03

## Prometheus Tunnel
kubectl port-forward service/prometheus-server --namespace prometheus 9090:80 &
echo $! > $PID04

## Elasticsearch Tunnel
kubectl port-forward service/elastic-coordinating-only --namespace logstore 9200:9200 &
echo $! > $PID05

## Legend
echo "Connections Details"
echo "===================================="
echo "Kibana:        http://localhost:5601"
echo "Grafana:       http://localhost:3000"
echo "Locust:        http://localhost:8089"
echo "Prometheus:    http://localhost:9090"
echo "Elasticsearch: http://localhost:9200"
echo "===================================="
echo ""
echo "Issue Ctrl-C to Exit"
## Wait...
wait


