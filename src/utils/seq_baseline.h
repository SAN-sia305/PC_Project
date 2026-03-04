#ifndef SEQ_BASELINE_H
#define SEQ_BASELINE_H

#include "../models.h"
#include <vector>

class SequentialBaseline {
public:
    SequentialBaseline(int total_deliveries);
    void run_sequential();
    const Result& get_metrics() const;

private:
    int total_deliveries;
    std::vector<Delivery> all_deliveries;
    Result seq_result;
    
    void generate_mock_data();
    double get_route_cost(int src, int dst);
};

#endif // SEQ_BASELINE_H
