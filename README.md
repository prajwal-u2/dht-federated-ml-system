# DHT Federated ML System

A distributed federated machine learning system that implements a decentralized peer-to-peer network using the Chord DHT (Distributed Hash Table) protocol. This system enables collaborative machine learning across multiple compute nodes without centralized data storage.

## Overview

This project implements a federated learning system where multiple compute nodes collaborate to train machine learning models while maintaining data privacy. The system uses a Chord DHT network for node discovery, task distribution, and result aggregation.

## Features

- **Distributed Hash Table (DHT)**: Implements Chord protocol for decentralized node management
- **Federated Learning**: Collaborative ML training without data centralization
- **Thrift RPC**: Efficient communication between nodes using Apache Thrift
- **Fault Tolerance**: System continues operation even when some nodes fail
- **Scalable Architecture**: Easy to add or remove compute nodes dynamically

## Architecture

### Components

1. **Supernode**: Central coordinator that manages the DHT network and distributes ML tasks
2. **Compute Nodes**: Individual nodes that perform ML computations and maintain DHT routing tables
3. **Client**: Interface for submitting ML tasks and retrieving results

### Network Structure

- **Chord DHT**: Each node maintains a finger table for efficient routing
- **Consistent Hashing**: Nodes are distributed across a circular identifier space
- **Fault Tolerance**: Automatic node failure detection and recovery

## Prerequisites

- Python 3.7+
- Apache Thrift
- Required Python packages (see `requirements.txt`)

## Installation

1. **Clone or extract the project**
   ```bash
   # If using git
   git clone <repository-url>
   cd dht-federated-ml-system
   
   # If using zip file
   # Extract the zipped folder (e.g., distributed_training.zip) into a local directory
   # Navigate to the extracted folder
   ```

2. **Create Virtual Environment and install requirements**
   ```bash
   python3 -m venv myenv
   source myenv/bin/activate  # On Windows: myenv\Scripts\activate
   pip install -r requirements.txt
   ```

## Execution Steps

### 1. Configure Compute Nodes
Open the file `compute_node.txt` and ensure it lists the host and port for each compute node you plan to run:
```
127.0.0.1,5001
127.0.0.1,5002
127.0.0.1,5003
```

### 2. Generate Thrift Files
```bash
thrift --gen py supernode.thrift
thrift --gen py compute_node.thrift
```

### 3. Start the Supernode
```bash
python3 Supernode.py
```
**Note**: Supernode runs on port 9091

### 4. Start Compute Nodes
Open additional terminals—one for each compute node:
```bash
python3 ComputeNode.py <port> <supernode_ip> <supernode_port>
```

**Examples**:
```bash
python3 ComputeNode.py 5001 127.0.0.1 9091
python3 ComputeNode.py 5002 127.0.0.1 9091
python3 ComputeNode.py 5003 127.0.0.1 9091
```

Each node will start listening on its respective port and be ready to accept tasks from other nodes.

### 5. Run the Client
Once the Supernode and ComputeNodes are running, open another terminal for the client:
```bash
python3 client.py <supernode_ip> <supernode_port>
```

**Example**:
```bash
python3 client.py 127.0.0.1 9091
```

## Output and Monitoring

- **Final Validation**: You can find the final validation results after training in the client console
- **Routing Tables**: You can find the routing and finger tables in the compute nodes console once each compute node comes up
- **Network Status**: Monitor node connections and DHT structure through console outputs

## Project Structure

```
dht-federated-ml-system/
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── src/                      # Source code directory
│   ├── Supernode.py         # Supernode implementation
│   ├── ComputeNode.py       # Compute node implementation
│   ├── client.py            # Client interface
│   ├── supernode.thrift     # Thrift interface for supernode
│   ├── compute_node.thrift  # Thrift interface for compute nodes
│   ├── compute_node.txt     # Compute node configuration
│   ├── ML/                  # Machine learning components
│   │   ├── ML.py           # Python ML implementation
│   │   ├── ML.cpp          # C++ ML implementation
│   │   └── ML.hpp          # C++ header file
│   └── gen-py/             # Generated Thrift Python files
└── reports/                # Project documentation
```

## Troubleshooting

1. **Port Conflicts**: Ensure no other services are using the required ports (9091, 5001, 5002, etc.)
2. **Thrift Generation**: Make sure Apache Thrift is properly installed and accessible
3. **Virtual Environment**: Ensure you're running all commands within the activated virtual environment
4. **Network Connectivity**: Verify that all nodes can communicate on the specified IP addresses

## Contributing

This project is designed for educational purposes in distributed systems and federated learning. Feel free to extend the functionality or improve the implementation.

## License

This project is for educational use. Please refer to your course guidelines for usage restrictions.
