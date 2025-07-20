namespace py supernode

struct JoinResponse {
  1: i32 id,
  2: i32 no_of_nodes
}

service Supernode {
  JoinResponse request_join(1: i32 port),
  bool confirm_join(1: i32 node_id),
  string get_node(),
  string get_compute_node_address(1: i32 node_id)
  void remove_join(1: i32 node_id)
}