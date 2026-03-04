#ifndef GRAPH_H
#define GRAPH_H

#include <vector>
#include <map>
#include <random>

// Edge representing a road
struct Edge {
    int src;
    int dst;
    double base_weight;
    double traffic_multiplier;
};

class Graph {
private:
    int num_nodes;
    std::vector<Edge> edges;
    std::vector<std::vector<Edge>> adj_list;

public:
    Graph(int nodes);
    
    // Add a directed edge
    void add_edge(int src, int dst, double weight);
    
    // Generates a random connected graph
    void generate_random_graph(int num_edges, unsigned int seed = 42);
    
    // Randomizes the traffic multiplier on edges
    void apply_traffic_updates(double max_multiplier = 3.0, unsigned int seed = 42);

    int get_num_nodes() const;
    const std::vector<Edge>& get_edges() const;
    const std::vector<std::vector<Edge>>& get_adj_list() const;
};

#endif // GRAPH_H
