import os
import argparse
import networkx as nx
import matplotlib.pyplot as plt
from kubernetes import client, config
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

def load_kube_config(kubeconfig_path):
    """
    Load the Kubernetes configuration from the specified path.
    
    Args:
    kubeconfig_path (str): Path to the kubeconfig file.
    """
    try:
        config.load_kube_config(config_file=kubeconfig_path)
    except Exception as e:
        print(f"Failed to load kubeconfig: {e}")
        raise

@lru_cache(maxsize=None)
def get_pods(api_instance, namespace):
    """
    Retrieve all pods in the specified Kubernetes namespace.
    If namespace is None, retrieves pods from all namespaces.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    namespace (str): Kubernetes namespace to retrieve pods from.
    
    Returns:
    list: List of pods.
    """
    try:
        if namespace:
            return api_instance.list_namespaced_pod(namespace=namespace).items
        else:
            return api_instance.list_pod_for_all_namespaces().items
    except Exception as e:
        print(f"Failed to get pods: {e}")
        return []

@lru_cache(maxsize=None)
def get_pvcs(api_instance, namespace):
    """
    Retrieve all PersistentVolumeClaims (PVCs) in the specified Kubernetes namespace.
    If namespace is None, retrieves PVCs from all namespaces.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    namespace (str): Kubernetes namespace to retrieve PVCs from.
    
    Returns:
    list: List of PVCs.
    """
    try:
        if namespace:
            return api_instance.list_namespaced_persistent_volume_claim(namespace=namespace).items
        else:
            return api_instance.list_persistent_volume_claim_for_all_namespaces().items
    except Exception as e:
        print(f"Failed to get PVCs: {e}")
        return []

@lru_cache(maxsize=None)
def get_volumes(api_instance):
    """
    Retrieve all PersistentVolumes (PVs) in the Kubernetes cluster.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    
    Returns:
    list: List of PVs.
    """
    try:
        return api_instance.list_persistent_volume().items
    except Exception as e:
        print(f"Failed to get volumes: {e}")
        return []

def get_pod_status(api_instance, namespace, pod_name):
    """
    Retrieve the status of a pod in the specified Kubernetes namespace.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    namespace (str): Kubernetes namespace of the pod.
    pod_name (str): Name of the pod.
    
    Returns:
    str: Status of the pod.
    """
    try:
        pod_status = api_instance.read_namespaced_pod_status(name=pod_name, namespace=namespace)
        return pod_status.status.phase
    except Exception as e:
        print(f"Failed to get status for pod {pod_name} in namespace {namespace}: {e}")
        return "Unknown"

def get_pvc_status(api_instance, namespace, pvc_name):
    """
    Retrieve the status of a PVC in the specified Kubernetes namespace.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    namespace (str): Kubernetes namespace of the PVC.
    pvc_name (str): Name of the PVC.
    
    Returns:
    str: Status of the PVC.
    """
    try:
        pvc_status = api_instance.read_namespaced_persistent_volume_claim_status(name=pvc_name, namespace=namespace)
        return pvc_status.status.phase
    except Exception as e:
        print(f"Failed to get status for PVC {pvc_name} in namespace {namespace}: {e}")
        return "Unknown"

def get_volume_status(api_instance, volume_name):
    """
    Retrieve the status of a PV (volume) in the Kubernetes cluster.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    volume_name (str): Name of the PV (volume).
    
    Returns:
    str: Status of the PV (volume).
    """
    try:
        volume_status = api_instance.read_persistent_volume(name=volume_name)
        return volume_status.status.phase
    except Exception as e:
        print(f"Failed to get status for volume {volume_name}: {e}")
        return "Unknown"

def get_pvc_capacity(api_instance, namespace, pvc_name):
    """
    Retrieve the capacity of a PVC in the specified Kubernetes namespace.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    namespace (str): Kubernetes namespace of the PVC.
    pvc_name (str): Name of the PVC.
    
    Returns:
    str: Capacity of the PVC.
    """
    try:
        pvc = api_instance.read_namespaced_persistent_volume_claim(name=pvc_name, namespace=namespace)
        return pvc.spec.resources.requests['storage']
    except Exception as e:
        print(f"Failed to get capacity for PVC {pvc_name} in namespace {namespace}: {e}")
        return "Unknown"

def get_volume_capacity(api_instance, volume_name):
    """
    Retrieve the capacity of a PV (volume) in the Kubernetes cluster.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    volume_name (str): Name of the PV (volume).
    
    Returns:
    str: Capacity of the PV (volume).
    """
    try:
        volume = api_instance.read_persistent_volume(name=volume_name)
        return volume.spec.capacity['storage']
    except Exception as e:
        print(f"Failed to get capacity for volume {volume_name}: {e}")
        return "Unknown"

