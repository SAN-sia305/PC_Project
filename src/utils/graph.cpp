#include "graph.h"
#include <iostream>

Graph::Graph(int nodes) : num_nodes(nodes) {
    adj_list.resize(nodes);
}

void Graph::add_edge(int src, int dst, double weight) {
    Edge e = {src, dst, weight, 1.0};
    edges.push_back(e);
    adj_list[src].push_back(e);
}

void Graph::generate_random_graph(int num_edges, unsigned int seed) {
    std::mt19937 gen(seed);
    std::uniform_int_distribution<> node_dist(0, num_nodes - 1);
    std::uniform_real_distribution<> weight_dist(5.0, 50.0);

    for (int i = 0; i < num_edges; ++i) {
        int src = node_dist(gen);
        int dst = node_dist(gen);
        
        // Prevent self loops
        while (src == dst) {
            dst = node_dist(gen);
        }

        double weight = weight_dist(gen);
        add_edge(src, dst, weight);
        // Assuming bidirectional roads for simplicity
        add_edge(dst, src, weight);
    }
}

void Graph::apply_traffic_updates(double max_multiplier, unsigned int seed) {
    std::mt19937 gen(seed);
    std::uniform_real_distribution<> mult_dist(1.0, max_multiplier);

    for (auto& edge : edges) {
        edge.traffic_multiplier = mult_dist(gen);
    }

    // Also update adjacency list items
    for (auto& adj_row : adj_list) {
        for (auto& e : adj_row) {
            e.traffic_multiplier = mult_dist(gen);
        }
    }
}

int Graph::get_num_nodes() const {
    return num_nodes;
}

const std::vector<Edge>& Graph::get_edges() const {
    return edges;
}

const std::vector<std::vector<Edge>>& Graph::get_adj_list() const {
    return adj_list;
}
