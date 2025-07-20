import hashlib
import os
import sys
import time
import numpy as np
import sys
sys.path.append("gen-py")
from thrift.transport import TSocket, TTransport
from thrift.protocol import TBinaryProtocol
from compute_node.ComputeNode import Client as ComputeNodeClient
from supernode.Supernode import Client as SupernodeClient
from ML.ML import mlp


def connect_to_supernode(ip, port):
    transport = TSocket.TSocket(ip, port)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = SupernodeClient(protocol)
    transport.open()
    return client, transport


def connect_to_compute_node(ip, port):
    transport = TSocket.TSocket(ip, port)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = ComputeNodeClient(protocol)
    transport.open()
    return client, transport


def average_models(models):
    
    model_list = list(models)
    init_model =mlp()
    init_model.init_training_random("validate_letters.txt", 26, 20)
    sum_V = None
    sum_W = None
    
    for model in model_list: 
        gradV = np.array(model.V, dtype=float)
        gradW = np.array(model.W, dtype=float)
        
        if sum_V is None:
            sum_V = gradV
            sum_W = gradW
            
        else:
            sum_V += gradV
            sum_W += gradW 
            
    count = len(model_list)   
    avg_V = (sum_V / count).tolist()
    avg_W = (sum_W / count).tolist()   
    
    return avg_V, avg_W    


if __name__ == "__main__":
    
    if len(sys.argv) != 3:
        print("Usage: python client.py <supernode_ip> <supernode_port>")
        sys.exit(1)

    supernode_ip = sys.argv[1]
    supernode_port = int(sys.argv[2])

    # Get initial node
    super_client, super_trans = connect_to_supernode(supernode_ip, supernode_port)
    node_info = super_client.get_node().split(':')
    super_trans.close()

    node_id, node_ip, node_port = node_info[0], node_info[1], int(node_info[2])
    node_client, node_trans = connect_to_compute_node(node_ip, node_port)
    print(f"Connected to node {node_id} at {node_ip}:{node_port}")
    
    no_of_files=20

    try:
        all_files = os.listdir("letters")
        files = all_files[:no_of_files] 
    except FileNotFoundError:
        print("Error: letters directory not found")
        sys.exit(1)

    # Distribute both files
    for filename in files:
        
        try:
            node_client.put_data(filename)
            print(f"Submitted {filename}",int(hashlib.sha1(filename.encode()).hexdigest(), 16) % (2 ** 6))
        except Exception as e:
            print(f"Error submitting {filename}: {e}")
            sys.exit(1)

    # Collect models with retries
    models = {}
    attempts = 0
    max_attempts = 10
    
    while len(models) < no_of_files and attempts < max_attempts:
        for filename in files:
            if filename in models:
                continue
                
            try:
                model = node_client.get_model(filename)
                if model.status == 'done':
                    models[filename] = model
                    print(f"Acquired model for {filename}")
                elif model.status == 'wait':
                    print(f"Waiting for {filename}...")
                else:
                    print(f"Error with {filename}")
            except Exception as e:
                print(f"Error retrieving {filename}: {e}")
        
        if len(models) < no_of_files:
            print(f"Retry {attempts+1}/{max_attempts}")
            time.sleep(5)
            attempts += 1

    if len(models) != no_of_files:
        print("Failed to collect both models")
        sys.exit(1)
    
    # Aggregate and validate
    print("Aggregating models...")
    avg_V, avg_W = average_models(models.values())


    final_model = mlp()
    avg_V = np.multiply(avg_V, 0.1)
    # Scale down the weight matrix V if necessary
    final_model.init_training_model("validate_letters.txt", avg_V, avg_W)  # Fixed model name
    error = final_model.validate("validate_letters.txt")
    print(f"Final validation error: {error:.2f}%")

    node_trans.close()