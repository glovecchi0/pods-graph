import os
import argparse
import networkx as nx
import matplotlib.pyplot as plt
from kubernetes import client, config
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import fnmatch


def load_kube_config(kubeconfig_path):
    """Load the Kubernetes configuration from the specified path."""
    try:
        config.load_kube_config(config_file=kubeconfig_path)
    except Exception as e:
        print(f"Failed to load kubeconfig: {e}")
        raise


@lru_cache(maxsize=None)
def get_resources(api_instance, resource_type, namespace=None):
    """
    Retrieve Kubernetes resources of a specified type in the given namespace.
    
    Args:
        api_instance (client.CoreV1Api): Kubernetes API instance.
        resource_type (str): Type of the resource to retrieve ('pods', 'pvcs', 'volumes').
        namespace (str, optional): Kubernetes namespace to retrieve resources from.
        
    Returns:
        list: List of resources.
    """
    try:
        if resource_type == 'pods':
            if namespace:
                return api_instance.list_namespaced_pod(namespace=namespace).items
            return api_instance.list_pod_for_all_namespaces().items
        
        if resource_type == 'pvcs':
            if namespace:
                return api_instance.list_namespaced_persistent_volume_claim(namespace=namespace).items
            return api_instance.list_persistent_volume_claim_for_all_namespaces().items
        
        if resource_type == 'volumes':
            return api_instance.list_persistent_volume().items
        
    except Exception as e:
        print(f"Failed to get {resource_type}: {e}")
        return []


def get_resource_status(api_instance, resource_type, namespace, name):
    """
    Retrieve the status of a Kubernetes resource.
    
    Args:
        api_instance (client.CoreV1Api): Kubernetes API instance.
        resource_type (str): Type of the resource ('pod', 'pvc', 'volume').
        namespace (str): Kubernetes namespace of the resource.
        name (str): Name of the resource.
        
    Returns:
        str: Status of the resource.
    """
    try:
        if resource_type == 'pod':
            status = api_instance.read_namespaced_pod_status(name=name, namespace=namespace)
            return status.status.phase
        
        if resource_type == 'pvc':
            status = api_instance.read_namespaced_persistent_volume_claim_status(name=name, namespace=namespace)
            return status.status.phase
        
        if resource_type == 'volume':
            status = api_instance.read_persistent_volume(name=name)
            return status.status.phase
            
    except Exception as e:
        print(f"Failed to get status for {resource_type} {name}: {e}")
        return "Unknown"


def get_resource_capacity(api_instance, resource_type, name, namespace=None):
    """
    Retrieve the capacity of a Kubernetes resource.
    
    Args:
        api_instance (client.CoreV1Api): Kubernetes API instance.
        resource_type (str): Type of the resource ('pvc', 'volume').
        name (str): Name of the resource.
        namespace (str, optional): Namespace for PVCs.
        
    Returns:
        str: Capacity of the resource.
    """
    try:
        if resource_type == 'pvc':
            pvc = api_instance.read_namespaced_persistent_volume_claim(name=name, namespace=namespace)
            return pvc.spec.resources.requests['storage']
        
        if resource_type == 'volume':
            volume = api_instance.read_persistent_volume(name=name)
            return volume.spec.capacity['storage']
            
    except Exception as e:
        print(f"Failed to get capacity for {resource_type} {name}: {e}")
        return "Unknown"


def create_resource_graph(pods, pvcs, volumes, api_instance):
    """Create a directed graph of Kubernetes resources."""
    G = nx.DiGraph()
    pvc_names = set()
    
    for pod in pods:
        pod_name = pod.metadata.name
        pod_status = get_resource_status(api_instance, 'pod', pod.metadata.namespace, pod_name)
        G.add_node(pod_name, label=f"{pod_name}\nStatus: {pod_status}")
        
        for volume in pod.spec.volumes:
            if volume.persistent_volume_claim:
                pvc_name = volume.persistent_volume_claim.claim_name
                pvc_names.add(pvc_name)
                pvc_capacity = get_resource_capacity(api_instance, 'pvc', pvc_name, pod.metadata.namespace)
                pvc_status = get_resource_status(api_instance, 'pvc', pod.metadata.namespace, pvc_name)
                G.add_node(pvc_name, label=f"{pvc_name}\nCapacity: {pvc_capacity}\nStatus: {pvc_status}\nType: PVC")
                G.add_edge(pod_name, pvc_name, label='uses')
    
    for pvc in pvcs:
        if pvc.metadata.name in pvc_names:
            pvc_name = pvc.metadata.name
            pvc_capacity = get_resource_capacity(api_instance, 'pvc', pvc_name, pvc.metadata.namespace)
            pvc_status = get_resource_status(api_instance, 'pvc', pvc.metadata.namespace, pvc_name)
            G.add_node(pvc_name, label=f"{pvc_name}\nCapacity: {pvc_capacity}\nStatus: {pvc_status}\nType: PVC")
            
            if pvc.spec.volume_name:
                volume_name = pvc.spec.volume_name
                volume_capacity = get_resource_capacity(api_instance, 'volume', volume_name)
                volume_status = get_resource_status(api_instance, 'volume', None, volume_name)
                G.add_node(volume_name, label=f"{volume_name}\nCapacity: {volume_capacity}\nStatus: {volume_status}\nType: Volume")
                G.add_edge(pvc_name, volume_name, label='bound to')
    
    for volume in volumes:
        volume_name = volume.metadata.name
        volume_capacity = get_resource_capacity(api_instance, 'volume', volume_name)
        volume_status = get_resource_status(api_instance, 'volume', None, volume_name)
        G.add_node(volume_name, label=f"{volume_name}\nCapacity: {volume_capacity}\nStatus: {volume_status}\nType: Volume")
    
    return G


