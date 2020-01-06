import math

from kivy.vector import Vector


class Rectangle:
    """Rectangle(center, size, bl_offset)

    Rectangle with it's center positioned at ``center``,
    of the size ``size`` and with bottom left (in the axis aligned position) offset by
    ``bl_offset`` from center, rotated by ``rotation`` degrees.
    Center also serves as the center of rotation.

    Args:
        center (Vector): Center of the rectangle, serves as the center of rotation and defines the position of the rectangle.
        size (Vector): Size of the rectangle in the form of (x,y) in the axis aligned position.
        bl_offset (Vector): Offset of the bottom left corner (minimal x,y in the axis aligned position) from the center.
        rotation (float): Angle of rotation of the rectangle from the base position.
    """
    def __init__(self, center, size, bl_offset, rotation):
        self.center = center
        self.size = size
        self.bl_offset = bl_offset
        self.rotation = rotation

    def get_bl(self):
        return self.get_local_bl() + self.center

    def get_br(self):
        return self.get_local_br() + self.center

    def get_tl(self):
        return self.get_local_tl() + self.center

    def get_tr(self):
        return self.get_local_tr() + self.center

    def get_local_bl(self):
        return self.get_aligned_bl().rotate(self.rotation)

    def get_local_br(self):
        return self.get_aligned_br().rotate(self.rotation)

    def get_local_tl(self):
        return self.get_aligned_tl().rotate(self.rotation)

    def get_local_tr(self):
        return self.get_aligned_tr().rotate(self.rotation)

    def get_aligned_bl(self):
        return self.bl_offset

    def get_aligned_br(self):
        return self.bl_offset + Vector(self.size.x, 0)

    def get_aligned_tl(self):
        return self.bl_offset + Vector(0, self.size.y)

    def get_aligned_tr(self):
        return self.bl_offset + self.size

    def get_vertexes(self):
        yield self.get_bl()
        yield self.get_br()
        yield self.get_tr()
        yield self.get_tl()

    def get_sides(self):
        yield self.get_bl(), self.get_br()
        yield self.get_br(), self.get_tr()
        yield self.get_tr(), self.get_tl()
        yield self.get_tl(), self.get_bl()

    def get_bbox(self):
        x = [vert.x for vert in self.get_vertexes()]
        y = [vert.y for vert in self.get_vertexes()]
        return min(x), min(y), max(x), max(y)

    def collide_point(self, point):
        p = point - self.center
        p.rotate(-self.rotation)
        return Vector.in_bbox(p, self.get_aligned_bl(), self.get_local_tr())

    def collide_line_segment(self, v1, v2):
        for side in self.get_sides():
            if Vector.segment_intersection(side[0], side[1], v1, v2) is not None:
                return True
        return self.collide_point(v1) and self.collide_point(v2)

    def collide_rectangle(self, rect):
        # check if any sides intersect

        for s_side in self.get_sides():
            for r_side in rect.get_sides():
                if Vector.segment_intersection(s_side[0], s_side[1], r_side[0], r_side[1]) is not None:
                    return True

        # check if all rect vertexes are inside self
        for v_r in rect.get_vertexes():
            if not self.collide_point(v_r):
                return False
        # rect is inside the rectangle
        return True


