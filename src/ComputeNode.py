import hashlib
import os
import threading
from thrift.transport import TSocket, TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
import socket
import numpy as np
import sys
sys.path.append("gen-py")
import ML.ML
from compute_node.ComputeNode import (
    Processor, 
    Client as ComputeNodeClient,
    Model 
)
import ML
from supernode.Supernode import Client as SupernodeClient

class ComputeNodeHandler:
    def __init__(self, node_port, supernode_ip, supernode_port):
        self.node_port = node_port
        self.supernode_ip = supernode_ip
        self.supernode_port = supernode_port
        self.predecessor = None
        self.successor = None
        self.finger_table = {}
        self.active_nodes = {}
        self.model = ML.ML.mlp()
        self.models = {}
        self.training_status = {}
        self.m = 6  # Chord ring size (2^6 = 64)
        self.node_path = []

        # Flag to indicate whether the global model has been initialized.
        self.global_model_initialized = False
        # Lock to protect model initialization and updates across threads.
        self.model_lock = threading.Lock()

        if self.join_network():
            self.confirm_join()

    def hash_filename(self, filename):
        """Return a hashed integer ID for the given filename modulo 2**m."""
        return int(hashlib.sha1(filename.encode()).hexdigest(), 16) % (2 ** self.m)
    
    
    def print_info(self, filename):
        print(f"\n=== Node {self.node_id} ===")
        print(f"Processing file: {filename}")
        print(f"Path taken: {' -> '.join(map(str, self.node_path))}")
        print(f"Predecessor: {self.predecessor}")
        print(f"Successor: {self.successor}")
        print("Finger Table:")
        for k, v in sorted(self.finger_table.items()):
            print(f"  Entry {k}: Start {v['start']} -> Node {v['node']}")
        print("=======================")


    def put_data(self, filename):
        """Route file data to the correct node for training."""
        hashed_id = self.hash_filename(filename)
        successor, path = self.find_successor_with_path(hashed_id)
        
        self.node_path = path
        self.print_info(filename)

        if successor == self.node_id:
            print(f"Starting training for {filename} on node {self.node_id}")
            print("Put Data -  Model - filename: ", filename, "ID:", hashed_id)
            self.start_training(filename)
        else:
            self.forward_to_node(successor, filename)
    
    
    def start_training(self, filename):
        """Begin training for the file if not already training."""
        if self.training_status.get(filename) == 'training':
            return
        self.training_status[filename] = 'training'
        threading.Thread(target=self.train_model, args=(filename,)).start()


    def train_model(self, filename):
        """Train the model using the file and compute weight gradients."""
        try:
            K = 26
            H = 20
            eta = 0.0001
            epochs = 250

            filepath = f"letters/{filename}"
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Training file {filepath} not found")

            self.model.init_training_random(filepath, K, H)
            # Save the initial weights (before training on this file)
            init_V, init_W = self.model.get_weights()

            # Convert initial weights to numpy arrays for later gradient computation.
            init_V = np.array(init_V)
            init_W = np.array(init_W)

            # Train the model on the current file.
            error_rate = self.model.train(eta=eta, epochs=epochs)

            # Compute gradients as the difference: (final - initial)
            final_V, final_W = self.model.get_weights()
            final_V_np = np.array(final_V, dtype=float)
            final_W_np = np.array(final_W, dtype=float)

            grad_V = (final_V_np - init_V).tolist()
            grad_W = (final_W_np - init_W).tolist()

            # Save the computed gradients and training error in our local structure.
            self.models[filename] = Model(
                V=grad_V,
                W=grad_W,
                error_rate=error_rate,
                status='done'
            )
            self.training_status[filename] = 'done'
            print(f"Computed gradients for {filename} (error rate: {error_rate:.4f})")

        except Exception as e:
            print(f"Training failed for {filename}: {str(e)}")
            self.models[filename] = Model(status='failed')
            self.training_status[filename] = 'failed'
            import traceback
            traceback.print_exc()
     
          
    def get_model(self, filename):
        """Retrieve the trained model for a given filename or forward the request."""
        hashed_id = self.hash_filename(filename)
        successor, path = self.find_successor_with_path(hashed_id)
        
        self.node_path = path
        self.print_info(filename)

        if successor != self.node_id:
            return self.forward_to_node(successor, filename, get_model=True)
            
        model = self.models.get(filename)
        print("Get Model - filename: ", filename, "ID:", hashed_id)

        if not model:
            status = 'wait' if self.training_status.get(filename) == 'training' else 'not_found'
            return Model(status=status)
            
        return model


    def find_successor_with_path(self, node_id):
        """Find the successor for a given node ID and return the path taken."""
        path = [self.node_id]
        if self.node_in_interval(self.node_id, node_id, self.successor):
            return self.successor, path + [self.successor]
            
        n0 = self.closest_preceding_node(node_id)
        path.append(n0)
        
        while True:
            addr = self.get_node_address(n0)
            if not addr: break
            
            ip, port = addr.split(':')
            client, transport = self.connect_to_compute_node(ip, int(port))
            if not client: break
            
            try:
                successor = client.find_successor(node_id)
                path.append(successor)
                return successor, path
            finally:
                transport.close()
    
    
    def forward_to_node(self, node_id, filename, get_model=False):
        """Forward the file or model request to the specified node."""
        addr = self.get_node_address(node_id)
        if not addr: return {'status': 'error'}
        
        ip, port = addr.split(':')
        client, transport = self.connect_to_compute_node(ip, int(port))
        if not client: return {'status': 'error'}
        
        try:
            if get_model:
                return client.get_model(filename)
            client.put_data(filename)
            return {'status': 'forwarded'}
        finally:
            transport.close()


    def join_network(self):
        """Join the network by registering with the supernode and updating state."""
        try:
            print("In Join Network")
            client, transport = self.connect_to_super_node()
            join_response = client.request_join(self.node_port)
            self.node_id = int(join_response.id)
            self.no_of_nodes = join_response.no_of_nodes

            if self.no_of_nodes == 0:
                for i in range(self.m):
                    start = (self.node_id + 2**i) % (2**self.m)
                    self.finger_table[i] = {'start': start, 'node': self.node_id}
                self.successor = self.node_id
                self.predecessor = self.node_id
                print(f"Single-node ring initialized with ID {self.node_id}.")
                transport.close()
                self.print_finger_table()
                return True
            
            connection_point = client.get_node()
            node_id, ip, port = connection_point.split(':')
            self.active_nodes[int(node_id)] = (ip, port)
            port = int(port)
            transport.close()

            self.print_finger_table()
            for x in self.active_nodes.items():
                print('Active Node: ', x)

            self.fix_fingers(int(node_id))
            self.update_others()
            return True

        except Exception as e:
            print(f"Error during join_network: {e}")
            return False


    def print_finger_table(self):
        """Print the current finger table and node relationships."""
        print(f"\nFinger Table for Node {self.node_id}:")
        print("Predecessor:", self.predecessor)
        print("Successor:", self.successor)
        for k in sorted(self.finger_table.keys()):
            v = self.finger_table[k]
            print(f"Finger {k}: Start = {v['start']}, Successor = {v['node']}")
        print("-" * 30)


    def get_predecessor(self):
        """Return the predecessor node."""
        return self.predecessor


    def set_successor(self, node_id):
        self.successor = node_id
        return True


    def get_successor(self):
        return self.successor


    def set_predecessor(self, node_id):
        self.predecessor = int(node_id)
        return True


    def fix_fingers(self, node_id):
        """Update the finger table entries using the specified node as reference."""
        print("\n=== Fixing Fingers ===")
        if node_id == self.node_id:
            return
        
        connection_address = self.get_node_address(node_id)
        if not connection_address:
            print("Failed to get connection address")
            return
            
        ip, port = connection_address.split(':')
        compute_node_client, transport = self.connect_to_compute_node(ip, int(port))
        if not compute_node_client:
            print("Failed to connect to compute node")
            return

        try:
            for i in range(self.m):
                start = (self.node_id + 2**i) % (2**self.m)
                # Special handling for last finger to ensure correct successor
                if i == self.m - 1 and self.node_id > start:
                    successor = self.node_id
                else:
                    successor = compute_node_client.find_successor(start)
                self.finger_table[i] = {'start': start, 'node': int(successor)}
                print(f"Finger {i}: start={start}, successor={successor}")
            
            # Set successor to the immediate next node
            self.successor = self.finger_table[0]['node']
            
            print("\nInitial finger table:")
            self.print_finger_table()

            # Update predecessor/successor relationships
            successor_address = self.get_node_address(self.successor)
            if successor_address:
                succ_ip, succ_port = successor_address.split(':')
                successor_client, succ_transport = self.connect_to_compute_node(succ_ip, int(succ_port))
                if successor_client:
                    try:
                        print(f"\nGetting predecessor of successor {self.successor}")
                        pred = successor_client.get_predecessor()
                        self.predecessor = int(pred) if pred is not None else None
                        print(f"Setting predecessor of {self.successor} to {self.node_id}")
                        successor_client.set_predecessor(self.node_id)
                    finally:
                        succ_transport.close()

            print("\nFinal finger table after fixing fingers:")
            self.print_finger_table()
            
        except Exception as e:
            print(f"Error in fix_fingers: {e}")
        finally:
            transport.close()


    def node_in_interval(self, start, node_id, end):
        """Determine if node_id lies within the interval (start, end] in the ring."""
        if start == end:
            return True
        if start < end:
            return start < node_id <= end
        else:
            return node_id > start or node_id <= end


    def connect_to_compute_node(self, ip, port):
        """Establish a connection to a compute node at the given IP and port."""
        try:
            transport = TSocket.TSocket(ip, int(port))
            transport = TTransport.TBufferedTransport(transport)
            protocol = TBinaryProtocol.TBinaryProtocol(transport)
            client = ComputeNodeClient(protocol)
            transport.open()
            return client, transport
        except Exception as e:
            print(f"Error connecting to compute node {ip}:{port} - {e}")
            return None, None


    def connect_to_super_node(self):
        """Establish a connection to the supernode using stored IP and port."""
        try:
            transport = TSocket.TSocket(self.supernode_ip, self.supernode_port)
            transport = TTransport.TBufferedTransport(transport)
            protocol = TBinaryProtocol.TBinaryProtocol(transport)
            client = SupernodeClient(protocol)
            transport.open()
            return client, transport
        except Exception as e:
            print(f"Error connecting to super node {self.supernode_ip}:{self.supernode_port} - {e}")
            return None, None


    def find_successor(self, node_id):
        """Find and return the successor for the given node ID in the network."""
        if self.node_id == node_id:
            return self.successor if self.successor != self.node_id else self.successor
            
        predecessor_node_id = self.find_predecessor(node_id)
        if predecessor_node_id == self.node_id:
            return self.successor if self.successor is not None else self.node_id
            
        connection_address = self.get_node_address(predecessor_node_id)
        if not connection_address:
            print("Failed to get predecessor address")
            return None
            
        ip, port = connection_address.split(':')
        client, transport = self.connect_to_compute_node(ip, int(port))
        if not client:
            print("Failed to connect to predecessor")
            return None
            
        try:
            return client.get_successor()
        finally:
            transport.close()


    def find_predecessor(self, node_id):
        """Locate and return the predecessor for the given node ID."""
        node = self.node_id
        succ_node = self.successor if self.successor is not None else self.node_id
        visited = set()
        max_hops = 10
        hop_count = 0

        while not self.node_in_interval(node, node_id, succ_node):
            if hop_count > max_hops or node in visited:
                print("Max hops exceeded or loop detected")
                return node
                
            visited.add(node)
            hop_count += 1
            
            next_node = self.closest_preceding_node(node_id)
            if next_node == node:
                break

            connection_address = self.get_node_address(next_node)
            if not connection_address:
                break

            ip, port = connection_address.split(':')
            client, transport = self.connect_to_compute_node(ip, int(port))
            if not client:
                break

            try:
                node = next_node
                succ_node = client.get_successor()
            except Exception as e:
                print(f"Error during predecessor finding: {e}")
                break
            finally:
                transport.close()

        return node


    def closest_preceding_node(self, id):
        """Return the closest preceding node for the given ID based on the finger table."""
        for i in range(self.m - 1, -1, -1):
            if i in self.finger_table:
                finger_node = self.finger_table[i]['node']
                if finger_node != self.node_id and self.node_in_interval(self.node_id, finger_node, id):
                    return finger_node
        return self.node_id


    def confirm_join(self):
        """Confirm the node's join to the network with the supernode."""
        client, transport = self.connect_to_super_node()
        if not client:
            print("Failed to connect to supernode for confirmation")
            return
            
        try:
            client.confirm_join(self.node_id)
        finally:
            transport.close()


    def get_node_address(self, node_id):
        """Retrieve the compute node address for the given node ID from the supernode."""
        client, transport = self.connect_to_super_node()
        if not client:
            print("Failed to connect to supernode")
            return None
            
        try:
            return client.get_compute_node_address(int(node_id))
        finally:
            transport.close()


    def update_others(self):
        """Update the finger tables of all other nodes in the network."""
        print("\n=== Updating Other Nodes' Finger Tables ===")
        for i in range(self.m):
            pred_id = (self.node_id - (2 ** i)) % (2 ** self.m)
            pred_node_id = self.find_predecessor(pred_id)
            
            if pred_node_id == self.node_id:
                print(f"Skipping finger[{i}] - predecessor is self")
                continue
                
            connection_address = self.get_node_address(pred_node_id)
            if not connection_address:
                print(f"Couldn't get address for predecessor {pred_node_id}")
                continue
                
            ip, port = connection_address.split(':')
            client, transport = self.connect_to_compute_node(ip, int(port))
            if not client:
                print(f"Couldn't connect to {pred_node_id}")
                continue
                
            try:
                print(f"\nUpdating node {pred_node_id}'s finger[{i}] to point to {self.node_id}")
                print("Before update:")
                client.print_finger_table()
                
                updated = client.update_finger_table(self.node_id, i)
                
                print("\nAfter update:")
                client.print_finger_table()
                
                if updated and i == 0:  # Only update successor for finger[0]
                    client.set_successor(self.node_id)
                    print("\nAfter setting successor:")
                    client.print_finger_table()
            except Exception as e:
                print(f"Error updating finger table: {e}")
            finally:
                transport.close()

        print("\n=== Finished Updating Others ===")
        print("My final finger table:")
        self.print_finger_table()


    def update_finger_table(self, node_id, index):
        """Update the finger table entry at the given index with the new node ID."""
        print(f"\nProcessing update request for finger[{index}] to point to {node_id}")
        if index not in self.finger_table:
            return False
            
        current_node = self.finger_table[index]['node']
        print(f"Current finger[{index}]: {current_node}")
        
        if node_id == self.node_id:
            print("Update skipped - cannot point to ourselves")
            return False
            
        start = self.finger_table[index]['start']
        
        if self.node_in_interval(self.node_id, node_id, current_node) or current_node == self.node_id:
            print(f"Updating finger[{index}] from {current_node} to {node_id}")
            self.finger_table[index]['node'] = int(node_id)
            
            # If this is finger[0], update successor
            if index == 0:
                self.set_successor(node_id)
            
            if self.predecessor and self.predecessor != self.node_id:
                print(f"Notifying predecessor {self.predecessor}")
                self.notify_predecessor_update(node_id, index)
            return True
        else:
            print(f"No update needed - {node_id} not in ({self.node_id}, {current_node}]")
            return False


    def notify_predecessor_update(self, node_id, index):
        """Notify the predecessor node to update its finger table at the specified index."""
        connection_address = self.get_node_address(self.predecessor)
        if not connection_address:
            print("Failed to get predecessor address")
            return
            
        ip, port = connection_address.split(':')
        client, transport = self.connect_to_compute_node(ip, int(port))
        if not client:
            print("Failed to connect to predecessor")
            return
            
        try:
            client.update_finger_table(node_id, index)
        except Exception as e:
            print(f"Error notifying predecessor: {e}")
        finally:
            transport.close()


def start_compute_node(port, supernode_ip, supernode_port):
    handler = ComputeNodeHandler(port, supernode_ip, supernode_port)
    processor = Processor(handler)
    transport = TSocket.TServerSocket(port=port)
    tfactory = TTransport.TBufferedTransportFactory()
    pfactory = TBinaryProtocol.TBinaryProtocolFactory()
    server = TServer.TThreadedServer(processor, transport, tfactory, pfactory)
    print(f"Compute Node {handler.node_id} running on port {port}")
    server.serve()


if __name__ == "__main__":
    port = int(sys.argv[1])
    supernode_ip = sys.argv[2]
    supernode_port = int(sys.argv[3])
    start_compute_node(port, supernode_ip, supernode_port)