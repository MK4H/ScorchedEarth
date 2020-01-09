import random
import math
from kivy.vector import Vector

"""Terrain generation.

Implements the terrain generation algorithms for randomized generation of the map terrain.
Generated terrain consists of preset number of topological features of different types. The types of the 
features and their parameters are chosen randomly, with some restrictions on repetition of types.

Attributes:
    FEATURE_SIZE (int): Size of the features, which determines the number of features that fit onto the map.
    NOISE_SIZE (int): Size of the random noise applied to each generated height. 
"""

FEATURE_SIZE = 200
NOISE_SIZE = 4


def generate_terrain(map_size, tank_x_positions, tank_size):
    solid_parts = []
    # limit the height so that tanks always fit above the terrain with some room to spare
    max_height = map_size[1] - (tank_size[1] * 2)
    # generate the initial hight
    prev_height = min(random.randrange(map_size[1]), max_height)

    # sorted tank position based on the x axis, so that we can pop the lowest once from the back of the list
    s_t_p = sorted(tank_x_positions, reverse=True)
    next_tank_pos = s_t_p.pop()

    # generates the topological features
    feature_points = get_topology(prev_height, map_size, max_height)
    feature_points.reverse()
    next_feature_pos = feature_points.pop()

    tank_positions = []
    for x in range(map_size[0]):
        if x < next_tank_pos:
            terrain_top = get_terrain_height(x, prev_height, max_height, next_tank_pos, tank_size, next_feature_pos)
        elif next_tank_pos == x:
            terrain_top = get_terrain_height(x, prev_height, max_height, next_tank_pos, tank_size, next_feature_pos)
            tank_positions.append(Vector(x, terrain_top))
        elif next_tank_pos < x < next_tank_pos + tank_size[0] - 1:
            # leaves terrain level for the tank
            terrain_top = prev_height
        else:
            terrain_top = prev_height
            if len(s_t_p) != 0:
                next_tank_pos = s_t_p.pop()
            else:
                next_tank_pos = map_size[0] + 1

        if math.floor(next_feature_pos[0]) == x:
            next_feature_pos = feature_points.pop()

        solid_parts.append([0, terrain_top])
        prev_height = terrain_top

    return solid_parts, tank_positions


def get_terrain_height(x, prev_height, max_height, next_tank_pos, tank_size, next_feature_pos):
    """Generates terrain height based on the previous height and the current topological feature.

    Generates the height so that we reach the position specified by the topological feature `next_feature_pos`.
    When the topological feature contains a tank, changes the generation to take into account the flat spot the
    tank will need, BUT DOES NOT GENERATE THE FLAT SPOT.

    Args:
        x (int): The x coordinate the height is for.
        prev_height (int): Height at the `x - 1` position.
        max_height (int): Upper limit on the value of height.
        next_tank_pos (int): x coordinate of the beggining of the tank position.
        tank_size (int): Size of tanks in the current level.
        next_feature_pos (float, float): (x,y) position we are trying to reach to generate the topological feature.

    Returns: The height of the terrain at `x` position.

    """
    dist_x = next_feature_pos[0] - x
    dist_y = next_feature_pos[1] - prev_height
    if dist_x != 0:
        height_diff = dist_y / dist_x
        # if the feature contains a tank, we need to get there faster, because there will be the flat spot for the tank
        if next_tank_pos < next_feature_pos[0]:
            height_diff *= 2
    else:
        height_diff = dist_y
    next_height = math.ceil(prev_height + height_diff)
    return random.randrange(max(next_height - NOISE_SIZE, 1), min(next_height + NOISE_SIZE, max_height))


