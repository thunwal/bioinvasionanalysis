import skimage.graph as graph
import numpy

# Declare cost matrix
numpy.random.seed(seed=5)
costs = numpy.random.normal(1,1,(50,100))

# Determine minimum costs to various points
mcp=graph.MCP_Geometric(costs)
cumulative_costs, traceback = mcp.find_costs([[3,0],[20,20],[25,50],[40,95]])

#cumulative_costs2, traceback2 = mcp.find_costs([[3,0],[3,3]])
print(costs)
print(cumulative_costs)
print(traceback)

# Determine optimal paths to endpoints
# Here one would put the location of the cities and iterate over all
# From this one could create Networks and such
cities=numpy.array([[0,0],[9,9],[3,2]])  # ,[99,99]
ncities=cities.shape[0]
paths=numpy.empty(costs.shape)
paths.fill(-1)
for i in range(ncities):
    try:
        route=mcp.traceback(cities[i,:])
        coords=numpy.asarray(route)
        print(route)
        #print coords
        for j in range(len(route)):
            paths[route[j]]=i+1
    except:
        print('No route to city ',i+1)
print(paths)

