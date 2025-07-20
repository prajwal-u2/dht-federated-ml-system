from thrift.transport import TSocket, TTransport
from thrift.protocol import TBinaryProtocol
from thrift.server import TServer
import random
import sys
import hashlib
sys.path.append("gen-py")
from supernode.Supernode import Processor, JoinResponse


class SupernodeHandler:
    

    def __init__(self):
        
        self.active_nodes = {}
        self.nodes_in_network={}
        self.max_nodes = 10
        self.pending_node = None
        self.pending_node_info = None  # Temporary storage for the node until it confirms
        
        
    def remove_join(self, node_id):
        del self.active_nodes[node_id]
      
        
    def get_compute_node_ip(self, port, filename="compute_node.txt"):
        
        with open(filename, "r") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue  
                ip, port_str = line.split(",")
                if int(port_str) == port:
                    return ip


    def request_join(self, port):
        
        """Handles the request for a node to join the network."""
        if self.pending_node:
            print("Another node is in process of joining.")
            return JoinResponse(id=-1)  # NACK: Node joining in progress
        
        if len(self.nodes_in_network) >= self.max_nodes:
            print("Network is full.")
            return JoinResponse(id=-2)  # NACK: Network full

        new_id = int(hashlib.sha1(str(port).encode()).hexdigest(), 16) % 64
        print(f"Assigning ID {new_id} to the new node.")

        # Temporarily store the node's details until it confirms the join
        compute_ip = self.get_compute_node_ip(port)
        self.pending_node = new_id
        self.pending_node_info = (compute_ip, port)
        self.active_nodes[new_id] = self.pending_node_info
        
        no_of_nodes_in_network = len(self.nodes_in_network)
        
        # First node in the network
        return JoinResponse(id=new_id, no_of_nodes= no_of_nodes_in_network)


    def confirm_join(self, node_id):
        
        """Confirms the node's successful join after it has completed the necessary setup."""
        if self.pending_node == node_id:
            # Add node to active nodes after confirmation
            self.nodes_in_network[node_id] = self.pending_node_info
            self.active_nodes[node_id] = self.pending_node_info

            print(f"Node {node_id} confirmed its join.")
            self.pending_node = None
            self.pending_node_info = None  # Clear the temporary data
            return True
        
        print("Invalid confirmation request.")
        return False


    def get_node(self):
        
        """Returns a random active node."""
        if not self.nodes_in_network:
            print("Error: No active nodes available.")
            return "Error: No active nodes"
        node_id, node_info = random.choice(list(self.nodes_in_network.items()))
        print(f"Returning random active node: ID {node_id}, Address {node_info[0]}:{node_info[1]}")
        return f"{node_id}:{node_info[0]}:{node_info[1]}"
    
    
    def get_compute_node_address(self, node_id):
        node_info = self.active_nodes[node_id]
        return f"{node_info[0]}:{node_info[1]}"

# Set up the Supernode server
handler = SupernodeHandler()
processor = Processor(handler)
transport = TSocket.TServerSocket(port=9091)  # Port for supernode
tfactory = TTransport.TBufferedTransportFactory()
pfactory = TBinaryProtocol.TBinaryProtocolFactory()

print("Supernode is running on port 9091...")
server = TServer.TThreadedServer(processor, transport, tfactory, pfactory)
server.serve()