def create_valley(map_height, prev_height, max_height, size):
    """Generates a part of a terrain with lower height.

    Generates on of a few types of valley topologies, generally creating a part of a terrain with lower height.

    Args:
        map_height (int): Total height of the map.
        prev_height (int): Height of the previous topology, i.e. the topology with lower x coordinate.
        max_height (int): Max generated height.
        size (int): Size of the topological feature on the x axis.

    Returns:
        list of (float, float): List of points the generated height should go through, basically waypoints for
            generating terrain.

    """
    form = random.choice(['deep', 'shallow', 'wavy'])

    if form == 'deep':
        if prev_height > map_height/2:
            return [(size/4, prev_height * 5/6), (size/2, prev_height/4), (size, map_height/20)]
        else:
            return [(size/4, prev_height/2), (size/2, map_height/10), (size, map_height/20)]
    elif form == 'shallow':
        return [(size/4, prev_height * 5/6), (size/2, prev_height/2), (size, prev_height/4)]
    elif form == 'wavy':
        return [(size/4, prev_height/2), (size / 2, prev_height), (size * 3/4, prev_height/2), (size, prev_height)]


def create_hill(map_height, prev_height, max_height, size):
    """Generates a part of a terrain with greater height.

        Generates on of a few types of hill topologies, generally creating a part of a terrain with greater height.

        Args:
            map_height (int): Total height of the map.
            prev_height (int): Height of the previous topology, i.e. the topology with lower x coordinate.
            max_height (int): Max generated height.
            size (int): Size of the topological feature on the x axis.

        Returns:
            list of (float, float): List of points the generated height should go through, basically waypoints for
                generating terrain.
    """
    form = random.choice(['steep', 'concave'])

    if form == 'steep':
        if prev_height < map_height/2:
            return [(size/4, min(prev_height * 2, max_height)), (size/2, min(map_height * 4/5, max_height)), (size, min(map_height * 9/10, max_height))]
        else:
            return [(size/4, min(map_height * 4/5, max_height)), (size/2, min(map_height * 9/10, max_height)), (size, min(map_height * 9/10, max_height))]
    elif form == 'concave':
        return [(size/2, map_height/2), (size, map_height * 3/4)]


def create_plateau(map_height, prev_height, max_height, size):
    """Generates a part of a terrain with constant height.

        Generates a plateau topology, creating part of the terrain with a constant height.

        Args:
            map_height (int): Total height of the map.
            prev_height (int): Height of the previous topology, i.e. the topology with lower x coordinate.
            max_height (int): Max generated height.
            size (int): Size of the topological feature on the x axis.

        Returns:
            list of (float, float): List of points the generated height should go through, basically waypoints for
                generating terrain.
    """
    height = random.randrange(map_height/20, max_height)
    return [((size/4), height), (size, height)]


def get_topology(init_height, map_size, max_height):
    """Generates list of waypoints the height generation should go through to create topologies.

    Creates random list of topological features and generates a list of points the terrain generation should
    pass the top of the terrain through to recreate these features in the map.

    Args:
        init_height (int): Starting height at `x == 0`.
        map_size (int, int): Size of the map in (x,y) coordinates.
        max_height (int): Upper limit on the generated height.

    Returns:
        list of (float, float): List of waypoints the height generation should go through to recreate generated
            topologies.
    """
    num_features = math.ceil(map_size[0] / FEATURE_SIZE)
    generators = [create_valley, create_hill, create_plateau]
    previous = [random.randrange(len(generators)), random.randrange(len(generators))]
    feature_points = []
    for i in range(num_features):
        while True:
            idx = random.randrange(len(generators))
            # do not repeat topology more than once
            if previous.count(idx) != 2:
                break
        new_points = generators[idx](map_size[1], init_height, max_height, FEATURE_SIZE)
        for idp in range(len(new_points)):
            # as the feature points are generated in local coordinates, shift them on the x axis to the correct part
            # of the terrain.
            new_points[idp] = (new_points[idp][0] + i * FEATURE_SIZE, new_points[idp][1])
        feature_points.extend(new_points)
        previous.pop(0)
        previous.append(idx)

    return feature_points
