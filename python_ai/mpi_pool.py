from mpi4py import MPI
import time

class MPIPool:
    def __init__(self, pathfinder_ref):
        self.comm = MPI.COMM_WORLD
        self.rank = self.comm.Get_rank()
        self.size = self.comm.Get_size()
        self.pathfinder = pathfinder_ref

    def is_master(self):
        return self.rank == 0
        
    def get_num_workers(self):
        return max(1, self.size - 1)

    def worker_loop(self):
        """Infinite loop for worker nodes to wait for tasks."""
        if self.is_master():
            return
            
        print(f"Worker {self.rank} started waiting for tasks.")
        while True:
            # Wait for instruction from master
            req_type = self.comm.bcast(None, root=0)
            
            if req_type == "SHUTDOWN":
                print(f"Worker {self.rank} shutting down.")
                break
                
            elif req_type == "SYNC_GRAPH":
                # Receive new traffic factors and apply them
                edge_updates = self.comm.bcast(None, root=0)
                self.pathfinder.apply_edge_updates(edge_updates)
                
            elif req_type == "COMPUTE_BATCH":
                # Master scatters chunks of pathfinding tasks
                local_tasks = self.comm.scatter(None, root=0)
                
                local_results = []
                for src, dst, order_id, v_id in local_tasks:
                    cost, _ = self.pathfinder.compute_shortest_path(src, dst, record_ui=False)
                    local_results.append({
                        "order_id": order_id,
                        "v_id": v_id,
                        "cost": cost
                    })
                    
                # Gather results back to master
                self.comm.gather(local_results, root=0)

    def stop_workers(self):
        """Master node tells workers to shut down."""
        if self.is_master() and self.size > 1:
            self.comm.bcast("SHUTDOWN", root=0)

    def sync_graph(self):
        """Master broadcasts current edge traffic factors to workers."""
        if not self.is_master() or self.size <= 1:
            return
            
        edge_data = {}
        for u, v, data in self.pathfinder.graph.edges(data=True):
            edge_data[(u, v)] = data.get('traffic_factor', 1.0)
            
        self.comm.bcast("SYNC_GRAPH", root=0)
        self.comm.bcast(edge_data, root=0)

    def compute_batch(self, tasks):
        """
        Master method: Dispatch a large batch of (src, dst) queries to workers.
        tasks is a list of tuples: (src, dst, order_id, v_id)
        Returns a flattened list of all results.
        """
        if self.size <= 1:
            # Fallback to sequential if only 1 node
            results = []
            for src, dst, order_id, v_id in tasks:
                 cost, _ = self.pathfinder.compute_shortest_path(src, dst, record_ui=False)
                 results.append({"order_id": order_id, "v_id": v_id, "cost": cost})
            return results
            
        # 1. Distribute tasks among workers
        num_workers = self.get_num_workers()
        chunks = [[] for _ in range(self.size)] # rank 0 gets []
        
        for i, task in enumerate(tasks):
            worker_id = (i % num_workers) + 1
            chunks[worker_id].append(task)
            
        # 2. Tell workers to prepare for batch computing
        self.comm.bcast("COMPUTE_BATCH", root=0)
        
        # 3. Scatter the chunks
        self.comm.scatter(chunks, root=0)
        
        # 4. Gather the results
        # Master sends its own empty chunk and gets back list of lists
        gathered = self.comm.gather([], root=0)
        
        # 5. Flatten results from all workers (ignoring rank 0's empty list)
        flattened = []
        for worker_res in gathered:
            flattened.extend(worker_res)
            
        return flattened
