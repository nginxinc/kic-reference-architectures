#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o nounset  # abort on unbound variable
set -o pipefail # don't hide errors within pipes

# Test to see if we have persistent volume support; to do this we provision a PV using the default storage class
# and then conduct a read and write test against it.
#
# Since MARA is intended as a testbed application, the performance numbers are not a particular concern, however it is
# advised that you test your PV provider for performance and concurrency if you are in production, development, or
# quality assurance testing. For example, the NFS volume support is known to potentially cause issues due to the way
# that NFS works (latency, performance).
#

# Timeout Value
# We check in 15 second increments
TIMEOUT=15


# Clean up the namespace....
cleanitup() {
  echo "Deleting testspace namespace"
  echo "This should remove all test resources"
  kubectl delete ns testspace
  if [ $? -ne 0 ] ; then
    echo "FAILURE! Unable to remove namespace testpsace"
    echo " "
    exit 100
  fi
}


echo " "
echo "This script will perform testing on the current kubernetes installation using the currently active kubernetes"
echo "configuration and context."
echo " "
echo "Any failures should be investigated, as they will indicate that the installation does not meet the minimum set"
echo "of capabilities required to run MARA."
echo " "
sleep 5

# We need kubectl to do any of this....
if command -v kubectl > /dev/null; then
  echo "Found kubectl - continuing"
else
  echo "Cannot proceed without kubectl!"
  echo "Please install kubectl and ensure it is in your path."
  exit 101
fi

# Write out the configuration so we can see it
echo "Dumping current configuration:"
kubectl config view
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to connect to dump configuration from kubeconfig file."
  echo "Please check your kubeconfig file."
  echo " "
  exit 102
else
  echo " "
fi

# Make sure we can connect
echo "Connecting to cluster:"
kubectl cluster-info
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to connect to cluster and pull information!"
  echo "Please make sure you are able to connect to the cluster context defined in your kubeconfig file"
  echo " "
  exit 103
else
  echo "Success connecting to cluster"
  echo " "
fi


# We are going to do all our testing in a dedicated namespace
echo "Test ability to create a namespace:"
kubectl create ns testspace
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to create namespace testspace!"
  echo "Please make sure you are able to create namespaces in your cluster"
  echo " "
  exit 104
fi
echo "Namespace testspace created"
echo " "

# Create a PV Claim
echo "Create a persistent volume"
kubectl apply -f - << EOF
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: maratest01
  namespace: testspace
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 5G
EOF

if [ $? -ne 0 ] ; then
  echo "FAILURE! Error trying to create persistent volume!"
  echo "This could be related to an error running the YAML or an issue attempting to create"
  echo "a persistent volume."
  echo " "
  echo "Please make sure you are able to create persistent volumes in your cluster and try again."
  echo " "
  cleanitup
  exit 105
fi
echo "Persistent volume yaml applied"
echo " "

# Perform a write test
echo "Test writing to the persistent volume"
kubectl apply -f - << EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: write
  namespace: testspace
spec:
  template:
    metadata:
      name: write
    spec:
      containers:
      - name: write
        image: ubuntu:xenial
        command: ["dd","if=/dev/zero","of=/mnt/pv/test.img","bs=1G","count=1","oflag=dsync"]
        volumeMounts:
        - mountPath: "/mnt/pv"
          name: maratest01
      volumes:
      - name: maratest01
        persistentVolumeClaim:
          claimName: maratest01
      restartPolicy: Never
EOF

WRITEJOB="FIRSTRUN"
KOUNT=1
while  [ "$WRITEJOB" != "Completed" ] && [ $KOUNT -lt $TIMEOUT ]  ; do
  WRITEJOB=$(kubectl get pods --selector=job-name=write --namespace testspace --output=jsonpath='{.items[*].status.containerStatuses[0].state.terminated.reason}')
  echo "Attempt $KOUNT of $TIMEOUT: Waiting for job to complete..."
  sleep 15
  ((KOUNT++))
done

if [ $KOUNT -ge $TIMEOUT ] ; then
  echo "FAILURE! Unable to create or write to persistent volume!"
  echo "Please make sure you are able to create and write to persistent volumes in your cluster."
  cleanitup
  exit 106
elif [ "$WRITEJOB" == "Completed" ] ; then
  echo "Persistent volume write test completed; logs follow:"
  kubectl logs --selector=job-name=write  --namespace testspace
  echo " "
