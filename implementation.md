# DIFM-DOS Implementation Plan

## 1. Big Picture

The Distributed Intelligent Fleet Management & Delivery Optimization
System (DIFM-DOS) is a distributed route-optimization simulator built
using MPI. The goal is to demonstrate parallel computing performance on
a logistics-style workload.

Success criteria:

-   Correct MPI orchestration\
-   Measurable speedup vs sequential\
-   Sensible optimization logic\
-   Clean metrics output

------------------------------------------------------------------------

## 2. Recommended Tech Stack

### Core Compute Layer (Mandatory)

-   Language: C++\
-   Parallel Framework: MPI (OpenMPI or MPICH)\
-   Compiler: g++\
-   Build Tool (optional): CMake

### Algorithm Layer

**Path Finding**

-   Dijkstra (baseline, required)\
-   Optional: A\*

**Task Assignment**

-   Minimum: Greedy nearest-vehicle assignment\
-   Optional: Hungarian algorithm

**Traffic Simulation**

-   Edge weight multiplier\
-   Random congestion factor\
-   Time-dependent delay

### Data Generation

**Recommended (Phase 1):** Synthetic generator in master process

**Advanced:** Read from CSV/JSON

### Metrics & Analysis

-   MPI_Wtime() for timing\
-   CSV output\
-   Optional: Python for plotting

------------------------------------------------------------------------

## 3. System Architecture

### Data Structures

``` cpp
struct Delivery {
    int id;
    int src;
    int dst;
    double deadline;
    double weight;
};

struct Vehicle {
    int id;
    int location;
    double fuel_capacity;
    double load_capacity;
    double speed;
};

struct Result {
    double total_time;
    double fuel_used;
    int delayed;
};
```

------------------------------------------------------------------------

### Graph Engine

Responsibilities:

-   Generate weighted graph\
-   Apply traffic updates\
-   Compute shortest paths using Dijkstra

Key functions:

-   generate_graph()\
-   apply_traffic()\
-   dijkstra()

------------------------------------------------------------------------

## 4. Master Process (Rank 0)

Execution flow:

1.  MPI_Init\
2.  Generate data\
3.  Broadcast traffic\
4.  Scatter deliveries\
5.  Gather worker results\
6.  Reduce global metrics\
7.  Print performance\
8.  MPI_Finalize

**Important:** Master should do minimal computation.

------------------------------------------------------------------------

## 5. Worker Processes

Each worker:

1.  Receive delivery subset\
2.  Run route optimization\
3.  Simulate traffic delay\
4.  Assign vehicles\
5.  Compute metrics\
6.  Send results to master

This is the parallel work kernel.

------------------------------------------------------------------------

## 6. Parallelization Strategy

### Partitioning

Use:

``` cpp
MPI_Scatter(deliveries)
```

Each worker receives:

    total_deliveries / num_workers

### Communication Pattern

-   MPI_Bcast → traffic data\
-   MPI_Scatter → delivery tasks\
-   MPI_Gather → worker results\
-   MPI_Reduce → global metrics

Pattern: SPMD data parallelism.

------------------------------------------------------------------------

## 7. Performance Measurement

### Sequential Version

Implement:

``` cpp
run_sequential()
```

### Parallel Timing

``` cpp
MPI_Barrier(MPI_COMM_WORLD);
start = MPI_Wtime();

// parallel work

MPI_Barrier(MPI_COMM_WORLD);
end = MPI_Wtime();
```

### Metrics

-   Speedup = T_seq / T_par\
-   Efficiency = Speedup / P\
-   Load balance efficiency

------------------------------------------------------------------------

## 8. Implementation Roadmap

### Phase 1 --- MPI Skeleton

-   Rank hello world\
-   Test Bcast\
-   Test Scatter/Gather\
-   Test Reduce

### Phase 2 --- Graph + Dijkstra

-   Graph generator\
-   Implement Dijkstra\
-   Validate shortest paths

### Phase 3 --- Sequential Simulator

-   Deliveries\
-   Vehicles\
-   Traffic\
-   Metrics

### Phase 4 --- Parallel Version

-   Scatter deliveries\
-   Workers compute\
-   Gather results\
-   Reduce metrics

### Phase 5 --- Performance Study

-   Vary number of processes\
-   Vary problem size\
-   Compute speedup\
-   Plot graphs (optional)

------------------------------------------------------------------------

## 9. Optional Enhancements

-   Dynamic load balancing\
-   Vehicle breakdown simulation\
-   A\* routing\
-   Real map data\
-   Hybrid MPI + OpenMP

------------------------------------------------------------------------

## 10. Common Failure Points

Watch for:

-   Scatter size mismatch\
-   Non-divisible workload\
-   Incorrect timing\
-   Master doing too much work\
-   Idle workers\
-   Graph too small (no speedup)

------------------------------------------------------------------------

## 11. Expected Outcomes

A successful DIFM-DOS implementation demonstrates:

-   Distributed task parallelism\
-   MPI collective communication\
-   Measurable speedup\
-   Load balancing behavior\
-   Scalability characteristics
