import numpy as np
from skimage.graph import MCP_Geometric

cost_array = np.array([
    [1, 2, 3, 4, 5],
    [2, 3, 4, 5, 6],
    [3, 4, 5, 6, 7],
    [4, 5, 6, 7, 8],
    [5, 6, 7, 8, 9]
])

source_coords = np.array([[0, 0]])
dest_coords = np.array([[3, 3], [4, 4]])
dest_coords_n = dest_coords.shape[0]

# Initialize MCP_Geometric instance
mcp = MCP_Geometric(cost_array)

# Create cumulative costs array and traceback array
costs_array, traceback_array = mcp.find_costs(starts=source_coords, ends=dest_coords, find_all_ends=True)

# Identify paths
for i in range(dest_coords_n):
    print("iteration:", i)
    path = mcp.traceback(dest_coords[i,:])  # [(0, 0), (1, 1), (2, 2), (3, 3)]
    print(path)
    path_coords = np.array(path)  # [[0 0] [1 1] [2 2] [3 3]]
    print(path_coords)
