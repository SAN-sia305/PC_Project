#include "seq_baseline.h"
#include <iostream>
#include <random>
#include <string>
#include <cstdlib>
#include <fstream>
#include <mpi.h>

SequentialBaseline::SequentialBaseline(int num_deliveries) : total_deliveries(num_deliveries) {
    seq_result = {0.0, 0.0, 0, 0};
    generate_mock_data();
}

void SequentialBaseline::generate_mock_data() {
    std::mt19937 gen(42);
    std::uniform_int_distribution<> node_dist(0, 49);
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
}

double SequentialBaseline::get_route_cost(int src, int dst) {
    std::string filename = "route_seq.txt";
    std::string command = "curl -s http://127.0.0.1:8000/get-route?src=" + std::to_string(src) + "&dst=" + std::to_string(dst) + " > " + filename;
    
    int result = std::system(command.c_str());
    if(result != 0) {
        std::cerr << "[Sequential] Error calling Python AI API." << std::endl;
        return dst - src + 10.0;
    }

    std::ifstream infile(filename);
    double cost = 0.0;
    std::string token;
    if(infile >> token) {
        try {
            cost = std::stod(token);
        } catch(...) {
            cost = 15.0; // Default if JSON string match fails
        }
    }
    infile.close();
    std::remove(filename.c_str());
    return cost; 
}


void SequentialBaseline::run_sequential() {
    std::cout << "[Sequential] Starting sequential run over " << total_deliveries << " deliveries..." << std::endl;
    for(const auto& task : all_deliveries) {
        double cost = get_route_cost(task.src_node, task.dst_node);
        
        seq_result.total_delivery_time += cost;
        seq_result.fuel_used += cost * 0.5;
        seq_result.completed_deliveries++;
        
        if (cost > task.deadline) {
            seq_result.delayed_count++;
        }
    }
    std::cout << "[Sequential] Run complete." << std::endl;
}

const Result& SequentialBaseline::get_metrics() const {
    return seq_result;
}
