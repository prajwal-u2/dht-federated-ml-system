# Execution Steps

## 1. Unzip the Folder
- Extract the zipped folder (e.g., distributed_training.zip) into a local directory of your choice.
- Navigate to the extracted folder.

## 2. Create Virtual Environment and Install Requirements
```bash
python3 -m venv myenv
source myenv/bin/activate  # On Windows: myenv\Scripts\activate
pip install -r requirements.txt
```
Execute the ComputeNode, Supernode and client in the virtual environment.

## 3. Configure Compute Nodes Text File
Open the file `compute_node.txt` and ensure it lists the host and port for each compute node you plan to run.

**Example**:
```
127.0.0.1,5001
127.0.0.1,5002
127.0.0.1,5003
```

## 4. Generate Thrift Files
```bash
thrift --gen py supernode.thrift
thrift --gen py compute_node.thrift
```

## 5. Start the Supernode
```bash
python3 Supernode.py
```
**Note**: Supernode.py runs on port 9091

## 6. Start the Compute Nodes
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

## 7. Run the Client
Once the Supernode and ComputeNodes are running, open another terminal for the client:
```bash
python3 client.py <supernode_ip> <supernode_port>
```

**Example**:
```bash
python3 client.py 127.0.0.1 9091
```

## 8. Monitor Output
- You can find the final validation results after training in the client console.
- You can find the routing and finger tables in the compute nodes console once each compute node comes up.
