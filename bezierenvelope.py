#!/usr/bin/env python
'''
Bezier Envelope extension for Inkscape
Copyright (C) 2009 Gerrit Karius

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.


About the Bezier Envelope extension:

This extension implements Bezier enveloping.
It takes an arbitrary path (the "letter") and a 4-sided path (the "envelope") as input.
The envelope must be 4 segments long. Unless the letter is to be rotated or flipped,
the envelope should begin at the upper left corner and be drawn clockwise.
The extension then attempts to squeeze the letter into the envelope
by rearranging all anchor and handle points of the letter's path.

In order to do this, the bounding box of the letter is used.
All anchor and bezier handle points get new x and y coordinates between 0% and 100%
according to their place inside the bounding box.
The 4 sides of the envelope are then interpreted as deformed axes.
Points at 0% or 100% could be placed along these axes, but because most points
are somewhere inside the bounding box, some tweening of the axes must be done.

The function mapPointsToMorph does the tweening.
Say, some point is at x=30%, y=40%.
For the tweening, the function tweenCubic first calculates a straight tween
of the y axis at the x percentage of 30%.
This tween axis now floats somewhere between the y axis keys at the x percentage,
but is not necessarily inside the envelope, because the x axes are not straight.
Now, the end points on the two x axes at 30% are calculated. The function match()
takes these points and calculates a "stretch" transform which maps the two anchor
points of the y axis tween to the two points on the x axes by rotating the tween and
stretching it along its endpoints. This transform is then applied to the handle points,
to get the entire tweened y axis to its x tweened position.
Last, the point at the y percentage 40% of this y axis tween is calculated.
That is the final point of the enveloped letter.

Finally, after all of the letter's points have been recalculated in this manner,
the resulting path is taken and replaces the letter's original path.

TODO:
* Some points of the letter appear outside the envelope, apparently because the bounding box
calculated by simpletransform.py is only a rough estimate. -> Calculate the real bbox,
perhaps using other existing extensions, or py2geom.
* Currently, both letter and envelope must be paths to work.
-> Arbitrary other shapes like circles and rectangles should be interpreted as paths.
* It should be possible to select several letters, and squeeze them into one envelope as a group.
* It should be possible to insert a clone of the letter, instead of replacing it.
* Bug #241565 prevented the matrix parser constructors from working. This extension can
only be used with the fixed version of simpletransform.py. As a workaround, two matrix constructors
were copied into this file.
* This program was originally written in Java. Maybe for some code, Python shortcuts can be used.

I hope the comments are not too verbose. Enjoy!

'''
import inkex, os, simplepath, cubicsuperpath, simpletransform,sys
from ffgeom import *


class BezierEnvelope(inkex.Effect):

	segmentTypes = ["move","line","quad","cubic","close"]

	def __init__(self):
			inkex.Effect.__init__(self)
	
	def effect(self):
		if len(self.options.ids) < 2:
			raise Exception, "Two paths must be selected. The 1st is the letter, the 2nd is the envelope and must have 4 sides."
			exit()
            
		letterElement = self.selected[self.options.ids[0]]
		envelopeElement = self.selected[self.options.ids[1]]

		if letterElement.tag != inkex.addNS('path','svg') or envelopeElement.tag != inkex.addNS('path','svg'):
			raise Exception, "Both letter and envelope must be SVG paths."
			exit()

		axes = extractMorphAxes( simplepath.parsePath( envelopeElement.get('d') ) );
		if axes is None:
			raise Exception, "No axes found on envelope."
		axisCount = len(axes)
		if axisCount < 4:
			raise Exception, "The envelope path has less than 4 segments."
		for i in range( 0, 4 ):
			if axes[i] is None:
				raise Exception, "axes[%i] is None" % i
		# morph the enveloped element according to the axes
		morphElement( letterElement, envelopeElement, axes );
	
def morphElement( letterElement, envelopeElement, axes ):
	path = simplepath.parsePath( letterElement.get('d') )
	morphedPath = morphPath( path, axes )
	letterElement.set("d", simplepath.formatPath(morphedPath))

	
# Morphs a path into a new path, according to cubic curved bounding axes.
def morphPath( path, axes ):
	bounds = simpletransform.roughBBox( cubicsuperpath.CubicSuperPath(path) )
	newPath = []
	current = [ 0.0, 0.0 ]
	start = [ 0.0, 0.0 ]

	for cmd, params in path:
		segmentType = cmd
		points = params
		if segmentType == "M":
			start[0] = points[0]
			start[1] = points[1]
		segmentType = convertSegmentToCubic( current, segmentType, points, start )
		percentages = [0.0]*len(points)
		morphed = [0.0]*len(points)
		numPts = getNumPts( segmentType )
		normalizePoints( bounds, points, percentages, numPts )
		mapPointsToMorph( axes, percentages, morphed, numPts )
		addSegment( newPath, segmentType, morphed )
		if len(points) >= 2:
			current[0] = points[ len(points)-2 ]
			current[1] = points[ len(points)-1 ]
	return newPath

	