class Circle:
    def __init__(self, pos, radius):
        self.pos = Vector(*pos)
        self.r = radius

    def get_bbox(self):
        return self.pos.x - self.r, self.pos.y - self.r, self.pos.x + self.r, self.pos.y + self.r

    def get_y_at(self, x):
        # solution of y^2 - 2 * self.pos.y * y + self.pos.y^2 + (x - self.pos.x)^2 - self.r^2 = 0
        # quadratic equation
        a = 1
        b = -2 * self.pos.y
        c = self.pos.y ** 2 + (x - self.pos.x) ** 2 - self.r ** 2

        has_sol, s1, s2 = self.solve_quadratic(a, b, c)

        if not has_sol:
            return False, 0, 0

        return True, s1, s2

    def collide_point(self, point):
        return self.pos.distance(point) <= self.r

    def collide_line(self, v1, v2):
        # based on https://stackoverflow.com/questions/40970478/python-3-5-2-distance-from-a-point-to-a-line
        x_diff = v2.x - v1.x
        y_diff = v2.y - v1.y
        num = abs(y_diff * self.pos.x - x_diff * self.pos.y + v2.x * v1.y - v2.y * v1.x)
        den = v2.distance(v1)
        return (num / den) <= self.r

    def collide_line_segment(self, v1, v2):
        if self.collide_point(v1) or self.collide_point(v2):
            return True

        # based on https://codereview.stackexchange.com/questions/86421/line-segment-to-circle-collision-algorithm
        # rewrite the segment as v1 + t*dir
        dir = v2 - v1
        # at^2 + bt + c
        a = dir.dot(dir)
        b = 2 * dir.dot(v1 - self.pos)
        c = v1.dot(v1) + self.pos.dot(self.pos) - 2 * v1.dot(self.pos) - self.r ** 2
        has_sol, t1, t2 = self.solve_quadratic(a ,b ,c)

        if not has_sol:
            return False

        return 0 <= t1 <= 1 or 0 <= t2 <= 1

    def collide_rect(self, rectangle):
        # any rectangle vertex inside the circle (either whole rectangle inside or side collision)
        for vertex in rectangle.get_vertexes():
            if self.collide_point(vertex):
                return True

        # all rect vertexes outside, try side collision
        for side in rectangle.get_sides():
            if self.collide_line_segment(side[0], side[1]):
                return True

    @staticmethod
    def solve_quadratic(a, b, c):
        disc = b ** 2 - 4 * a * c
        if disc < 0:
            return False, 0, 0

        sqrt_disc = math.sqrt(disc)
        t1 = (-b + sqrt_disc) / (2 * a)
        t2 = (-b - sqrt_disc) / (2 * a)

        return True, t1, t2


def circle_segment_test(pos, radius, v1, v2, should_collide):
    c = Circle(pos, radius)
    result = c.collide_line_segment(v1, v2)
    assert result == should_collide


def circle_line_test(pos, radius, v1, v2, should_collide):
    c = Circle(pos, radius)
    result = c.collide_line(v1, v2)
    assert result == should_collide


def circle_point_test(pos, radius, p, should_collide):
    c = Circle(pos, radius)
    result = c.collide_point(p)
    assert result == should_collide

def circle_rect_test(c_pos, c_radius, r_center, r_bl_off, r_size, should_collide):
    c = Circle(c_pos, c_radius)
    rect = Rectangle(r_center, r_size, r_bl_off)
    result = c.collide_rect(rect)
    assert result == should_collide

def circle_tests():
    # point in the center of the circle
    circle_point_test(Vector(0, 0), 5, Vector(0,0), True)
    # point outside the circle
    circle_point_test(Vector(10, 10), 5, Vector(0, 0), False)
    # point on the circumference of the circle
    circle_point_test(Vector(10, 10), 10, Vector(0, 0), False)
    # float test
    circle_point_test(Vector(1.25, 0.25), 0.25, Vector(1.125, 0.125), True)

    circle_line_test(Vector(0, 0), 10, Vector(20,0), Vector(15,0), True)
    circle_line_test(Vector(0, 0), 10, Vector(5,0), Vector(-5,0), True)
    circle_line_test(Vector(5, 5), 10, Vector(20,20), Vector(-20, -20), True)
    circle_line_test(Vector(5, 5), 10, Vector(20,20), Vector(20, -20), False)

    # circle contains line segment
    circle_segment_test(Vector(0,0), 10, Vector(5,0), Vector(-5, 0), True)
    # line segment intersects the circumference
    circle_segment_test(Vector(0,0), 10, Vector(10,5), Vector(0, 5), True)

    circle_segment_test(Vector(5,5), 10, Vector(-10,0), Vector(-20, 5), False)


tests = {
    "circle tests": circle_tests
}

if __name__ == '__main__':
    circle_tests()
    #for name, test in tests:
    #    test.run()