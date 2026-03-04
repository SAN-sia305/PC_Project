#include "master.h"
#include <iostream>
#include <mpi.h>
#include <random>

Master::Master(int total_workers, int num_deliveries)
    : num_workers(total_workers), total_deliveries(num_deliveries) {
    worker_results.resize(total_workers);
}

void Master::generate_mock_data() {
    std::mt19937 gen(42);
    std::uniform_int_distribution<> node_dist(0, 49); // Assume 50 nodes graph
    std::uniform_real_distribution<> weight_dist(10.0, 100.0);
    std::uniform_real_distribution<> deadline_dist(5.0, 50.0);

    for (int i = 0; i < total_deliveries; ++i) {
        Delivery d;
        d.id = i;
        d.src_node = node_dist(gen);
        d.dst_node = node_dist(gen);
        d.deadline = deadline_dist(gen);
        d.weight = weight_dist(gen);
        all_deliveries.push_back(d);
    }
    
    // Create 10 mock vehicles for the simulation
    for (int i = 0; i < 10; ++i) {
        Vehicle v;
        v.id = i;
        v.current_location = node_dist(gen);
        v.fuel_capacity = 1000.0;
        v.load_capacity = 500.0;
        v.speed = 1.0;
        all_vehicles.push_back(v);
    }
}

void Master::init() {
    std::cout << "[Master] Initializing simulation data..." << std::endl;
    generate_mock_data();
}

void Master::broadcast_data() {
    std::cout << "[Master] Broadcasting common data to workers..." << std::endl;
    // Simplification for prototype: Workers can regenerate or we broadcast size arrays
    // For Phase 1, we will mock the broadcast since it requires serializing objects
    // Bcast delivery counts
    int total = total_deliveries;
    MPI_Bcast(&total, 1, MPI_INT, 0, MPI_COMM_WORLD);
}

void Master::distribute_tasks() {
    std::cout << "[Master] Scattering tasks to workers..." << std::endl;
    
    int sendsize = total_deliveries / num_workers;
    
    // Distributing via Scatter byte streams
    // Delivery struct is pure data (POD), can be mapped directly to MPI_BYTE
    
    Delivery* recv_buffer = new Delivery[sendsize];
    
    MPI_Scatter(all_deliveries.data(), sendsize * sizeof(Delivery), MPI_BYTE,
                recv_buffer, sendsize * sizeof(Delivery), MPI_BYTE,
                0, MPI_COMM_WORLD);

    delete[] recv_buffer; // Master won't use it, just participating in Scatter
}

void Master::collect_results() {
    std::cout << "[Master] Gathering worker results..." << std::endl;
    
    Result local_res = {0, 0, 0, 0}; // Master's dummy participation
    
    MPI_Gather(&local_res, sizeof(Result), MPI_BYTE,
               worker_results.data(), sizeof(Result), MPI_BYTE,
               0, MPI_COMM_WORLD);
}

void Master::finalize_metrics() {
    std::cout << "[Master] Reducing final metrics..." << std::endl;
    
    Result global_res = {0.0, 0.0, 0, 0};
    Result local_res = {0.0, 0.0, 0, 0}; // Dummy

    // Reduce over double variables
    MPI_Reduce(&local_res.total_delivery_time, &global_res.total_delivery_time, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_res.fuel_used, &global_res.fuel_used, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_res.delayed_count, &global_res.delayed_count, 1, MPI_INT, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_res.completed_deliveries, &global_res.completed_deliveries, 1, MPI_INT, MPI_SUM, 0, MPI_COMM_WORLD);

    std::cout << "========== SIMULATION COMPLETE ==========" << std::endl;
    std::cout << "Total Deliveries Processed: " << global_res.completed_deliveries << std::endl;
    std::cout << "Total Delayed: " << global_res.delayed_count << std::endl;
    std::cout << "Total Time: " << global_res.total_delivery_time << std::endl;
    std::cout << "Total Fuel Used: " << global_res.fuel_used << std::endl;
    std::cout << "=========================================" << std::endl;
}