def getNumPts( segmentType ):
	if segmentType == "M":
		return 1
	if segmentType == "L":
		return 1
	if segmentType == "Q":
		return 2
	if segmentType == "C":
		return 3
	if segmentType == "Z":
		return 0
	return -1
	

	
def addSegment( path, segmentType, points ):
	path.append([segmentType,points])


# Converts visible path segments (Z,L,Q) into absolute cubic segments (C).
def convertSegmentToCubic( current, segmentType, points, start ):
	if segmentType == "M":
		return "M";
	if segmentType == "C":
		return "C";
	elif segmentType == "Z":
		for i in range(0,6):
			points.append(0.0)
		points[4] = start[0]
		points[5] = start[1]
		thirdX = (points[4] - current[0]) / 3.0
		thirdY = (points[5] - current[1]) / 3.0
		points[2] = points[4]-thirdX
		points[3] = points[5]-thirdY
		points[0] = current[0]+thirdX
		points[1] = current[1]+thirdY
		return "C"
	elif segmentType == "L":
		for i in range(0,4):
			points.append(0.0)
		points[4] = points[0]
		points[5] = points[1]
		thirdX = (points[4] - current[0]) / 3.0
		thirdY = (points[5] - current[1]) / 3.0
		points[2] = points[4]-thirdX
		points[3] = points[5]-thirdY
		points[0] = current[0]+thirdX
		points[1] = current[1]+thirdY
		return "C"
	elif segmentType == "Q":
		for i in range(0,2):
			points.append(0.0)
		firstThirdX = (points[0] - current[0]) * 2.0 / 3.0
		firstThirdY = (points[1] - current[1]) * 2.0 / 3.0
		secondThirdX = (points[2] - points[0]) * 2.0 / 3.0
		secondThirdY = (points[3] - points[1]) * 2.0 / 3.0
		points[4] = points[2]
		points[5] = points[3]
		points[0] = current[0] + firstThirdX
		points[1] = current[1] + firstThirdY
		points[2] = points[2] - secondThirdX
		points[3] = points[3] - secondThirdY
		return "C"
	else:
		print >>sys.stderr, "unsupported segment type: " + segmentType
		return segmentType


# Normalizes the points of a path segment, so that they are expressed as percentage coordinates
# relative to the bounding box axes of the total shape.
# @param bounds The bounding box of the shape.
# @param points The points of the segment.
# @param percentages The returned points in normalized percentage form.
# @param numPts
def normalizePoints( bounds, points, percentages, numPts ):
	# bounds has structure xmin,xMax,ymin,yMax
	xmin,xMax,ymin,yMax = bounds
	for i in range( 0, numPts ):
		x = i*2
		y = i*2+1
		percentages[x] = (points[x] - xmin) / (xMax-xmin)
		percentages[y] = (points[y] - ymin) / (yMax-ymin)

	

# Extracts 4 axes from a path. It is assumed that the path starts with a move, followed by 4 cubic paths.
# The extraction reverses the last 2 axes, so that they run in parallel with the first 2.
# @param path The path that is formed by the axes.
# @return The definition points of the 4 cubic path axes as float arrays, bundled in another array.
def extractMorphAxes( path ):
	points = []
	current = [ 0.0, 0.0 ]
	start = [ 0.0, 0.0 ]
	# the curved axis definitions go in here
	axes = [None]*4
	i = 0
	
	for cmd, params in path:
		points = params
		cmd = convertSegmentToCubic( current, cmd, points, start )
		
		if cmd == "M":
			current[0] = points[0]
			current[1] = points[1]
			start[0] = points[0]
			start[1] = points[1]

		elif cmd == "C":
			
			# 1st cubic becomes x axis 0
			# 2nd cubic becomes y axis 1
			# 3rd cubic becomes x axis 2 and is reversed
			# 4th cubic becomes y axis 3 and is reversed
			if i % 2 == 0:
				index = i
			else:
				index = 4-i
			if( i < 2 ):
				# axes 1 and 2
				axes[index] = [	current[0], current[1], points[0], points[1], points[2], points[3], points[4], points[5] ]
			elif( i < 4 ):
				# axes 3 and 4
				axes[index] = [ points[4], points[5], points[2], points[3], points[0], points[1], current[0], current[1] ]
			else:
				# more than 4 axes - hopefully it was an unnecessary trailing Z
				{}
			current[0] = points[4]
			current[1] = points[5]
			i = i + 1
		elif cmd == "Z":
			#do nothing
			{}
		else:
			raise Exception, "Unsupported segment type: %s" % cmd
			return None
		
	return axes

		
