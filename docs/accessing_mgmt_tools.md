## Accessing the Management Tools in MARA
Currently, the management tool suite in MARA consists of:
- Prometheus
- Grafana
- Locust
- Elasticsearch
- Kibana

Each of these tools provides an interface that can be reached through an endpoint exposed by the tool. 
For security reasons these tools are not exposed to the internet, which means you will need to use some 
form of port forwarding to access them.

### Running MARA on your Local Workstation
If you are running MARA on your local workstation, you can use the [test-forward.sh](../bin/test-forward.sh)
script to use [kubectl](https://kubernetes.io/docs/reference/kubectl/) to forward the ports on your behalf. 
These ports are all forwarded to the corresponding port on localhost as shown below:

```python
Connections Details
====================================
Kibana:        http://localhost:5601
Grafana:       http://localhost:3000
Locust:        http://localhost:8089
Prometheus:    http://localhost:9090
Elasticsearch: http://localhost:9200
====================================

Issue Ctrl-C to Exit
```

Issuing a Ctrl-C will cause the ports to close. 

### Running MARA Somewhere Else
In the event you are running MARA somewhere else - in the cloud, on a different server, in a VM on your laptop, etc
you will need to go through an additional step. Note that this is just one way of accomplishing this, and depending
on your environment you may want or need to do this differently. 

The easiest thing is to install `kubectl` on the system you want to access the MARA tooling from and then copy over the
`kubeconfig` from your MARA deployment system. This will then allow you to copy over the `test-forward.sh` script and
use that to build the tunnels locally.

### Edge Cases
There are definitely cases where these solutions will not work. Please see the "More Information" section below, and 
if you have one of these cases and discover a solution please open a PR so that we can add to this section.

### More Information
To learn more about Kubernetes port-forwarding, please see 
[this article](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/)