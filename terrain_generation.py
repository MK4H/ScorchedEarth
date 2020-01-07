import random
import math
from kivy.vector import Vector


FEATURE_SIZE = 200
NOISE_SIZE = 4

def generate_terrain(map_size, tank_x_positions, tank_size):
    solid_parts = []
    max_height = map_size[1] - (tank_size[1] * 2)
    prev_height = min(random.randrange(map_size[1]), max_height)
    s_t_p = sorted(tank_x_positions, reverse=True)
    next_tank_pos = s_t_p.pop()
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
    dist_x = next_feature_pos[0] - x
    dist_y = next_feature_pos[1] - prev_height
    if dist_x != 0:
        height_diff = dist_y / dist_x
        if next_tank_pos < next_feature_pos[0]:
            height_diff *= 2
    else:
        height_diff = dist_y
    next_height = math.ceil(prev_height + height_diff)
    return random.randrange(max(next_height - NOISE_SIZE, 1), min(next_height + NOISE_SIZE, max_height))


def create_valley(map_height, prev_height, max_height, size):
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
    form = random.choice(['steep', 'concave'])

    if form == 'steep':
        if prev_height < map_height/2:
            return [(size/4, min(prev_height * 2, max_height)), (size/2, min(map_height * 4/5, max_height)), (size, min(map_height * 9/10, max_height))]
        else:
            return [(size/4, min(map_height * 4/5, max_height)), (size/2, min(map_height * 9/10, max_height)), (size, min(map_height * 9/10, max_height))]
    elif form == 'concave':
        return [(size/2, map_height/2), (size, map_height * 3/4)]


def create_plateau(map_height, prev_height, max_height, size):
    height = random.randrange(map_height/20, max_height)
    return [((size/4), height), (size, height)]


def get_topology(init_height, map_size, max_height):
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
            new_points[idp] = (new_points[idp][0] + i * FEATURE_SIZE, new_points[idp][1])
        feature_points.extend(new_points)
        previous.pop(0)
        previous.append(idx)

    return feature_points