def create_resource_graph(pods, pvcs, volumes, api_instance):
    """
    Create a directed graph of Kubernetes resources.
    
    Args:
    pods (list): List of pods.
    pvcs (list): List of PVCs.
    volumes (list): List of PVs.
    api_instance (client.CoreV1Api): Kubernetes API instance.
    
    Returns:
    networkx.DiGraph: Directed graph of resources.
    """
    G = nx.DiGraph()

    # Add nodes and edges for pods
    for pod in pods:
        pod_name = pod.metadata.name
        pod_status = get_pod_status(api_instance, pod.metadata.namespace, pod_name)
        G.add_node(pod_name, label=f"{pod_name}\nStatus: {pod_status}")  # Use the pod name and status as the label
        for volume in pod.spec.volumes:
            if volume.persistent_volume_claim:
                pvc_name = volume.persistent_volume_claim.claim_name
                pvc_capacity = get_pvc_capacity(api_instance, pod.metadata.namespace, pvc_name)
                pvc_status = get_pvc_status(api_instance, pod.metadata.namespace, pvc_name)
                G.add_node(pvc_name, label=f"{pvc_name}\nCapacity: {pvc_capacity}\nStatus: {pvc_status}\nType: PVC")  # Use the PVC name, capacity, status and type as the label
                G.add_edge(pod_name, pvc_name, label='uses')

    # Add nodes and edges for PVCs
    for pvc in pvcs:
        pvc_name = pvc.metadata.name
        pvc_capacity = get_pvc_capacity(api_instance, pvc.metadata.namespace, pvc_name)
        pvc_status = get_pvc_status(api_instance, pvc.metadata.namespace, pvc_name)
        G.add_node(pvc_name, label=f"{pvc_name}\nCapacity: {pvc_capacity}\nStatus: {pvc_status}\nType: PVC")  # Use the PVC name, capacity, status and type as the label
        if pvc.spec.volume_name:
            volume_name = pvc.spec.volume_name
            volume_capacity = get_volume_capacity(api_instance, volume_name)
            volume_status = get_volume_status(api_instance, volume_name)
            G.add_node(volume_name, label=f"{volume_name}\nCapacity: {volume_capacity}\nStatus: {volume_status}\nType: Volume")  # Use the PV name, capacity, status and type as the label
            G.add_edge(pvc_name, volume_name, label='bound to')

    # Add nodes for Volumes
    for volume in volumes:
        volume_name = volume.metadata.name
        volume_capacity = get_volume_capacity(api_instance, volume_name)
        volume_status = get_volume_status(api_instance, volume_name)
        G.add_node(volume_name, label=f"{volume_name}\nCapacity: {volume_capacity}\nStatus: {volume_status}\nType: Volume")  # Use the PV name, capacity, status and type as the label

    return G

def draw_graph(G):
    """
    Draw the Kubernetes resource graph.
    
    Args:
    G (networkx.DiGraph): Directed graph of resources.
    """
    pos = nx.spring_layout(G, seed=42)
    labels = nx.get_edge_attributes(G, 'label')
    node_labels = nx.get_node_attributes(G, 'label')

    plt.figure(figsize=(14, 10))
    nx.draw(G, pos, with_labels=True, labels=node_labels, node_size=3000, node_color='lightblue', font_size=10, font_weight='bold')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=labels, font_color='red')
    plt.title("Kubernetes Resource Graph")
    plt.show()

def fetch_resources(api_instance, namespaces):
    """
    Fetch Kubernetes resources (pods, PVCs, volumes) in parallel.
    
    Args:
    api_instance (client.CoreV1Api): Kubernetes API instance.
    namespaces (list): List of Kubernetes namespaces to fetch resources from.
    
    Returns:
    tuple: Lists of pods, PVCs, and PVs.
    """
    pods = []
    pvcs = []
    volumes = []

    with ThreadPoolExecutor() as executor:
        pod_futures = {executor.submit(get_pods, api_instance, namespace): namespace for namespace in namespaces}
        for future in pod_futures:
            namespace = pod_futures[future]
            try:
                pods.extend(future.result())
            except Exception as e:
                print(f"Failed to fetch pods from namespace {namespace}: {e}")

        pvc_futures = {executor.submit(get_pvcs, api_instance, namespace): namespace for namespace in namespaces}
        for future in pvc_futures:
            namespace = pvc_futures[future]
            try:
                pvcs.extend(future.result())
            except Exception as e:
                print(f"Failed to fetch PVCs from namespace {namespace}: {e}")

        try:
            volumes = get_volumes(api_instance)
        except Exception as e:
            print(f"Failed to fetch volumes: {e}")

    return pods, pvcs, volumes

def main(kubeconfig_path, namespaces):
    """
    Main function to load configuration, fetch resources, and create the graph.
    
    Args:
    kubeconfig_path (str): Path to the kubeconfig file.
    namespaces (str or list): Kubernetes namespace(s) to use. If None or empty list, uses all namespaces.
    """
    load_kube_config(kubeconfig_path)
    api_instance = client.CoreV1Api()

    if not namespaces:
        namespaces = [None]  # If no namespaces specified, use None to indicate all namespaces

    pods, pvcs, volumes = fetch_resources(api_instance, namespaces)
    resource_graph = create_resource_graph(pods, pvcs, volumes, api_instance)
    draw_graph(resource_graph)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a graph of Kubernetes resources")
    parser.add_argument('-k', '--kubeconfig', type=str, default=os.path.expanduser("~/.kube/config"),
                        help='Path to the kubeconfig file (default: ~/.kube/config)')
    parser.add_argument('-n', '--namespaces', type=str, nargs='*', default=None,
                        help='Kubernetes namespace(s) to use. If not specified, uses all namespaces.')
    args = parser.parse_args()

    main(args.kubeconfig, args.namespaces)
