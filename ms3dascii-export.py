import bpy
import mathutils
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy.types import Operator
from bpy_extras.io_utils import ExportHelper
from os import path

bl_info = {
    "name": "Export to MS3DASCII",
    "author": "Mikex5",
    "version": (0, 1, 2),
    "blender": (2, 80, 0),
    "location": "File > Export > MS3DASCII",
    "description": "Export > MS3DASCII",
    "warning": "",
    "category": "Import-Export"
}

# Utility classes to organize data for MS3DASCII
class MS3DMesh:
    def __init__(self, name="", flag=0, mat=0):
        self.Name = name
        self.Flags = flag
        self.Material = mat
        self.Vertices = []
        self.Normals = []
        self.Triangles = []

class MS3DVertex:
    def __init__(self, flag=0, x=0, y=0, z=0, u=0, v=0, bone=-1):
        self.Flags = flag
        self.X = round(x, 6)
        self.Y = round(y, 6)
        self.Z = round(z, 6)
        self.U = round(u, 6)
        self.V = round(v, 6)
        self.Bone = bone
    def __eq__(self,other):
        return ((self.X == other.X)
                and (self.Y == other.Y)
                and (self.Z == other.Z)
                and (self.U == other.U)
                and (self.V == other.V)
                and (self.Flags == other.Flags)
                and (self.Bone == other.Bone))

class MS3DNormal:
    def __init__(self, x=0, y=0, z=0):
        self.X = round(x, 6)
        self.Y = round(y, 6)
        self.Z = round(z, 6)
    def __eq__(self,other):
        return ((self.X == other.X)
                and (self.Y == other.Y)
                and (self.Z == other.Z))

class MS3DTriangle:
    def __init__(self, flag=0, v1=0, v2=0, v3=0, n1=0, n2=0, n3=0, smooth=1):
        self.Flags = flag
        self.Verts = [v1, v2, v3]
        self.Norms = [n1, n2, n3]
        self.SmoothGroup = smooth

class MS3DMaterial:
    def __init__(self, name="",
                    ambient=[.2,.2,.2,1],
                    diffuse=[.8,.8,.8,1],
                    specular=[1,1,1,1],
                    emissive=[0,0,0,0],
                    shininess=0,
                    alpha=1,
                    colorMap="",
                    alphaMap=""):
        self.Name = name
        self.Ambient = ambient
        self.Diffuse = diffuse
        self.Specular = specular
        self.Emissive = emissive
        self.Shininess = shininess
        self.Alpha = alpha
        self.ColorMap = colorMap
        self.AlphaMap = alphaMap

class MS3DKeyFrame:
    def __init__(self, time=1, x=0, y=0, z=0):
        self.Time = time
        self.X = x
        self.Y = y
        self.Z = z

class MS3DBone:
    def __init__(self, name="", parent="", flag=0, pos=[0,0,0], rot=[0,0,0]):
        self.Name = name
        self.Parent = parent
        self.Flags = flag
        self.IdlePos = pos
        self.IdleRot = rot
        self.PosFrames = []
        self.RotFrames = []

