from datetime import datetime as dt
import networkx as nx
import geopandas as gpd
import os
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points

# Function to create a network graph from cost raster
def create_graph_from_cost(cost_array):
    print(f"[{dt.now().strftime('%H:%M:%S')}] Converting cost array to cost graph...")
    graph = nx.Graph()
    rows, cols = cost_array.shape

    for row in range(rows):
        for col in range(cols):
            cost = cost_array[row, col]
            node_id = f"{row}_{col}"
            graph.add_node(node_id, cost=cost, geometry=Point(col, row))

            # Add edges to neighbors
            for i, j in [(row - 1, col), (row, col - 1), (row + 1, col), (row, col + 1)]:
                if 0 <= i < rows and 0 <= j < cols:
                    neighbor_id = f"{i}_{j}"
                    neighbor_cost = cost_array[i, j]
                    graph.add_edge(node_id, neighbor_id, weight=neighbor_cost)

    return graph

# Function to calculate and save shortest paths
def calculate_and_save_shortest_paths(graph, presence_thinned, year_field, output_gpkg):
    # List to store features
    features = []

    for _, row_source in presence_thinned.iterrows():
        year_source = row_source[year_field]

        for _, row_dest in presence_thinned.iterrows():
            year_dest = row_dest[year_field]

            if year_source > year_dest:
                print(
                    f"[{dt.now().strftime('%H:%M:%S')}] Calculating with source = {year_source} and dest = {year_dest}...")

                # Snap source and destination points to the nearest nodes in the graph
                source_point = nearest_points(row_source['geometry'],
                                              gpd.GeoSeries(graph.nodes[node]['geometry'] for node in graph.nodes))
                dest_point = nearest_points(row_dest['geometry'],
                                            gpd.GeoSeries(graph.nodes[node]['geometry'] for node in graph.nodes))

                # Retrieve the node IDs based on the snapped points
                source_coords = source_point[0].x, source_point[0].y
                dest_coords = dest_point[0].x, dest_point[0].y

                source_coords = source_coords[1], source_coords[0]
                dest_coords = dest_coords[1], dest_coords[0]

                source_node_id = f"{source_coords[1]:.6f}_{source_coords[0]:.6f}"  # Round to 6 decimal places
                dest_node_id = f"{dest_coords[1]:.6f}_{dest_coords[0]:.6f}"

                # Calculate the shortest path
                path = nx.shortest_path(graph, source=source_node_id, target=dest_node_id, weight="weight")

                # Create line geometry
                line_coords = [graph.nodes[node]["geometry"].coords[0] for node in path]
                line_geometry = LineString(line_coords)

                # Create feature and set attributes
                feature = {
                    'geometry': line_geometry,
                    'properties': {
                        'year_source': year_source,
                        'year_destination': year_dest,
                        'accumulated_cost': nx.shortest_path_length(graph, source=source_node_id, target=dest_node_id,
                                                                    weight="weight")
                    }
                }

                # Append feature to the list
                features.append(feature)

    # Create a GeoDataFrame from the list of features
    result_gdf = gpd.GeoDataFrame.from_features(features)

    # Save the GeoDataFrame to a GeoPackage
    result_gdf.to_file(output_gpkg, driver='GPKG')

# Example usage:
def shortestpaths(workdir_path, presence_name, presence_thinned, cost, run, year_field):
    print(f"[{dt.now().strftime('%H:%M:%S')}] Converting cost raster to array...")
    cost_array = cost.read(1)
    output_gpkg = os.path.join(workdir_path, f"{presence_name}_{run}_paths.gpkg")
    
    graph = create_graph_from_cost(cost_array)
    calculate_and_save_shortest_paths(graph, presence_thinned, year_field, output_gpkg)
