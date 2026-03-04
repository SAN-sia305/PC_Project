#include <mpi.h>
#include <iostream>
#include "master/master.h"
#include "worker/worker.h"

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);

    int world_rank;
    MPI_Comm_rank(MPI_COMM_WORLD, &world_rank);
    
    int world_size;
    MPI_Comm_size(MPI_COMM_WORLD, &world_size);

    if (world_size < 2) {
        if (world_rank == 0) {
            std::cerr << "This simulation requires at least 2 processes (1 Master, 1+ Workers)." << std::endl;
        }
        MPI_Finalize();
        return 1;
    }

    // Number of deliveries
    int total_deliveries = 100;
    // Number of nodes in Graph
    int num_nodes = 50;
    
    // Performance measurement variables
    double start_time, end_time;

    if (world_rank == 0) {
        // Master process
        Master master(world_size, total_deliveries);
        master.init();
        
        // Ensure all processes reach this point
        MPI_Barrier(MPI_COMM_WORLD);
        start_time = MPI_Wtime();

        master.broadcast_data();
        master.distribute_tasks();
        master.collect_results();
        master.finalize_metrics();

        MPI_Barrier(MPI_COMM_WORLD);
        end_time = MPI_Wtime();

        std::cout << "Parallel Execution Time: " << end_time - start_time << " seconds" << std::endl;

    } else {
        // Worker processes
        Worker worker(world_rank, num_nodes);
        
        MPI_Barrier(MPI_COMM_WORLD);

        worker.receive_broadcast();
        worker.receive_tasks();
        worker.process_tasks();
        worker.send_results();
        worker.finalize_metrics();

        MPI_Barrier(MPI_COMM_WORLD);
    }

    MPI_Finalize();
    return 0;
}
