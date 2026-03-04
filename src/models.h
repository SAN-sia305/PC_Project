#ifndef MODELS_H
#define MODELS_H

#include <string>

// Struct representing a package delivery request
struct Delivery {
    int id;
    int src_node;
    int dst_node;
    double deadline; // Required delivery deadline (time factor)
    double weight;   // Payload weight in arbitrary units
};

// Struct representing an instantiated vehicle available to carry deliveries
struct Vehicle {
    int id;
    int current_location; // Corresponding to a node ID in the graph
    double fuel_capacity; // Maximum or available fuel
    double load_capacity; // Max weight limit the vehicle can carry
    double speed;         // Base speed scalar
};

// Struct summarizing global or local route assignment results
struct Result {
    double total_delivery_time;
    double fuel_used;
    int delayed_count; // Number of tasks that missed the deadline
    int completed_deliveries;
};

#endif // MODELS_H
