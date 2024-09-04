# pods-graph

Relationship between the Kubernetes pods and their volumes

## What does this application do, in more detail?

### This application provides a detailed and interactive way to visualize Kubernetes resources and their relationships within a cluster. Here’s a more in-depth explanation of what the application does:

1. **Kubernetes Cluster Interaction:** The application connects to your Kubernetes cluster using a specified `kubeconfig` file.

2. **Resource Retrieval:** The application fetches three main types of Kubernetes resources ->

  -  Pods: The smallest deployable units that can be created and managed in Kubernetes, usually running one or more containers.

  -  Persistent Volume Claims (PVCs): Requests for storage by users. PVCs abstract the storage resource requirements of applications.

  - Persistent Volumes (PVs): Actual storage resources in the cluster that can be used by PVCs.

3. **Namespace Specification:** Users can specify which namespaces to pull resources from. If no namespace is specified, the application fetches resources from all namespaces in the cluster, providing a comprehensive view.

4. **Graph Creation:**

  - The application constructs a directed graph using `networkx`, a Python package for creating and manipulating complex networks.

  - Nodes in the graph represent the resources (Pods, PVCs, and PVs). Each node is labeled with detailed information, including the resource’s name, status, capacity, and type.

  - Edges between nodes represent relationships: for example, how Pods use PVCs, and how PVCs are bound to PVs. The edges are labeled to indicate the nature of these connections. 

5. **Resource Status and Capacity Visualization:** 

  - The graph provides a visual overview of each resource’s status, such as whether a Pod is running, pending, or failed, or whether a PVC is bound or unbound.

  - It also shows the capacity of storage resources, giving users insights into how much storage each PVC and PV is requesting or providing.

6. **Error Handling:** The application includes robust error handling to deal with issues such as failed connections, missing resources, or permission errors, and outputs helpful error messages to guide users in troubleshooting.

7. **Graph Visualization:**

  - The graph is rendered using `matplotlib`, a plotting library that displays the graph directly in a visual format.

  - This visual representation makes it easy for users to understand complex resource dependencies and quickly identify potential issues such as unbound volumes or Pods without storage.

### What are the possible use cases?

1. **Troubleshooting:** Quickly identify Pods that are not running as expected or PVCs that are not correctly bound to PVs.

2. **Resource Management:** Gain a clear overview of how storage resources are allocated and used across different namespaces.

3. **Cluster Monitoring:** Continuously monitor the health and status of Kubernetes resources in a visual format that is easier to digest than raw command-line outputs.

Overall, this application simplifies the management of Kubernetes resources by transforming abstract connections into a visual map. This allows DevOps engineers, SREs, and Kubernetes administrators to quickly grasp the state of their clusters, identify potential issues, and optimize resource utilization.

## Requirements:

```console
python3 -m venv venv
source venv/bin/activate
pip3 install kubernetes networkx matplotlib
#`deactivate`is the command to use to exit the venv environment.
```

## How to use the script:

```console
$ python3 graph.py -h
usage: graph.py [-h] [-k KUBECONFIG] [-n [NAMESPACES ...]]

This script generates a graph of Kubernetes resources such as Pods, Persistent Volume Claims (PVCs), and Persistent Volumes (PVs). It fetches these
resources from specified Kubernetes namespaces and visually represents their relationships.

options:
  -h, --help            show this help message and exit
  -k KUBECONFIG, --kubeconfig KUBECONFIG
                        Path to the kubeconfig file (default: ~/.kube/config). This file is used to authenticate and configure access to your Kubernetes
                        cluster.
  -n [NAMESPACES ...], --namespaces [NAMESPACES ...]
                        Kubernetes namespace(s) to use. If not specified, the script fetches resources from all namespaces. Example: -n default kube-
                        system.

Example usage: python graph.py -k ~/.kube/config -n default
```
