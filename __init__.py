# ***** BEGIN GPL LICENSE BLOCK *****
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 59 Temple Place - Suite 330, Boston, MA	 02111-1307, USA.
#
# ***** END GPL LICENCE BLOCK *****

bl_info = {
	"name": "Cross section Leger",
	"author": "Yorik van Havre, Alejandro Sierra, Howard Trickey, Campbell Barton, Ejnar Rasmussen",
	"description": "Creates cross section(s) of the selected object(s) using the active object as cut plane",
	"version": (0, 1, 8),
	"blender": (2, 92, 0),
	"category": "Object",
	"location": "Toolshelf > Cross Section",
	"warning": '',
	"wiki_url": "",
	"tracker_url": "",
	}


"""Script made by Yorik for 2.4x based upon a code by Cambo found on blenderArtists,
and ported to 2.5x by Ejnaren.

This scripts creates cross-sections of selected objects, at intersection with
active plane object.

Installation:

Via the addons menu, no particular action needed

Usage:

Select objects you want to cut, then select (make active)
the cutting plane, then run the script. The resulting section parts will be
filled and nicely placed inside a group for easy selection.

Options:

You can turn the fill option on or off, if enabled, closed edge loops are turned into faces.

Limitations:

- Only Mesh and Surface (by approximation) objects will be cut
- The cutting object must be a plane (it must have only one face)
- The cutting plane shouldn't have any parents, if it does, the rotation from
  the parents will not affect the section's position and rotation"""

import bpy
import time
EPSILON = 0.000001


def dupTest(object):
	"""Checks objects for duplicates enabled (any type)
	object: Blender Object.
	Returns: Boolean - True if object has any kind of duplicates enabled."""

	if (object.is_instancer):
		return True
	else:
		return False


def getObjectsAndDuplis(oblist, MATRICES=False, HACK=False):
	"""Return a list of real objects and duplicates and optionally their matrices
	oblist: List of Blender Objects
	MATRICES: Boolean - Check to also get the objects matrices default=False
	HACK: Boolean - See note default=False
	Returns: List of objects or
			 List of tuples of the form:(ob,matrix) if MATRICES is set to True
	NOTE: There is an ugly hack here that excludes all objects whose name
	starts with "dpl_" to exclude objects that are parented to a duplicating
	object, User must name objects properly if hack is used."""

	result = []

	for o in oblist:
		if dupTest(o):
			dup_obs = o.children
			if len(dup_obs):
				for dup_ob in dup_obs:
					if MATRICES:
						result.append((dup_ob, dup_ob.matrix_world))
					else:
						result.append(dup_ob)
		else:
			if HACK:
				if o.name[0:4] != "dpl_":
					if MATRICES:
						result.append((o, o.matrix_world))
					else:
						result.append(o)
			else:
				if MATRICES:
					result.append((o, o.matrix_world))
				else:
					result.append(o)

	return result


def section(context, m, itM, FILL=True):
	"""Finds the section mesh between a mesh and a plane
	m: Blender Mesh - the mesh to be cut
	itM: Matrix - The matrix of object of the mesh for correct coordinates
	FILL: Boolean - Check if you want to fill the resulting mesh, default=True
	Returns: Mesh - the resulting mesh of the section if any or
			 Boolean - False if no section exists"""

	verts = []
	edges = []
	ed_xsect = {}

	for ed in m.edges:

		# getting a vector from each edge vertices to a point on the plane
		# first apply transformation matrix so we get the real section

		id0 = ed.vertices[0]
		p0 = itM @ m.vertices[id0].co
		id1 = ed.vertices[1]
		p1 = itM @ m.vertices[id1].co

		d0 = abs(p0.z)
		d1 = abs(p1.z)

		# Check to see if edge intersects.
		if (p0.z > 0) != (p1.z > 0):
			t = d0 / (d0 + d1)
			co = p0 + (p1 - p0) * t
			ed_xsect[ed.key] = len(verts)
			verts.append(co)

		elif d0 < EPSILON:
			ed_xsect[ed.key] = len(verts)
			verts.append(p0)

		elif d1 < EPSILON:
			ed_xsect[ed.key] = len(verts)
			verts.append(p1)

	for p in m.polygons:
		# get the edges that the intersecting points form
		# to explain this better:
		# If a face has an edge that is proven to be crossed then use the
		# mapping we created earlier to connect the edges properly
		ps = [ed_xsect[key] for key in p.edge_keys if key in ed_xsect]
		s = len(ps)
		if s == 2:
			edges.append(tuple(ps))
		elif s > 2:
			# when one vertex is coplanar
			# the end of two edges are found
			unique = {tuple(verts[id]): id for id in ps}
			if len(unique) == 2:
				edges.append(tuple(unique.values()))

	if edges:

		me = bpy.data.meshes.new('Section')
		me.from_pydata(verts, edges, [])

		# create a temp object and link it to the current scene to be able to
		# apply rem Doubles and fill
		o = bpy.data.objects.new('Section', me)

		scene = context.scene
		#scene.objects.link(o)
		bpy.context.collection.objects.link(o)

		# do a remove doubles to cleanup the mesh, this is needed when there
		# is one or more edges coplanar to the plane.
		o.select_set(True)
		context.view_layer.objects.active = o

		bpy.ops.object.mode_set(mode="EDIT")
		bpy.ops.mesh.select_mode(type="EDGE", action="ENABLE")
		bpy.ops.mesh.select_all(action="SELECT")

		# remove doubles:
		bpy.ops.mesh.remove_doubles()

		if FILL:
			bpy.ops.mesh.edge_face_add()

		# recalculate outside normals:
		bpy.ops.mesh.normals_make_consistent(inside=False)

		bpy.ops.object.mode_set(mode='OBJECT')
		return o

	else:
		return False