def draw_graph(G):
    """Draw the directed graph of Kubernetes resources."""
    pos = nx.spring_layout(G, seed=42)
    labels = nx.get_edge_attributes(G, 'label')
    node_labels = nx.get_node_attributes(G, 'label')

    plt.figure(figsize=(14, 10))
    nx.draw(G, pos, with_labels=True, labels=node_labels, node_size=3000,
            node_color='lightblue', font_size=10, font_weight='bold')
    nx.draw_networkx_edge_labels(G, pos, edge_labels=labels, font_color='red')
    plt.title("Kubernetes Resource Graph")
    plt.show()


def fetch_resources(api_instance, namespaces, pod_patterns):
    """Fetch Kubernetes resources (pods, PVCs, volumes) from the specified namespaces."""
    def matches_pattern(name, patterns):
        """Check if the pod name matches any of the provided patterns."""
        return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)

    pods = []
    pvcs = []

    if namespaces:
        with ThreadPoolExecutor() as executor:
            all_pods = sum(executor.map(lambda ns: get_resources(api_instance, 'pods', ns), namespaces), [])
            if pod_patterns:
                pods = [pod for pod in all_pods if matches_pattern(pod.metadata.name, pod_patterns)]
            else:
                pods = all_pods

            pvcs = sum(executor.map(lambda ns: get_resources(api_instance, 'pvcs', ns), namespaces), [])
    else:
        all_pods = get_resources(api_instance, 'pods')
        if pod_patterns:
            pods = [pod for pod in all_pods if matches_pattern(pod.metadata.name, pod_patterns)]
        else:
            pods = all_pods

        pvcs = get_resources(api_instance, 'pvcs')

    volumes = get_resources(api_instance, 'volumes')
    return pods, pvcs, volumes


def main(kubeconfig_path, namespaces, pod_patterns):
    """Main function to generate and display the Kubernetes resource graph."""
    if not (namespaces or not pod_patterns):
        raise ValueError("Pod patterns (-p) can only be used with namespaces (-n).")

    load_kube_config(kubeconfig_path)
    api_instance = client.CoreV1Api()

    pods, pvcs, volumes = fetch_resources(api_instance, namespaces, pod_patterns)
    G = create_resource_graph(pods, pvcs, volumes, api_instance)
    draw_graph(G)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Generate a graph of Kubernetes resources such as Pods, Persistent Volume Claims (PVCs), "
            "and Persistent Volumes (PVs). Fetches resources from specified Kubernetes namespaces and "
            "visually represents their relationships.\n\n"
        ),
        epilog=(
            "Example usage:\n"
            "  python graph.py -k ~/.kube/config -n default -p pod-name-1-hash pod-name-2-*\n"
        )
    )
    parser.add_argument(
        '-k', '--kubeconfig',
        type=str,
        default=os.path.expanduser("~/.kube/config"),
        help='Path to the kubeconfig file (default: ~/.kube/config).'
    )
    parser.add_argument(
        '-n', '--namespaces',
        type=str,
        nargs='*',
        default=None,
        help='Kubernetes namespace(s) to use. If not specified, fetches resources from all namespaces.'
    )
    parser.add_argument(
        '-p', '--pods',
        type=str,
        nargs='*',
        default=None,
        help='Pod name patterns to filter. Use wildcard patterns as needed.'
    )
    args = parser.parse_args()

    main(args.kubeconfig, args.namespaces, args.pods)
