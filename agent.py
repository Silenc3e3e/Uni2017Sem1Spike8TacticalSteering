'''An agent with Seek, Flee, Arrive, Pursuit behaviours

Created for COS30002 AI for Games by Clinton Woodward cwoodward@swin.edu.au

'''

from vector2d import Vector2D
from vector2d import Point2D
from graphics import egi, KEY
from math import sin, cos, radians
from random import random, randrange, uniform, randint
from path import Path

AGENT_MODES = {
    KEY._1: 'seek',
    KEY._2: 'arrive_slow',
    KEY._3: 'arrive_normal',
    KEY._4: 'arrive_fast',
    KEY._5: 'flee',
    KEY._6: 'pursuit',
    KEY._7: 'follow_path',
    KEY._8: 'wander'
}
class DummyAgent(object):
    def __init__(self, x, y):
        self.pos = Vector2D (x, y)
        self.vel = Vector2D(0, 0)

class Agent(object):
    # NOTE: Class Object (not *instance*) variables!
    DECELERATION_SPEEDS = {
        'slow': 0.5,        
        'normal': 1,
        'mildfast': 2,
        'fast': 5
    }

    #All Agent variables
    world = None
    floatScale = 10.0
    scale = Vector2D(1, 1)
    mass = 0.1
    friction = 0.01
    max_speed = 55.0
    max_force = 50.0

    #flee information
    panicDist = 35

    #wander variables
    wander_dist = 8.25
    wander_radius = 6.75
    wander_jitter = 76.0

    #Agent render shapes
    vehicle_shape = [
            Point2D(-1.0,  0.6),
            Point2D( 1.0,  0.0),
            Point2D(-1.0, -0.6)
        ]
    hunter_shape = [
            Point2D(-1.0,  0.6),
            Point2D( 0.9,  0.5),
            Point2D( 0.65,  0.4),
            Point2D( 1.1,  0.15),
            Point2D( 0.65,  0.0),
            Point2D( 1.1, -0.15),
            Point2D( 0.65, -0.4),
            Point2D( 0.9, -0.5),
            Point2D(-1.0, -0.6)
        ]

    #path variables
    waypoint_threshold = 10
    loop = False

    # group behaviour proportions  
    cohesive = .2#.35
    seperated = 0.5
    aligned = 0.2#.3
    GroupWander = 1
    cohesiveRange = 9
    seperationRange = 3
    alignmentRange = 6

    distanceFromWall = 10
    
    # debug draw info?
    show_info = False

    def __init__(self, mode='seek', world=None):
        self.nearbyAgents = []
        # keep a reference to the world object
        if not world == None:
            Agent.world = world
        self.mode = mode
        # where am i and where am i going? random
        dir = radians(random()*360)
        self.pos = Vector2D(0, 0)
        if not Agent.world == None:
            self.pos = Vector2D(randrange(Agent.world.cx), randrange(Agent.world.cy))
        elif not world == None:
            self.pos = Vector2D(randrange(world.cx), randrange(world.cy))
        self.vel = Vector2D()
        self.heading = Vector2D(sin(dir), cos(dir))
        self.side = self.heading.perp()
        self.force = Vector2D()
        self.accel = Vector2D()  # current steering force

        self.hunterTargVec = Vector2D(10,10)
        self.hunterTarg = None

        # NEW WANDER INFO
        self.wander_target = Vector2D(1, 0)
        #self.bRadius = 1.0 * scale Not sure what this is meant to be used for?

        # data for drawing this agent
        self.color = 'ORANGE'

        # path to follow
        self.path = Path()
        self.randomise_path()

    def calculate(self, delta):
        # reset the steering force
        mode = self.mode
        force = Vector2D(0,0)
        if mode == 'seek':
            force = self.seek(Agent.world.target)
        elif mode == 'arrive_slow':
            force = self.arrive(Agent.world.target, 'slow')
        elif mode == 'arrive_normal':
            force = self.arrive(Agent.world.target, 'normal')
        elif mode == 'arrive_fast':
            force = self.arrive(Agent.world.target, 'fast')
        elif mode == 'flee':
            if Agent.world.hunter != self:
                force = self.flee(Agent.world.hunter.pos, delta)
            elif Agent.world.hunter == self:
                totalx = 0
                totaly = 0
                for agent in Agent.world.agents:
                    if agent != self:
                        totalx += agent.pos.x
                        totaly += agent.pos.y
                totalAgents = len(Agent.world.agents)-1
                totalx = totalx / totalAgents
                totaly = totaly / totalAgents
                dumAgent = DummyAgent(totalx, totaly)
                force = self.pursuit(self.FindClosest(dumAgent))

        elif mode == 'pursuit' and self == Agent.world.hunter:
            target = self.FindClosest(self)
            if self.hunterTarg != None:
                if (self.hunterTarg.pos - self.pos).length() > Agent.panicDist * Agent.floatScale * 1.05:
                    if target != self.hunterTarg:
                        if self.hunterTarg != None:
                            self.hunterTarg.mode = 'pursuit'
                        self.hunterTarg = target
                else:
                    target = self.hunterTarg
            else:
                self.hunterTarg = target
            target.mode = 'flee'
            force = self.pursuit(target)
        elif mode == 'follow_path':
            force = self.FollowPath()
        elif mode == 'wander':
            force = self.groupForce(delta)
        else:
            force = self.groupForce(delta)
        forcewindow = self.windowEdge()
        if forcewindow[1] > 0:
            #print ("forcewindow %s prop = %s" % (str(forcewindow[0]) , str(forcewindow[1])))
            #if ((not forcewindow[1] == 1) and (self.pos.x < 0 or self.pos.x > Agent.world.cx or self.pos.y < 0 or self.pos.y > Agent.world.cy)) or forcewindow[1] > 1:
                #print ("error %s" % forcewindow[1])
            return ((force * (1 - forcewindow[1])) + (forcewindow[0]))
            
        return force

    def update(self, delta):
        #MUST be done at the start of the update function
        largestAgentScanRange = max(Agent.cohesiveRange, Agent.seperationRange, Agent.alignmentRange) * Agent.floatScale
        self.nearbyAgents = []
        for agent in Agent.world.agents:
            if agent.pos.distance(self.pos) < largestAgentScanRange:
                self.nearbyAgents.append(agent)

        ''' update vehicle position and orientation '''
        self.force = self.calculate(delta)
        self.force.truncate(Agent.max_force * Agent.floatScale)

        self.accel = self.force#/ (Agent.mass * Agent.floatScale)
        # new velocity
        self.vel += self.accel * delta
        # proportional friction
        #self.vel = self.vel * (1-((Agent.friction * Agent.floatScale)*(self.vel.length()/(Agent.max_speed * Agent.floatScale))))

        # check for limits of new velocity
        self.vel.truncate(Agent.max_speed * Agent.floatScale)
        # update position
        self.pos += self.vel * delta
        # update heading is non-zero velocity (moving)
        if self.vel.lengthSq() > 0.00000001:
            self.heading = self.vel.get_normalised()
            self.side = self.heading.perp()
        # treat world as continuous space - wrap new position if needed
        #Agent.world.wrap_around(self.pos)

    def render(self, color=None):
        ''' Draw the triangle agent with color'''
        color = None
        shape = None
        if(self != Agent.world.hunter):
            color = self.color
            shape = Agent.vehicle_shape
        else:
            color = 'RED'
            shape = Agent.hunter_shape
        egi.set_pen_color(name=color)
        pts = Agent.world.transform_points(shape, self.pos, self.heading, self.side, Agent.scale * Agent.floatScale)
        # draw it!
        egi.closed_shape(pts)
        #cap taget pos to window diameters
        if ((self.mode == 'pursuit' or self.mode == 'flee') and self == Agent.world.hunter):
            egi.green_pen()
            if self.hunterTargVec.y > Agent.world.cy:
                self.hunterTargVec = Vector2D(self.hunterTargVec.x, Agent.world.cy)
            elif self.hunterTargVec.y < 0:
                self.hunterTargVec = Vector2D(self.hunterTargVec.x, 0)
            if self.hunterTargVec.x > Agent.world.cx:
                self.hunterTargVec = Vector2D(Agent.world.cx, self.hunterTargVec.y)
            elif self.hunterTargVec.x < 0:
                self.hunterTargVec = Vector2D(0, self.hunterTargVec.y)
            egi.cross(self.hunterTargVec, 10)

        # add some handy debug drawing info lines - force and velocity
        if Agent.show_info:
            #s = 0.5 # <-- scaling factor
            # force
            egi.red_pen()
            egi.line_with_arrow(self.pos, self.pos + self.force, 5) #replaced s with Agent.floatScale
            # velocity
            egi.grey_pen()
            egi.line_with_arrow(self.pos, self.pos + self.vel, 5) #replaced s with Agent.floatScale

            # draw the path if it exists and the mode is follow
            if self.mode == 'follow_path':
                self.path.render()
            # draw wander info?
            elif self .mode == 'wander':
                # calculate the center of the wander circle in front of the agent
                wnd_pos = Vector2D( Agent.wander_dist * Agent.floatScale, 0)
                wld_pos = self .world.transform_point(wnd_pos, self .pos, self .heading, self .side)
                # draw the wander circle
                egi.green_pen()
                egi.circle(wld_pos, Agent.wander_radius * Agent.floatScale)
                # draw the wander target (little circle on the big circle)
                egi.red_pen()
                wnd_pos = ( self.wander_target + Vector2D( Agent.wander_dist * Agent.floatScale, 0))
                wld_pos = Agent.world.transform_point(wnd_pos, self.pos, self.heading, self.side)
                egi.circle(wld_pos, 3)
                
            #draw cohesion range
            egi.blue_pen()
            egi.circle(self.pos, Agent.cohesiveRange * Agent.floatScale)
            egi.red_pen()
            egi.circle(self.pos, Agent.seperationRange * Agent.floatScale)
            egi.green_pen()
            egi.circle(self.pos, Agent.alignmentRange * Agent.floatScale)
    def speed(self):
        return self.vel.length()

    def FindClosest(self, agentFrom):
        closest = None
        ClosestDistance = 99999999
        for agent in Agent.world.agents:
            distToAgent = agent.pos.distance(agentFrom.pos)
            if distToAgent < ClosestDistance and agent != self:# and agentToIgnore.pos.x != agentFrom.pos.x and agent.pos.y != agentFrom.pos.y:
                closest = agent
                ClosestDistance = distToAgent
        return closest


    #--------------------------------------------------------------------------

    def seek(self, target_pos):
        ''' move towards target position '''
        desired_vel = (target_pos - self.pos).normalise() * (Agent.max_speed * Agent.floatScale)
        return (desired_vel - self.vel)

    def flee(self, hunter_pos, delta):
        ''' move away from hunter position '''
        groupForced = self.groupForce(delta)
        hunterDist = (hunter_pos - self.pos).length()
        scaledPanicDist = Agent.panicDist * Agent.floatScale
        if hunterDist < scaledPanicDist:
            desired_vel = (-((hunter_pos - self.pos).normalise() * (Agent.max_speed * Agent.floatScale))) - self.vel
            proportion = hunterDist / scaledPanicDist

            return (desired_vel * (1 - proportion) + groupForced * (proportion))
        return groupForced

    def arrive(self, target_pos, speed):
        ''' this behaviour is similar to seek() but it attempts to arrive at
            the target position with a zero velocity'''
        decel_rate = self.DECELERATION_SPEEDS[speed]
        to_target = target_pos - (self.pos + self.vel)
        dist = to_target.length()
        maxSpeedScaled = Agent.max_speed * Agent.floatScale
        if not dist == 0:
            # calculate the speed required to reach the target given the
            # desired deceleration rate
            #speed = dist * decel_rate
            # make sure the velocity does not exceed the max
            #speed = min(speed, (maxSpeedScaled))
            # from here proceed just like Seek except we don't need to
            # normalize the to_target vector because we have already gone to the
            # trouble of calculating its length for dist.
            proportion = 1.0
            if dist < maxSpeedScaled:
                proportion = dist / maxSpeedScaled
            desired_vel = to_target.normalise() * maxSpeedScaled * proportion * decel_rate
            return (desired_vel - self.vel)
        return Vector2D(0, 0)

    def pursuit(self, evader):
        ''' this behaviour predicts where an agent will be in time T and seeks
            towards that point to intercept it. '''
        target_pos = evader.pos + evader.vel
        #print(str(target_pos.x) + "targetpos")
        self.hunterTargVec = Vector2D(target_pos.x, target_pos.y)
        return (self.arrive(target_pos, 'normal'))

    def FollowPath(self):
        if self.path.current_pt().distance(self.pos) < Agent.waypoint_threshold * Agent.floatScale:
            self.path.inc_current_pt()
        if self.path.is_finished():
            return self.arrive(self.path.current_pt(),'fast')
        else:
            return self.seek(self.path.current_pt())

    def randomise_path(self):
        if not Agent.world == None:
            cx = Agent.world.cx  # width
            cy = Agent.world.cy  # height
            margin = min(cx, cy) * (1/6)  # use this for padding in the next line ... #previous min(cx, cy)
            self.path.create_random_path(randint(3,16),margin,margin,cx-margin,cy-margin, Agent.loop)  # you have to figure out the parameters 

    def wander(self, delta):
        ''' Random wandering using a projected jitter circle. '''
        wt = self.wander_target
        # this behaviour is dependent on the update rate, so this line must
        # be included when using time independent framerate.
        jitter_tts = Agent.wander_jitter * delta * Agent.floatScale # this time slice
        # first, add a small random vector to the target's position
        wt += Vector2D(uniform(-1,1) * jitter_tts, uniform(-1,1) * jitter_tts)
        # re-project this new vector back on to a unit circle
        wt.normalise()
        # increase the length of the vector to the same as the radius
        # of the wander circle
        wt *= Agent.wander_radius * Agent.floatScale
        # move the target into a position WanderDist in front of the agent
        target = wt + Vector2D( Agent.wander_dist * Agent.floatScale, 0)
        # project the target into world space
        wld_target = Agent.world.transform_point(target, self.pos, self.heading, self.side)
        # and steer towards it 
        return self.arrive(wld_target, 'normal')

    def cohesionForce(self, delta):
        totalx = self.pos.x
        totaly = self.pos.y
        totalnum = 1
        cohesRange = Agent.cohesiveRange * Agent.floatScale
        for agent in self.nearbyAgents:
            if agent != self and agent.pos.distance(self.pos) < cohesRange:
                totalx += agent.pos.x
                totaly += agent.pos.y
                totalnum += 1
        if totalnum > 1:
            totalx = totalx / totalnum
            totaly = totaly / totalnum
            alliesMiddle = Vector2D(totalx, totaly)
            return self.seek(alliesMiddle) #* ((cohesRange - self.pos.distance(alliesMiddle)) / cohesRange)
        return Vector2D(0,0)
    def seperationForce(self):
        total = Vector2D(0,0)
        for agent in self.nearbyAgents:
            sepRange = Agent.seperationRange * Agent.floatScale
            if agent.pos.distance(self.pos) < sepRange:
                total += -(agent.pos - self.pos).normalise() * (Agent.max_speed * Agent.floatScale)# * ((sepRange - agent.pos.distance(self.pos)) / sepRange)
        return total
    def alignmentForce(self):
        total = self.vel
        count = 1
        for agent in self.nearbyAgents:
            if agent.pos.distance(self.pos) < Agent.alignmentRange * Agent.floatScale:
                total += agent.heading
                count += 1
        total = total / count
        total = total.truncate(Agent.max_force * Agent.floatScale)
        return total
    def groupForce(self, delta):
        force = Vector2D(0,0)
        if(Agent.cohesive > 0):
            force += (self.cohesionForce(delta) * Agent.cohesive)
        #print("cohesion %s" % str(force))
        if(Agent.seperated > 0):
            force += (self.seperationForce() * Agent.seperated)
        #print ("seperation %s" % str(self.seperationForce() * Agent.seperated))
        if(Agent.aligned > 0):
            force += (self.alignmentForce() * Agent.aligned)
        #print ("alignment %s" % str(self.alignmentForce() * Agent.aligned))
        if(Agent.GroupWander > 0):
            force += (self.wander(delta) * Agent.GroupWander)
        return force

    def windowEdge(self):
        totalVec = Vector2D(0,0)
        scaleddist = Agent.distanceFromWall * Agent.floatScale
        totalProportion = 0
        futurePos = self.pos + self.vel
        
        if futurePos.x < 0:
            futurePos.x = 0
        elif futurePos.x > Agent.world.cx:
            futurePos.x = Agent.world.cx
        if futurePos.y < 0:
            futurePos.y = 0
        elif futurePos.y > Agent.world.cy:
            futurePos.y = Agent.world.cy

        #x diff
        if futurePos.x < scaleddist:
            proportion = ((scaleddist - futurePos.x) / scaleddist)
            totalProportion = proportion
            totalVec = Vector2D(1,0) * Agent.max_speed * Agent.floatScale * proportion
        elif futurePos.x > Agent.world.cx - scaleddist:
            proportion = (futurePos.x + scaleddist - Agent.world.cx) / scaleddist
            totalProportion = proportion
            totalVec = Vector2D(-1,0) * Agent.max_speed * Agent.floatScale * proportion
        #y diff
        if futurePos.y < scaleddist:
            proportion = (scaleddist - futurePos.y) / scaleddist
            totalProportion = max(proportion, totalProportion)
            totalVec += Vector2D(0,1) * Agent.max_speed * Agent.floatScale * proportion
        elif futurePos.y > Agent.world.cy - scaleddist:
            proportion = (futurePos.y + scaleddist - Agent.world.cy) / scaleddist
            totalProportion = max(proportion, totalProportion)
            totalVec += Vector2D(0,-1) * Agent.max_speed * Agent.floatScale * proportion
        return [totalVec, totalProportion]