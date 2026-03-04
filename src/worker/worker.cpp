#include "worker.h"
#include <iostream>
#include <mpi.h>
#include <cstdlib>
#include <sstream>
#include <string>
#include <fstream>
#include <random>

Worker::Worker(int id, int nodes) : worker_id(id), num_nodes(nodes) {
    local_result = {0.0, 0.0, 0, 0};
}

// C++ native HTTP call wrap via system curl
double Worker::get_route_cost(int src, int dst) {
    std::string filename = "route_" + std::to_string(worker_id) + ".txt";
    std::string command = "curl -s http://127.0.0.1:8000/get-route?src=" + std::to_string(src) + "&dst=" + std::to_string(dst) + " > " + filename;
    
    int result = std::system(command.c_str());
    if(result != 0) {
        std::cerr << "[Worker " << worker_id << "] Error calling Python AI API." << std::endl;
        return dst - src + 10.0; // Fallback distance mock
    }

    std::ifstream infile(filename);
    double cost = 0.0;
    std::string token;
    // Expected output format from Python API: {"cost": 45.2, ...} -> For prototype simply grabbing raw output if numeric, but here we mock parsing.
    if(infile >> token) {
        // Fast mock: Assuming raw number is returned for prototyping phase from python backend
        try {
            cost = std::stod(token);
        } catch(...) {
            cost = 15.0; // Default if JSON returned
        }
    }
    infile.close();
    std::remove(filename.c_str()); // cleanup
    return cost; 
}

void Worker::receive_broadcast() {
    int total;
    MPI_Bcast(&total, 1, MPI_INT, 0, MPI_COMM_WORLD);
}

void Worker::receive_tasks() {
    int total_tasks; // ideally from bcast but assume 100 
    // Wait for real logic in a dynamic setting, using local sizes
    
    // In our prototype, Master gathers num workers. We need exact match.
    // For simplicity of prototype scatter, assume sendsize = 100 / num_workers
    int num_workers;
    MPI_Comm_size(MPI_COMM_WORLD, &num_workers);
    
    // Let's assume total_deliveries was 100
    int total_deliveries = 100;
    int sendsize = total_deliveries / num_workers;

    assigned_tasks.resize(sendsize);

    MPI_Scatter(nullptr, 0, MPI_BYTE,
                assigned_tasks.data(), sendsize * sizeof(Delivery), MPI_BYTE,
                0, MPI_COMM_WORLD);

    std::cout << "[Worker " << worker_id << "] Received " << sendsize << " tasks." << std::endl;
}

void Worker::process_tasks() {
    std::cout << "[Worker " << worker_id << "] Processing tasks and consulting AI routing..." << std::endl;
    // Process each delivery
    for(const auto& task : assigned_tasks) {
        double current_route_cost = get_route_cost(task.src_node, task.dst_node);
        
        // Mock business logic using cost
        local_result.total_delivery_time += current_route_cost;
        local_result.fuel_used += current_route_cost * 0.5; // dummy conversion rate
        local_result.completed_deliveries++;
        
        if (current_route_cost > task.deadline) {
            local_result.delayed_count++;
        }
    }
}

void Worker::send_results() {
    std::cout << "[Worker " << worker_id << "] Submitting results... (Gather)" << std::endl;
    MPI_Gather(&local_result, sizeof(Result), MPI_BYTE,
               nullptr, 0, MPI_BYTE,
               0, MPI_COMM_WORLD);
}

void Worker::finalize_metrics() {
    // Workers only contribute to local metrics -> Global
    MPI_Reduce(&local_result.total_delivery_time, nullptr, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_result.fuel_used, nullptr, 1, MPI_DOUBLE, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_result.delayed_count, nullptr, 1, MPI_INT, MPI_SUM, 0, MPI_COMM_WORLD);
    MPI_Reduce(&local_result.completed_deliveries, nullptr, 1, MPI_INT, MPI_SUM, 0, MPI_COMM_WORLD);
}