# operator definition
class OBJECT_OT_cross_section(bpy.types.Operator):
	"""Creates cross section(s) of the selected object(s), using the active object as cut plane"""
	bl_idname = "object.cross_section"
	bl_label = "Cross Section"
	bl_options = {'REGISTER', 'UNDO'}
	bl_description = "Creates cross section(s) of the selected object(s), using the active object as cut plane"

	@classmethod
	def poll(cls, context):
		if context.view_layer.objects.active:
			if len(context.selected_objects) > 1:
				return True
		return False

	def execute(self, context):

		act = context.view_layer.objects.active
		sel = context.selected_objects[:]
		
		if not act or act.type != 'MESH':
			self.report({'WARNING'}, "No meshes or active object selected")
			return

		if len(sel) >= 2:

			# Window.WaitCursor(1) 2.6 equivalent?
			t = time.time()

			# Get section Plane's transformation matrix
			tM = act.matrix_world
			itM = tM.inverted()

			# filter selection to get back any duplis to cut them as well
			oblist = getObjectsAndDuplis(sel, MATRICES=True, HACK=False)

			# deselect all selected objects so we can select new ones and put
			# them into the group that will contain all new objects
			for o in sel:
				o.select_set(False)

			# create a list to hold all objects that we'll create
			parts = []
			for o, wM in oblist:
				typ = o.type
				if o != act and (typ == "MESH" or typ == "SURFACE" or typ == "CURVE"):

					# Use BpyMesh to get mesh data so that modifiers are applied
					# and to be able to cut surfaces and curves (curves behave
					# strange though and don't seem to be very usefull

					#m = o.to_mesh(scene=context.scene, apply_modifiers=True, settings='PREVIEW')
					m = o.to_mesh()
					# Run the main function
					ob = section(context, m, itM @ wM, context.scene.cross_section_fill)

					# if there's no intersection just skip the object creation
					if ob:

						# Reset section part's center and orientation
						# Since it's a 2d object it's best to use the objects
						# center of mass instead of bounding box center
						ob.matrix_world = tM.copy()
						parts.append(ob)

					else:
						self.report({'WARNING'}, "an object does not intersect the plane, continuing happily")
			# Put the parts of the section into a new group so that it's easy to
			# select them all
			#sect_grp = bpy.data.groups.new('section')
			sect_grp = bpy.data.collections.new('section')
			bpy.context.scene.collection.children.link(sect_grp)
			
			for part in parts:
				#sect_grp.objects.link(part)
				sect_grp.objects.link(part)
				bpy.context.view_layer.active_layer_collection.collection.objects.unlink(part)

		else:
			self.report({'WARNING'}, "the selection is empty, no object to cut!")

		print('CrossSection finished in %.2f seconds' % (time.time() - t))

		act.select_set(False)

		return {'FINISHED'}


# a panel containing 2 buttons
class VIEW3D_PT_tools_cross_section(bpy.types.Panel):
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = "Tool"
	bl_context = "objectmode"
	bl_label = "Cross Section"

	def draw(self, context):
		row = self.layout.row(align=True)
		row.alignment = 'LEFT'
		row.prop(context.scene, "cross_section_fill")
		row.operator("object.cross_section", text="Create cross section")


classes = (OBJECT_OT_cross_section,VIEW3D_PT_tools_cross_section)


# Registers the operator, the toolshelf panel and the fill property
def register():

# this registers all the panels and operators
	from bpy.utils import register_class
	for cls in classes:
		register_class(cls)

	# this stores the fill property in the current scene
	bpy.types.Scene.cross_section_fill = bpy.props.BoolProperty(
			name="Fill",
			description="Fill closed contours with faces",
			default=True)


# Removes the operator, the toolshelf and the fill property
def unregister():

	from bpy.utils import unregister_class
	for cls in reversed(classes):
		unregister_class(cls)

	del bpy.types.Scene.cross_section_fill


# This lets you import the script without running it
if __name__ == "__main__":
	register()
