#ifndef WORKER_H
#define WORKER_H

#include "../models.h"
#include <vector>

class Worker {
public:
    Worker(int id, int nodes);

    // Initial sync
    void receive_broadcast();

    // Receive personal cluster of tasks
    void receive_tasks();

    // Processes assigned tasks by consulting Python API for routing
    void process_tasks();

    // Dispatches results back to master
    void send_results();

    // Finalizes metric reports to master
    void finalize_metrics();

private:
    int worker_id;
    int num_nodes;
    std::vector<Delivery> assigned_tasks;
    Result local_result;
    
    // Perform a localized mock HTTP request via curl
    double get_route_cost(int src, int dst);
};

#endif // WORKER_H
