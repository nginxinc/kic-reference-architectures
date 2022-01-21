#!/usr/bin/env bash

#set -o errexit  # abort on nonzero exit status
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
  exit 100
fi

# Make sure we can connect
kubectl cluster-info
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to connect to cluster and pull information!"
  echo " "
  exit 101
else
  echo " "
  echo "Success connecting to cluster"
  echo " "
fi


# We are going to do all our testing in a dedicated namespace
echo " "
echo "Test ability to create a namespace:"
kubectl create ns testspace
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to create namespace testspace!"
  echo " "
  exit 1
fi
echo "Namespace testspace created"
echo " "

# Create a PV Claim
echo " "
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
  echo " "
  exit 2
fi
echo "Persistent volume yaml applied"
echo " "

# Perform a write test
echo " "
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
KOUNT=0
while  [ "$WRITEJOB" != "Completed" ] || [ $KOUNT -ge 10 ]  ; do
  WRITEJOB=$(kubectl get pods --selector=job-name=write --output=jsonpath='{.items[*].status.containerStatuses[0].state.terminated.reason}')
  echo "Waiting for job to complete..."
  sleep 15
  ((KOUNT++))
done

if [ $KOUNT -ge 10 ] ; then
  echo "FAILURE! Unable to create or write to persistent volume!"
  exit 3
elif [ "$WRITEJOB" == "Completed" ] ; then
  echo "Persistent volume write test completed; logs follow:"
  kubectl logs --selector=job-name=write  --namespace testspace
  echo " "
else
  echo "Should not get here! Exiting!"
  exit 4
fi


# Perform a read test
echo " "
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
KOUNT=0
while [ "$READJOB" != "Completed" ] || [ $KOUNT -ge 10 ]  ; do
  READJOB=$(kubectl get pods --selector=job-name=read --output=jsonpath='{.items[*].status.containerStatuses[0].state.terminated.reason}')
  echo "Waiting for job to complete..."
  sleep 15
  ((KOUNT++))
done

if [ $KOUNT -ge 10 ] ; then
  echo "FAILURE! Unable to read from persistent volume!"
  exit 3
elif [ "$READJOB" == "Completed" ] ; then
  echo "Persistent volume read test completed; logs follow:"
  kubectl logs --selector=job-name=read  --namespace testspace
  echo " "
else
  echo "Should not get here! Exiting!"
  exit 4
fi

# Clean up...
echo " "
echo "Cleaning up read job"
kubectl --namespace testspace delete job read
if [ $? -ne 0 ] ; then
  echo "Failed to cleanup read job"
else
  echo "Complete"
  echo " "
fi

echo "Cleaning up write job"
kubectl --namespace testspace delete job write
if [ $? -ne 0 ] ; then
  echo "Failed to cleanup write job"
else
  echo "Complete"
  echo " "
fi

echo "Cleaning up persistent volume"
kubectl --namespace testspace delete pvc maratest01
if [ $? -ne 0 ] ; then
  echo "Failed to cleanup persistent volume"
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
  echo " "
  exit 1
fi

echo "Sleeping 30 to wait for IP assignment"
sleep 30
echo "Checking for External IP address"
echo " "
EXTIP=$(kubectl  get service kuard  --namespace testspace --output=jsonpath='{.status.loadBalancer.ingress[*].ip}')
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to pull loadBalancer IP address!"
  echo " "
  exit 1
fi

echo "External IP is $EXTIP"
echo " "

echo "Deleting KUARD deployment"
kubectl --namespace testspace delete deployment kuard
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete KUARD deployment!"
  echo " "
  exit 1
fi

echo "Deleting KUARD service"
kubectl --namespace testspace delete service kuard
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete KUARD service!"
  echo " "
  exit 1
fi

echo "Deleting testspace namespace"
kubectl delete ns testspace
if [ $? -ne 0 ] ; then
  echo "FAILURE! Unable to delete KUARD service!"
  echo " "
  exit 1
fi

echo "All tests passed!"

