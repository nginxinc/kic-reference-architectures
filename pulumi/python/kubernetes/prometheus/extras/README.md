# Purpose

This directory contains a manifest that can be used to change the metrics
bind port for the kube-proxy from 127.0.0.1 to 0.0.0.0 in order to allow the
metrics to be scraped by the prometheus service.

This is not being automatically applied, since it is changing the bind address
that is being used for the metrics port. That said, this should be secure
since it is internal to the installation and the connection is done via HTTPS.

However, please see this

[github issue](https://github.com/prometheus-community/helm-charts/issues/977)
for the full discussion of why this is required.
