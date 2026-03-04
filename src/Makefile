CXX = mpicxx
CXXFLAGS = -std=c++11 -Wall -I./utils -I./master -I./worker

# Source files
SRCS = main.cpp master/master.cpp worker/worker.cpp utils/graph.cpp
OBJS = $(SRCS:.cpp=.o)

# Executable name
TARGET = difm_dos

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) -o $(TARGET) $(OBJS)

%.o: %.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(TARGET) route_*.txt