class ExportMs3dascii(Operator, ExportHelper):
    """Export Object(s) to MS3DASCII"""
    bl_idname = "export_ms3dascii.scene"
    bl_label = "Export MS3DASCII"
    bl_options = {"UNDO"}

    filename_ext = ".txt"

    filter_glob: StringProperty(
        default="*.txt",
        options={'HIDDEN'},
        maxlen=255,
    )

    export_selection: BoolProperty(
        name="Export Selected",
        description="Only export selected objects",
        default=True,
    )

    export_animations: BoolProperty(
        name="Export Animation",
        description="Export bone group animations",
        default=True,
    )

    bone_threshold: FloatProperty(
        name="Bone Weight Threshold",
        description="Minimum weight needed for a vertex to be considered part of a bone group",
        default=0.5,
        min=0.0,
        max=1.0,
        soft_min=0.0,
        soft_max=1.0
    )

    animation_fps: IntProperty(
        name="Keyframes Per Second",
        description="Number of keyframes per second for the exported animations",
        default=30,
        min=1,
        max=300,
        soft_min=1,
        soft_max=300,
        step=10
    )

    export_normals: EnumProperty(
        name="Normals",
        description="Choose how normals are calculated",
        items=(
            ("FACE", "Per Face", "Per Face"),
            ("VERTEX", "Per Vertex", "Per Vertex"),
        ),
        default="FACE",
    )

    separate_materials: BoolProperty(
        name="Separate Materials",
        description="Export materials in separate file",
        default=False,
    )

    separate_animations: BoolProperty(
        name="Separate Animations",
        description="Export animations in separate file",
        default=False,
    )

    def execute(self, context):
        # Get list of objects to export
        if self.export_selection:
            exportList = [obj for obj in bpy.context.selected_objects if obj.type in ["MESH", "ARMATURE"]]
        else:
            exportList = [obj for obj in bpy.context.scene.collection.all_objects if obj.type in ["MESH", "ARMATURE"]]
        meshes = []
        materials = []
        animations = []
        objidx = 0
        scene = bpy.context.scene
        # Blender and MS3D have very different ways of representing data, parse it all before writing out
        # Also important: XYZ in Blender -> YZX in MS3D
        #         Z              Y
        # Blender |         MS3D |
        #         |____Y         |____X
        #        /              /
        #       X              Z
        while objidx < len(exportList):
            # TODO: modify for edit mode support? see gotchas page https://docs.blender.org/api/current/info_gotcha.html
            originalObj = exportList[objidx]
            anims = []
            if originalObj.type == "ARMATURE":
                obj = None
                # Separate any meshes that are using this armature
                for child in originalObj.children:
                    if child.type == "MESH":
                        if obj == None:
                            obj = child
                        else:
                            exportList.append(child)
                # Parse bones and animations
                for bone in originalObj.data.bones:
                    if bone.parent == None:
                        posIdle = bone.head_local
                        posIdle = originalObj.matrix_world @ posIdle
                        parent = ""
                    else:
                        posIdle = [x for x in bone.head_local]
                        parent = bone.parent.name
                    rotIdle = [y for y in bone.matrix_local.to_euler("YZX")]
                    anims.append(MS3DBone(bone.name,parent,0,[posIdle[1],posIdle[2],posIdle[0]],rotIdle))
                # MS3D animations are 30fps but support floats for keyframe times
                # Sample animations at user specified output fps
                if self.export_animations:
                    timeStep = 1 / self.animation_fps
                    currentTime = 0
                    blenderFrame = scene.frame_start
                    exportFrame = 1
                    while blenderFrame <= scene.frame_end + 1:
                        scene.frame_set(frame=int(blenderFrame), subframe=blenderFrame % 1)
                        for boneidx in range(len(anims)):
                            correctIdlePos = [anims[boneidx].IdlePos[2],anims[boneidx].IdlePos[0],anims[boneidx].IdlePos[1]]
                            bone = originalObj.pose.bones[boneidx]
                            if anims[boneidx].Parent == "":
                                posAnim = [x for x in bone.head]
                            else:
                                posAnim = [bone.head[x] - correctIdlePos[x] for x in range(3)]
                            rotAnim = [bone.matrix.to_euler("YZX")[x] - anims[boneidx].IdleRot[x] for x in range(3)]
                            anims[boneidx].PosFrames.append(MS3DKeyFrame(exportFrame, posAnim[1], posAnim[2], posAnim[0]))
                            anims[boneidx].RotFrames.append(MS3DKeyFrame(exportFrame, rotAnim[0], rotAnim[1], rotAnim[2]))
                        currentTime += timeStep
                        blenderFrame = (scene.render.fps * currentTime) + scene.frame_start
                        exportFrame = (30 * currentTime) + 1
                    # Root bones should have a starting rotation of 0, so sayeth I
                    for bone in anims:
                        if bone.Parent == "":
                            bone.IdleRot = [0,0,0]
                    # Add animation
                    animations.append(anims)
                # No meshes to parse, continue
                if obj == None:
                    objidx += 1
                    continue
            else:
                obj = exportList[objidx]
            # Parse the mesh
            mesh = obj.data
            outMesh = MS3DMesh(mesh.name, 0, objidx)
            for polyIdx in range(len(mesh.polygons)):
                poly = mesh.polygons[polyIdx]
                vl = []
                nl = []
                if self.export_normals == "FACE":
                    tempNorm = MS3DNormal(poly.normal[1],poly.normal[2],poly.normal[0])
                    try:
                        nidx = outMesh.Normals.index(tempNorm)
                    except ValueError:
                        nidx = len(outMesh.Normals)
                        outMesh.Normals.append(tempNorm)
                # TODO: consider using MeshLoopTriangle https://docs.blender.org/api/current/bpy.types.MeshLoopTriangle.html
                for lidx in poly.loop_indices:
                    loop = mesh.loops[lidx]
                    vcoords = mesh.vertices[loop.vertex_index].co
                    vtexmap = mesh.uv_layers.active.data[lidx].uv
                    # Determine the bone for this vertex
                    vweight = 0
                    vbone = -1
                    for bone in obj.vertex_groups:
                        try:
                            weight = bone.weight(loop.vertex_index)
                        except:
                            weight = 0
                        if weight > vweight:
                            vweight = weight
                            if weight >= self.bone_threshold:
                                vbone = bone.index
                    tempVert = MS3DVertex(0, vcoords[1], vcoords[2], vcoords[0], vtexmap[0], vtexmap[1]*-1, vbone)
                    try:
                        vidx = outMesh.Vertices.index(tempVert)
                    except ValueError:
                        vidx = len(outMesh.Vertices)
                        outMesh.Vertices.append(tempVert)
                    if self.export_normals != "FACE":
                        vnorm = mesh.vertices[loop.vertex_index].normal
                        tempNorm = MS3DNormal(vnorm[1], vnorm[2], vnorm[0])
                        try:
                            nidx = outMesh.Normals.index(tempNorm)
                        except ValueError:
                            nidx = len(outMesh.Normals)
                            outMesh.Normals.append(tempNorm)
                    vl.append(vidx)
                    nl.append(nidx)
                for tidx in range(1, len(vl)-1):
                    # Discard if this triangle is a line. It happens sometimes.
                    vec1 = mathutils.Vector((outMesh.Vertices[vl[0]].X - outMesh.Vertices[vl[tidx]].X,
                                            outMesh.Vertices[vl[0]].Y - outMesh.Vertices[vl[tidx]].Y,
                                            outMesh.Vertices[vl[0]].Z - outMesh.Vertices[vl[tidx]].Z))
                    vec2 = mathutils.Vector((outMesh.Vertices[vl[0]].X - outMesh.Vertices[vl[tidx+1]].X,
                                            outMesh.Vertices[vl[0]].Y - outMesh.Vertices[vl[tidx+1]].Y,
                                            outMesh.Vertices[vl[0]].Z - outMesh.Vertices[vl[tidx+1]].Z))
                    if vec1.angle(vec2) < 0.00001:
                        continue
                    outMesh.Triangles.append(MS3DTriangle(0,vl[0],vl[tidx],vl[tidx+1],nl[0],nl[tidx],nl[tidx+1],polyIdx+1))
            meshes.append(outMesh)
            # Best effort, Blender materials do not translate well
            mat = obj.active_material
            if mat != None:
                diffuse = [x for x in mat.diffuse_color]
                specular = [x for x in mat.specular_color]
                specular.append(mat.specular_intensity)
                for node in mat.node_tree.nodes:
                    if node.type == "TEX_IMAGE":
                        tex = bpy.path.abspath(node.image.filepath)
                        break
                materials.append(MS3DMaterial(name=mat.name, diffuse=diffuse, specular=specular, shininess=mat.metallic, colorMap=tex))
            objidx += 1
        # Open file and write out
        extIdx = self.filepath.rfind(".")
        f = open(self.filepath, 'w')
        f.write("// MilkShape 3D ASCII\n// Converted using ms3dascii-export Blender plugin\n// https://github.com/mikex5/ms3dascii-blender-addon")
        # write out frames, which is on top for some reason
        f.write("\nFrames: {}\nFrame: 1\n\n".format(int((scene.frame_end - scene.frame_start + 1) * (30 / scene.render.fps))))
        # write out meshes, normals, and triangles
        f.write("Meshes: {}\n".format(len(meshes)))
        for mesh in meshes:
            f.write("\"{}\" {} {}\n".format(mesh.Name, mesh.Flags, mesh.Material))
            f.write("{}\n".format(len(mesh.Vertices)))
            for v in mesh.Vertices:
                f.write("{} {:.6f} {:.6f} {:.6f} {:.6f} {:.6f} {}\n".format(v.Flags,round(v.X,6),round(v.Y,6),round(v.Z,6),round(v.U,6),round(v.V,6),v.Bone))
            f.write("{}\n".format(len(mesh.Normals)))
            for n in mesh.Normals:
                f.write("{:.6f} {:.6f} {:.6f}\n".format(round(n.X,6),round(n.Y,6),round(n.Z,6)))
            f.write("{}\n".format(len(mesh.Triangles)))
            for t in mesh.Triangles:
                f.write("{} {} {} {} {} {} {} {}\n".format(t.Flags,t.Verts[0],t.Verts[1],t.Verts[2],t.Norms[0],t.Norms[1],t.Norms[2],t.SmoothGroup))
        # Write out materials
        if self.separate_materials:
            f.write("Materials: 0\n")
            matfile = open("{} mats.{}".format(self.filepath[:extIdx], self.filepath[extIdx+1:]), 'w')
        else:
            matfile = f
        matfile.write("Materials: {}\n".format(len(materials)))
        for mat in materials:
            matfile.write("\"{}\"\n".format(mat.Name))
            matfile.write("{:.6f} {:.6f} {:.6f} {:.6f}\n".format(round(mat.Ambient[0],6),round(mat.Ambient[1],6),round(mat.Ambient[2],6),round(mat.Ambient[3],6)))
            matfile.write("{:.6f} {:.6f} {:.6f} {:.6f}\n".format(round(mat.Diffuse[0],6),round(mat.Diffuse[1],6),round(mat.Diffuse[2],6),round(mat.Diffuse[3],6)))
            matfile.write("{:.6f} {:.6f} {:.6f} {:.6f}\n".format(round(mat.Specular[0],6),round(mat.Specular[1],6),round(mat.Specular[2],6),round(mat.Specular[3],6)))
            matfile.write("{:.6f} {:.6f} {:.6f} {:.6f}\n".format(round(mat.Emissive[0],6),round(mat.Emissive[1],6),round(mat.Emissive[2],6),round(mat.Emissive[3],6)))
            matfile.write("{:.6f}\n".format(round(mat.Shininess)))
            matfile.write("1.000000\n")
            matfile.write("\"{}\"\n".format(mat.ColorMap))
            matfile.write("\"{}\"\n".format(mat.AlphaMap))
        if self.separate_materials:
            matfile.close()
        # Write out bones and animation
        # Only one animation can be stored per file, other animations need their own files
        animFiles = 0
        if self.separate_animations:
            f.write("Bones: 0\n")
            animfile = open("{} anim.{}".format(self.filepath[:extIdx], self.filepath[extIdx+1:]), 'w')
        else:
            animfile = f
        for anim in animations:
            animfile.write("Bones: {}\n".format(len(anim)))
            for bone in anim:
                animfile.write("\"{}\"\n".format(bone.Name))
                animfile.write("\"{}\"\n".format(bone.Parent))
                animfile.write("{} {:.6f} {:.6f} {:.6f} {:.6f} {:.6f} {:.6f}\n".format(
                                    bone.Flags,
                                    round(bone.IdlePos[0], 6),
                                    round(bone.IdlePos[1], 6),
                                    round(bone.IdlePos[2], 6),
                                    round(bone.IdleRot[0], 6),
                                    round(bone.IdleRot[1], 6),
                                    round(bone.IdleRot[2], 6)))
                if self.export_animations:
                    animfile.write("{}\n".format(len(bone.PosFrames)))
                    for pos in bone.PosFrames:
                        animfile.write("{:.6f} {:.6f} {:.6f} {:.6f}\n".format(round(pos.Time, 6),round(pos.X, 6),round(pos.Y,6),round(pos.Z,6)))
                    animfile.write("{}\n".format(len(bone.RotFrames)))
                    for rot in bone.RotFrames:
                        animfile.write("{:.6f} {:.6f} {:.6f} {:.6f}\n".format(round(rot.Time, 6),round(rot.X, 6),round(rot.Y,6),round(rot.Z,6)))
                else:
                    animfile.write("1\n1 0 0 0\n1\n1 0 0 0\n")
            animFiles += 1
            # Do not close the original file handle
            if self.separate_animations or animFiles > 1:
                animfile.close()
            if animFiles < len(animations):
                animfile = open("{} anim {}.{}".format(self.filepath[:extIdx], animFiles, self.filepath[extIdx+1:]), 'w')
        # Boilerplate comments at the end
        f.write("GroupComments: 0\nMaterialComments: 0\nBoneComments: 0\nModelComment: 0\n")
        f.close()
        return {'FINISHED'}

    def invoke(self, context, event):
        if not self.filepath:
            blend_filepath = context.blend_data.filepath
            if not blend_filepath:
                blend_filepath = "UNKNOWN"
            else:
                blend_filepath = path.splitext(blend_filepath)[0]
            self.filepath = blend_filepath + self.filename_ext
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

def menu_func_export(self, context):
    self.layout.operator(ExportMs3dascii.bl_idname, text="MS3DASCII (.txt)")

def register():
    bpy.utils.register_class(ExportMs3dascii)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    bpy.utils.unregister_class(ExportMs3dascii)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
    bpy.ops.export_ms3dascii.scene('INVOKE_DEFAULT')