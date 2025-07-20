namespace py compute_node

struct Model {
    1: list<list<double>> V,
    2: list<list<double>> W,
    3: double error_rate,
    4: string status
}

service ComputeNode {
  oneway void put_data(1: string filename),
  
  Model get_model(1: string filename),
  
  void fix_fingers(),
  
  i32 find_successor(1: i32 node_id),
  
  i32 find_predecessor(1: i32 node_id),
  
  void update_finger_table(1: i32 node_id, 2: i32 index),

  i32 get_predecessor(),

  i32 get_successor(),

  bool set_predecessor(1: i32 node_id),

  i32 closest_preceding_node(1: i32 node_id),

  void set_successor(),

  void print_finger_table()
}