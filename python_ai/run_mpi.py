import time
import random
from mpi4py import MPI
from pathfinding import PathFinder

def main():
    # Initialize MPI
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    if size < 2:
        if rank == 0:
            print("This simulation requires at least 2 processes (1 Master, 1+ Workers).")
        return

    # Configuration
    TOTAL_DELIVERIES = 100
    NUM_NODES = 50

    # Only Master maintains the full sequence for sequential comparison
    if rank == 0:
        # Initialize PathFinder for sequential test
        pf = PathFinder(num_nodes=NUM_NODES)
        
        # 1. Sequential Execution (baseline)
        start_seq = time.time()
        for _ in range(TOTAL_DELIVERIES):
            src = random.randint(0, NUM_NODES - 1)
            dst = random.randint(0, NUM_NODES - 1)
            while dst == src:
                dst = random.randint(0, NUM_NODES - 1)
            
            # Master evaluates sequentially without UI recording
            pf.compute_shortest_path(src, dst, record_ui=False)
            
        end_seq = time.time()
        sequential_time = end_seq - start_seq

        # 2. Parallel Execution Setup
        # Generate tasks (source, destination pairs)
        tasks = []
        for _ in range(TOTAL_DELIVERIES):
            src = random.randint(0, NUM_NODES - 1)
            dst = random.randint(0, NUM_NODES - 1)
            while dst == src:
                dst = random.randint(0, NUM_NODES - 1)
            tasks.append((src, dst))

        # Split tasks among workers (rank 1 to size-1)
        num_workers = size - 1
        chunks = [[] for _ in range(size)] # rank 0 gets empty chunk
        for i, task in enumerate(tasks):
            worker_id = (i % num_workers) + 1
            chunks[worker_id].append(task)
            
        # Start Parallel Timer
        start_par = MPI.Wtime()

    else:
        chunks = None

    # --- PARALLEL DISTRIBUTION START ---
    
    # Broadcast PathFinder Graph Seed so all nodes share same map
    seed = comm.bcast(42 if rank == 0 else None, root=0)
    
    # Scatter tasks to all ranks
    local_tasks = comm.scatter(chunks, root=0)
    
    # Workers process their chunks locally
    local_results = []
    local_delayed = 0
    local_fuel = 0.0
    
    if rank != 0:
        worker_pf = PathFinder(num_nodes=NUM_NODES, seed=seed)
        
        for src, dst in local_tasks:
            # Execute logic (this runs the RuleEngine locally too!)
            cost, route = worker_pf.compute_shortest_path(src, dst, record_ui=False)
            
            # Mock delay calculation based on cost
            if cost > 50.0:
                local_delayed += 1
            
            # Fuel is roughly proportional to drive cost
            local_fuel += (cost * 0.15)
            
            local_results.append((src, dst, cost, len(route)))

    # Gather results back to Master
    all_results = comm.gather((local_delayed, local_fuel, len(local_results)), root=0)

    # --- PARALLEL DISTRIBUTION END ---

    if rank == 0:
        end_par = MPI.Wtime()
        parallel_time = end_par - start_par
        
        # Aggregate stats
        total_delayed = sum(res[0] for res in all_results if res is not None)
        total_fuel = sum(res[1] for res in all_results if res is not None)
        total_processed = sum(res[2] for res in all_results if res is not None)

        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        efficiency = speedup / num_workers if num_workers > 0 else 0

        # Print EXACT output format expected by the backend parser
        print(f"Parallel Execution Time: {parallel_time:.4f} seconds")
        print(f"Sequential Execution Time: {sequential_time:.4f} seconds")
        print(f"Total Deliveries Processed: {total_processed}")
        print(f"Total Delayed: {total_delayed}")
        print(f"Total Fuel Used: {total_fuel:.2f}")

if __name__ == "__main__":
    main()
