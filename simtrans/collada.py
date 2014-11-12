# -*- coding:utf-8 -*-

"""
Reader and writer for collada format
"""

from __future__ import absolute_import
from . import model
import warnings
with warnings.catch_warnings():
    warnings.simplefilter('ignore')
    from .thirdparty import transformations as tf
import os
import collada
import numpy
import uuid


class ColladaReader(object):
    '''
    Collada reader class
    '''
    def __init__(self):
        self._basepath = None
        self._assethandler = None
        self._materials = {}

    def read(self, f, assethandler=None):
        '''
        Read collada model data given the file path

        >>> r = ColladaReader()
        >>> m = r.read('/opt/ros/indigo/share/atlas_description/meshes/head.dae')
        '''
        self._basepath = os.path.dirname(f)
        self._assethandler = assethandler
        d = collada.Collada(f)
        for m in d.materials:
            self._materials[m.id] = m
        m = model.MeshTransformData()
        m.children = []
        for n in d.scene.nodes:
            cm = self.convertchild(n)
            if cm is not None:
                m.children.append(cm)
        return m

    def convertchild(self, d):
        m = None
        if type(d) == collada.scene.Node:
            m = model.MeshTransformData()
            m.matrix = d.matrix
            m.children = []
            for c in d.children:
                m.children.append(self.convertchild(c))
        elif type(d) == collada.scene.GeometryNode:
            m = model.MeshTransformData()
            for p in d.geometry.primitives:
                sm = model.MeshData()
                sm.vertex = p.vertex
                sm.vertex_index = p.vertex_index
                if p.normal.size > 0:
                    sm.normal = p.normal
                    sm.normal_index = p.normal_index
                if len(p.texcoordset) > 0:
                    sm.uvmap = p.texcoordset[0]
                    sm.uvmap_index = p.texcoord_indexset[0]
                try:
                    for pr in self._materials[p.material].effect.params:
                        if type(pr) == collada.material.Surface:
                            fname = os.path.abspath(os.path.join(self._basepath, pr.image.path))
                            if self._assethandler:
                                sm.image = self._assethandler(fname)
                            else:
                                sm.image = fname
                except KeyError:
                    pass
                m.children.append(sm)
        return m


class ColladaWriter(object):
    '''
    Collada writer class
    '''
    def __init__(self):
        self._mesh = None
        self._matnode = None

    def write(self, m, f):
        '''
        Write simulation model in collada format
        '''
        # we use pycollada to generate the dae file
        self._mesh = collada.Collada()

        # create effect and material
        effect = collada.material.Effect("effect0", [], "phong", diffuse=(1,0,0), specular=(0,1,0))
        mat = collada.material.Material("material0", "mymaterial", effect)
        self._mesh.effects.append(effect)
        self._mesh.materials.append(mat)
        self._matnode = collada.scene.MaterialNode("materialref", mat, inputs=[])

        # convert shapes recursively
        node = collada.scene.Node("root", children=[self.convertchild(m.data)])

        # create scene graph
        myscene = collada.scene.Scene("myscene", [node])
        self._mesh.scenes.append(myscene)
        self._mesh.scene = myscene
        self._mesh.write(f)

    def convertchild(self, m):
        if type(m) == model.MeshTransformData:
            children = []
            name = 'node-' + str(uuid.uuid1()).replace('-', '')
            for c in m.children:
                cn = self.convertchild(c)
                if cn:
                    children.append(cn)
            node = collada.scene.Node(name, children=children)
            return node
        elif type(m) == model.MeshData:
            name = 'shape-' + str(uuid.uuid1()).replace('-', '')
            vertexname = name + '-vertex'
            normalname = name + '-normal'
            sources = []
            input_list = collada.source.InputList()
            sources.append(collada.source.FloatSource(vertexname, m.vertex.reshape(1, m.vertex.size), ('X', 'Y', 'Z')))
            indices = m.vertex_index.reshape(1, m.vertex_index.size)
            input_list.addInput(0, 'VERTEX', '#' + vertexname)
            if m.normal:
                sources.append(collada.source.FloatSource(normalname, m.normal.reshape(1, m.normal.size), ('X', 'Y', 'Z')))
                indices = numpy.vstack([indices, m.normal_index.reshape(1, m.normal_index.size)])
                input_list.addInput(1, 'NORMAL', '#' + normalname)
            geom = collada.geometry.Geometry(self._mesh, 'geometry0', name, sources)
            # create triangles
            triset = geom.createTriangleSet(indices.T.reshape(1, indices.size), input_list, 'materialref')
            geom.primitives.append(triset)
            self._mesh.geometries.append(geom)
            node = collada.scene.GeometryNode(geom, [self._matnode])
            return node
        return None