# Projects points in percentage coordinates into a morphed coordinate system that is framed
# by 2 x cubic curves (along the x axis) and 2 y cubic curves (along the y axis).
# @param axes The x and y axes of the envelope.
# @param percentage The current segment of the letter in normalized percentage form.
# @param morphed The array to hold the returned morphed path.
# @param numPts The number of points to be transformed.
def mapPointsToMorph( axes, percentage, morphed, numPts ):
	# rename the axes for legibility
	yCubic0 = axes[1]
	yCubic1 = axes[3]
	xCubic0 = axes[0]
	xCubic1 = axes[2]
	# morph each point
	for i in range( 0, numPts ):
		x = i*2
		y = i*2+1
		# tween between the morphed y axes according to the x percentage
		tweenedY = tweenCubic( yCubic0, yCubic1, percentage[x] )
		# get 2 points on the morphed x axes
		xSpot0 = pointOnCubic( xCubic0, percentage[x] )
		xSpot1 = pointOnCubic( xCubic1, percentage[x] )
		# create a transform that stretches the y axis tween between these 2 points
		yAnchor0 = [ tweenedY[0], tweenedY[1] ]
		yAnchor1 = [ tweenedY[6], tweenedY[7] ]
		xTransform = match( yAnchor0, yAnchor1, xSpot0, xSpot1 )
		# map the y axis tween to the 2 points by applying the stretch transform
		for j in range(0,4):
			x2 = j*2
			y2 = j*2+1
			pointOnY = [tweenedY[x2],tweenedY[y2]]
			simpletransform.applyTransformToPoint( xTransform, pointOnY )
			tweenedY[x2] = pointOnY[0]
			tweenedY[y2] = pointOnY[1]
		# get the point on the tweened and transformed y axis according to the y percentage
		morphedPoint = pointOnCubic( tweenedY, percentage[y] )
		morphed[x] = morphedPoint[0]
		morphed[y] = morphedPoint[1]
		
# Calculates the point on a cubic bezier curve at the given percentage.
def pointOnCubic( c, t ):
	point = [0.0,0.0]
	_t_2 = t*t
	_t_3 = _t_2*t
	_1_t = 1-t
	_1_t_2 = _1_t*_1_t
	_1_t_3 = _1_t_2*_1_t
	
	for i in range( 0, 2 ):
		point[i] = c[i]*_1_t_3 + 3*c[2+i]*_1_t_2*t + 3*c[4+i]*_1_t*_t_2 + c[6+i]*_t_3
	return point

# Tweens 2 bezier curves in a straightforward way,
# i.e. each of the points on the curve is tweened along a straight line
# between the respective point on key1 and key2.
def tweenCubic( key1, key2, percentage ):
	tween = [0.0]*len(key1)
	for i in range ( 0, len(key1) ):
		tween[i] = key1[i] + percentage * (key2[i] - key1[i])
	return tween

# Calculates a transform that matches 2 points to 2 anchors
# by rotating and scaling (up or down) along the axis that is formed by
# a line between the two points.
def match( p1, p2, a1, a2 ):
	x = 0
	y = 1
	# distances
	dp = [ p2[x]-p1[x], p2[y]-p1[y] ]
	da = [ a2[x]-a1[x], a2[y]-a1[y] ]
	# angles
	angle_p = math.atan2( dp[x], dp[y] )
	angle_a = math.atan2( da[x], da[y] )
	# radians
	#rp = math.sqrt( dp[x]*dp[x] + dp[y]*dp[y] )
	#ra = math.sqrt( da[x]*da[x] + da[y]*da[y] )
	rp = math.hypot( dp[x], dp[y] )
	ra = math.hypot( da[x], da[y] )
	# scale
	scale = ra / rp
	# transforms in the order they are applied
	t1 = simpletransform.parseTransform( "translate(%f,%f)"%(-p1[x],-p1[y]) )
	#t2 = simpletransform.parseTransform( "rotate(%f)"%(-angle_p) )
	#t3 = simpletransform.parseTransform( "scale(%f,%f)"%(scale,scale) )
	#t4 = simpletransform.parseTransform( "rotate(%f)"%angle_a )
	t2 = rotateTransform(-angle_p)
	t3 = scaleTransform( scale, scale )
	t4 = rotateTransform( angle_a )
	t5 = simpletransform.parseTransform( "translate(%f,%f)"%(a1[x],a1[y]) )
	# transforms in the order they are multiplied
	t = t5
	t = simpletransform.composeTransform( t, t4 )
	t = simpletransform.composeTransform( t, t3 )
	t = simpletransform.composeTransform( t, t2 )
	t = simpletransform.composeTransform( t, t1 )
	# return the combined transform
	return t


def rotateTransform( a ):
	return [[math.cos(a),-math.sin(a),0],[math.sin(a),math.cos(a),0]]

def scaleTransform( sx, sy ):
	return [[sx,0,0],[0,sy,0]]
	
e = BezierEnvelope()
e.affect()

