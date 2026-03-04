#ifndef MASTER_H
#define MASTER_H

#include "../models.h"
#include <vector>

class Master {
public:
    Master(int total_workers, int num_deliveries);

    // Initialize the environment (Deliveries, Vehicles, Graph)
    void init();

    // Broadcast setup to workers
    void broadcast_data();

    // Scatter tasks to corresponding worker node
    void distribute_tasks();

    // Gather and collect task results from workers
    void collect_results();

    // Final calculations and log reductions
    void finalize_metrics();

private:
    int num_workers;
    int total_deliveries;
    std::vector<Delivery> all_deliveries;
    std::vector<Vehicle> all_vehicles;
    std::vector<Result> worker_results;
    
    // Generates mock data for simulating requests
    void generate_mock_data();
};

#endif // MASTER_H