else
  echo "Should not get here! Exiting!"
  cleanitup
  exit 107
fi


# Perform a read test
echo "Test reading from the persistent volume"
kubectl apply -f - << EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: read
  namespace: testspace
spec:
  template:
    metadata:
      name: read
    spec:
      containers:
      - name: read
        image: ubuntu:xenial
        command: ["dd","if=/mnt/pv/test.img","of=/dev/null","bs=8k"]
        volumeMounts:
        - mountPath: "/mnt/pv"
          name: maratest01
      volumes:
      - name: maratest01
        persistentVolumeClaim:
          claimName: maratest01
      restartPolicy: Never
EOF

READJOB="FIRSTRUN"
KOUNT=1
while [ "$READJOB" != "Completed" ]  && [ $KOUNT -lt $TIMEOUT ]   ; do
  READJOB=$(kubectl get pods --selector=job-name=read --namespace testspace --output=jsonpath='{.items[*].status.containerStatuses[0].state.terminated.reason}')
  echo "Attempt $KOUNT of $TIMEOUT: Waiting for job to complete..."
  sleep 15
  ((KOUNT++))
done

if [ $KOUNT -ge $TIMEOUT ] ; then
  echo "FAILURE! Unable to read from persistent volume!"
  echo "Please make sure you are able to read from persistent volumes in your cluster"
  cleanitup
  exit 108
elif [ "$READJOB" == "Completed" ] ; then
  echo "Persistent volume read test completed; logs follow:"
  kubectl logs --selector=job-name=read  --namespace testspace
  echo " "
else
  echo "Should not get here! Exiting!"
  cleanitup
  exit 109
fi

# Clean up...
echo "Cleaning up read job"
kubectl --namespace testspace delete job read
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete read job!"
  echo "Please check your installation to determine why this is failing!"
  cleanitup
  exit 110
else
  echo "Complete"
  echo " "
fi

echo "Cleaning up write job"
kubectl --namespace testspace delete job write
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete write job!"
  echo "Please check your installation to determine why this is failing!"
  cleanitup
  exit 111
else
  echo "Complete"
  echo " "
fi

echo "Cleaning up persistent volume"
kubectl --namespace testspace delete pvc maratest01
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to clean up persistent volume!"
  echo "Please check your installation to determine why this is failing!"
  cleanitup
  exit 112
else
  echo "Complete"
  echo " "
fi

echo "Deploying KUARD application"
kubectl apply -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: kuard
  name: kuard
  namespace: testspace
spec:
  replicas: 2
  selector:
    matchLabels:
      app: kuard
  template:
    metadata:
      labels:
        app: kuard
    spec:
      containers:
      - image: gcr.io/kuar-demo/kuard-amd64:1
        name: kuard
---
apiVersion: v1
kind: Service
metadata:
  labels:
    app: kuard
  name: kuard
  namespace: testspace
spec:
  ports:
  - port: 80
    protocol: TCP
    targetPort: 8080
  selector:
    app: kuard
  sessionAffinity: None
  type: LoadBalancer
EOF

if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to create KUARD application!"
  echo "Please check your installation to determine why this is failing!"
  cleanitup
  exit 113
fi

echo "Sleeping 30 to wait for IP assignment"
sleep 30
echo "Checking for External IP address"
echo " "
EXTIP=$(kubectl  get service kuard  --namespace testspace --output=jsonpath='{.status.loadBalancer.ingress[*].ip}')
if [ "$EXTIP" == "" ] ; then
  echo "FAILURE! Unable to pull loadBalancer IP address!"
  echo "This could mean that you do not have a loadBalancer egress defined for the cluster, or it could"
  echo "be misconfigured. Please remediate this issue."
  echo " "
  cleanitup
  exit 114
fi

echo "External IP is $EXTIP"
echo " "

echo "Deleting KUARD deployment"
kubectl --namespace testspace delete deployment kuard
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete KUARD deployment!"
  echo "Please check your installation to determine why this is failing!"
  cleanitup
  exit 115
fi

echo "Deleting KUARD service"
kubectl --namespace testspace delete service kuard
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete KUARD service!"
  echo "Please check your installation to determine why this is failing!"
  cleanitup
  exit 116
fi

# If we reached this point we are good!
cleanitup
echo " "
echo "=============================================================="
echo "| All tests passed! This system meets the basic requirements |"
echo "| to deploy MARA.                                            |"
echo "=============================================================="

