from vector2d import Vector2D
from vector2d import Point2D
from graphics import egi, KEY
from math import sin, cos, radians
from random import random, randrange, uniform, randint
from path import Path

class CircularWall(object):
	def __init__(self, radius, position):
		self.radius = radius
		self.pos = position
	def render(self):
		egi.white_pen()
		egi.circle(self.pos, self.radius)