// skyforge_core.cpp
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <vector>
#include <unordered_map>
#include <cstdint>
#include <queue>
#include <cmath>

// ----------------------------
// Utils
// ----------------------------
static inline uint64_t pack_edge(int src, int dst)
{
    return (uint64_t(uint32_t(src)) << 32) | uint32_t(dst);
}

struct HalfEdgeMeshData
{
    int num_points = 0;
    std::vector<int> src, dst, next, prev, twin, equiv_next, prim;
    std::unordered_map<uint64_t, int> edge_map; // (src,dst)->he (primary)

    void clear()
    {
        num_points = 0;
        src.clear(); dst.clear(); next.clear(); prev.clear();
        twin.clear(); equiv_next.clear(); prim.clear();
        edge_map.clear();
    }
};

typedef struct {
    PyObject_HEAD
        HalfEdgeMeshData* m;
} PyHalfEdgeMesh;

static inline int clamp_he(const PyHalfEdgeMesh* self, int he)
{
    if (!self || !self->m) return -1;
    const int nhe = (int)self->m->src.size();
    if (he < 0 || he >= nhe) return -1;
    return he;
}

// ----------------------------
// Build from faces: list[list[int]]
// ----------------------------
static int build_from_faces(HalfEdgeMeshData& M, PyObject* faces_obj, int num_points)
{
    if (!PyList_Check(faces_obj))
    {
        PyErr_SetString(PyExc_TypeError, "faces must be a list of faces (list[list[int]])");
        return 0;
    }
    if (num_points < 0)
    {
        PyErr_SetString(PyExc_ValueError, "num_points must be >= 0");
        return 0;
    }

    M.clear();
    M.num_points = num_points;

    std::unordered_map<uint64_t, std::vector<int>> hedges_of;
    hedges_of.reserve((size_t)PyList_Size(faces_obj) * 4);

    const Py_ssize_t nfaces = PyList_Size(faces_obj);
    for (Py_ssize_t fi = 0; fi < nfaces; ++fi)
    {
        PyObject* face_obj = PyList_GetItem(faces_obj, fi); // borrowed
        if (!PyList_Check(face_obj))
        {
            PyErr_SetString(PyExc_TypeError, "each face must be a list of ints");
            return 0;
        }

        const Py_ssize_t nv = PyList_Size(face_obj);
        if (nv < 3) continue;

        std::vector<int> pts;
        pts.reserve((size_t)nv);

        for (Py_ssize_t i = 0; i < nv; ++i)
        {
            PyObject* item = PyList_GetItem(face_obj, i); // borrowed
            if (!PyLong_Check(item))
            {
                PyErr_SetString(PyExc_TypeError, "face vertex ids must be int");
                return 0;
            }
            long p = PyLong_AsLong(item);
            if (p < 0 || p >= num_points)
            {
                PyErr_SetString(PyExc_ValueError, "face contains point index out of range");
                return 0;
            }
            pts.push_back((int)p);
        }

        const int base = (int)M.src.size();
        M.src.resize(M.src.size() + (size_t)nv);
        M.dst.resize(M.dst.size() + (size_t)nv);
        M.next.resize(M.next.size() + (size_t)nv);
        M.prev.resize(M.prev.size() + (size_t)nv);
        M.prim.resize(M.prim.size() + (size_t)nv);

        for (int i = 0; i < (int)nv; ++i)
        {
            const int a = pts[(size_t)i];
            const int b = pts[(size_t)((i + 1) % (int)nv)];
            const int he = base + i;

            M.src[(size_t)he] = a;
            M.dst[(size_t)he] = b;

            M.next[(size_t)he] = base + ((i + 1) % (int)nv);
            M.prev[(size_t)he] = base + ((i - 1 + (int)nv) % (int)nv);
            M.prim[(size_t)he] = (int)fi;

            hedges_of[pack_edge(a, b)].push_back(he);
        }
    }

    const int nhe = (int)M.src.size();
    M.equiv_next.assign((size_t)nhe, -1);
    M.twin.assign((size_t)nhe, -1);

    for (auto& kv : hedges_of)
    {
        auto& L = kv.second;
        const int m = (int)L.size();
        if (m <= 1) continue;

        for (int i = 0; i < m; ++i)
        {
            const int he = L[(size_t)i];
            const int heN = L[(size_t)((i + 1) % m)];
            M.equiv_next[(size_t)he] = heN;
        }
    }

    M.edge_map.reserve(hedges_of.size());
    for (auto& kv : hedges_of)
    {
        auto& L = kv.second;
        if (!L.empty())
            M.edge_map.emplace(kv.first, L[0]);
    }

    for (int he = 0; he < nhe; ++he)
    {
        const int a = M.src[(size_t)he];
        const int b = M.dst[(size_t)he];
        auto it = hedges_of.find(pack_edge(b, a));
        if (it != hedges_of.end() && !it->second.empty())
            M.twin[(size_t)he] = it->second[0];
    }

    return 1;
}

// ----------------------------
// Build from compact arrays:
//   vtx_points: sequence[int] length = vertexcount
//   prim_counts: sequence[int] length = primitivecount (vertex count per prim)
// ----------------------------
static int build_from_compact(
    HalfEdgeMeshData& M,
    PyObject* vtx_points_obj,
    PyObject* prim_counts_obj,
    int num_points)
{
    if (num_points < 0)
    {
        PyErr_SetString(PyExc_ValueError, "num_points must be >= 0");
        return 0;
    }

    PyObject* vtx_seq = PySequence_Fast(vtx_points_obj, "vtx_points must be a sequence of ints");
    if (!vtx_seq) return 0;

    PyObject* cnt_seq = PySequence_Fast(prim_counts_obj, "prim_counts must be a sequence of ints");
    if (!cnt_seq) { Py_DECREF(vtx_seq); return 0; }

    const Py_ssize_t vtx_n = PySequence_Fast_GET_SIZE(vtx_seq);
    const Py_ssize_t prim_n = PySequence_Fast_GET_SIZE(cnt_seq);

    PyObject** vtx_items = PySequence_Fast_ITEMS(vtx_seq);
    PyObject** cnt_items = PySequence_Fast_ITEMS(cnt_seq);

    M.clear();
    M.num_points = num_points;

    std::unordered_map<uint64_t, std::vector<int>> hedges_of;
    hedges_of.reserve((size_t)prim_n * 4);

    Py_ssize_t vcursor = 0;

    for (Py_ssize_t pi = 0; pi < prim_n; ++pi)
    {
        PyObject* cobj = cnt_items[pi];
        if (!PyLong_Check(cobj))
        {
            PyErr_SetString(PyExc_TypeError, "prim_counts must contain ints");
            Py_DECREF(cnt_seq);
            Py_DECREF(vtx_seq);
            return 0;
        }

        long nvL = PyLong_AsLong(cobj);
        if (nvL < 0)
        {
            PyErr_SetString(PyExc_ValueError, "prim_counts contains negative count");
            Py_DECREF(cnt_seq);
            Py_DECREF(vtx_seq);
            return 0;
        }

        if (vcursor + nvL > vtx_n)
        {
            PyErr_SetString(PyExc_ValueError, "prim_counts sum exceeds vtx_points length");
            Py_DECREF(cnt_seq);
            Py_DECREF(vtx_seq);
            return 0;
        }

        if (nvL < 3)
        {
            vcursor += nvL;
            continue;
        }

        const int nv = (int)nvL;

        const int base = (int)M.src.size();
        M.src.resize(M.src.size() + (size_t)nv);
        M.dst.resize(M.dst.size() + (size_t)nv);
        M.next.resize(M.next.size() + (size_t)nv);
        M.prev.resize(M.prev.size() + (size_t)nv);
        M.prim.resize(M.prim.size() + (size_t)nv);

        for (int i = 0; i < nv; ++i)
        {
            PyObject* pobjA = vtx_items[vcursor + i];
            PyObject* pobjB = vtx_items[vcursor + ((i + 1) % nv)];

            if (!PyLong_Check(pobjA) || !PyLong_Check(pobjB))
            {
                PyErr_SetString(PyExc_TypeError, "vtx_points must contain ints");
                Py_DECREF(cnt_seq);
                Py_DECREF(vtx_seq);
                return 0;
            }

            long aL = PyLong_AsLong(pobjA);
            long bL = PyLong_AsLong(pobjB);

            if (aL < 0 || aL >= num_points || bL < 0 || bL >= num_points)
            {
                PyErr_SetString(PyExc_ValueError, "vtx_points contains point index out of range");
                Py_DECREF(cnt_seq);
                Py_DECREF(vtx_seq);
                return 0;
            }

            const int a = (int)aL;
            const int b = (int)bL;
            const int he = base + i;

            M.src[(size_t)he] = a;
            M.dst[(size_t)he] = b;

            M.next[(size_t)he] = base + ((i + 1) % nv);
            M.prev[(size_t)he] = base + ((i - 1 + nv) % nv);
            M.prim[(size_t)he] = (int)pi;

            hedges_of[pack_edge(a, b)].push_back(he);
        }

        vcursor += nv;
    }

    const int nhe = (int)M.src.size();
    M.equiv_next.assign((size_t)nhe, -1);
    M.twin.assign((size_t)nhe, -1);

    for (auto& kv : hedges_of)
    {
        auto& L = kv.second;
        const int m = (int)L.size();
        if (m <= 1) continue;

        for (int i = 0; i < m; ++i)
        {
            const int he = L[(size_t)i];
            const int heN = L[(size_t)((i + 1) % m)];
            M.equiv_next[(size_t)he] = heN;
        }
    }

    M.edge_map.reserve(hedges_of.size());
    for (auto& kv : hedges_of)
    {
        auto& L = kv.second;
        if (!L.empty())
            M.edge_map.emplace(kv.first, L[0]);
    }

    for (int he = 0; he < nhe; ++he)
    {
        const int a = M.src[(size_t)he];
        const int b = M.dst[(size_t)he];
        auto it = hedges_of.find(pack_edge(b, a));
        if (it != hedges_of.end() && !it->second.empty())
            M.twin[(size_t)he] = it->second[0];
    }

    Py_DECREF(cnt_seq);
    Py_DECREF(vtx_seq);
    return 1;
}

// ----------------------------
// HalfEdgeMesh Python Type
// ----------------------------
static void HalfEdgeMesh_dealloc(PyHalfEdgeMesh* self)
{
    delete self->m;
    self->m = nullptr;
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject* HalfEdgeMesh_new(PyTypeObject* type, PyObject* args, PyObject* kwds)
{
    (void)args; (void)kwds;
    PyHalfEdgeMesh* self = (PyHalfEdgeMesh*)type->tp_alloc(type, 0);
    if (!self) return nullptr;
    self->m = new HalfEdgeMeshData();
    return (PyObject*)self;
}

// Supports:
//   HalfEdgeMesh()                      -> empty
//   HalfEdgeMesh(faces, num_points)     -> build from faces
static int HalfEdgeMesh_init(PyHalfEdgeMesh* self, PyObject* args, PyObject* kwds)
{
    (void)kwds;

    if (!self->m) self->m = new HalfEdgeMeshData();

    if (PyTuple_Size(args) == 0)
    {
        self->m->clear();
        return 0;
    }

    PyObject* faces_obj = nullptr;
    int num_points = 0;

    if (!PyArg_ParseTuple(args, "Oi", &faces_obj, &num_points))
        return -1;

    if (!build_from_faces(*self->m, faces_obj, num_points))
        return -1;

    return 0;
}

static PyObject* HalfEdgeMesh_rebuild(PyHalfEdgeMesh* self, PyObject* args)
{
    PyObject* faces_obj = nullptr;
    int num_points = 0;

    if (!PyArg_ParseTuple(args, "Oi", &faces_obj, &num_points))
        return nullptr;

    if (!self->m) self->m = new HalfEdgeMeshData();

    if (!build_from_faces(*self->m, faces_obj, num_points))
        return nullptr;

    Py_RETURN_NONE;
}

// rebuild_compact(vtx_points, prim_counts, num_points)
static PyObject* HalfEdgeMesh_rebuild_compact(PyHalfEdgeMesh* self, PyObject* args)
{
    PyObject* vtx_points_obj = nullptr;
    PyObject* prim_counts_obj = nullptr;
    int num_points = 0;

    if (!PyArg_ParseTuple(args, "OOi", &vtx_points_obj, &prim_counts_obj, &num_points))
        return nullptr;

    if (!self->m) self->m = new HalfEdgeMeshData();

    if (!build_from_compact(*self->m, vtx_points_obj, prim_counts_obj, num_points))
        return nullptr;

    Py_RETURN_NONE;
}

static PyObject* HalfEdgeMesh_clear(PyHalfEdgeMesh* self, PyObject* /*args*/)
{
    if (self->m) self->m->clear();
    Py_RETURN_NONE;
}

static PyObject* HalfEdgeMesh_pt_hedge(PyHalfEdgeMesh* self, PyObject* args)
{
    int a, b;
    if (!PyArg_ParseTuple(args, "ii", &a, &b))
        return nullptr;

    auto it = self->m->edge_map.find(pack_edge(a, b));
    if (it == self->m->edge_map.end())
        return PyLong_FromLong(-1);

    return PyLong_FromLong((long)it->second);
}

static PyObject* HalfEdgeMesh_next(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->next[(size_t)he]);
}

static PyObject* HalfEdgeMesh_prev(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->prev[(size_t)he]);
}

static PyObject* HalfEdgeMesh_twin(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->twin[(size_t)he]);
}

static PyObject* HalfEdgeMesh_equiv_next(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->equiv_next[(size_t)he]);
}

static PyObject* HalfEdgeMesh_src(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->src[(size_t)he]);
}

static PyObject* HalfEdgeMesh_dst(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->dst[(size_t)he]);
}

// prim index of half-edge owner face, or -1
static PyObject* HalfEdgeMesh_hedge_prim(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0) return PyLong_FromLong(-1);

    return PyLong_FromLong((long)self->m->prim[(size_t)he]);
}

// (left_prim, right_prim) around undirected edge represented by he.
// right_prim is the twin owner face, or -1 on boundary.
static PyObject* HalfEdgeMesh_hedge_prims(PyHalfEdgeMesh* self, PyObject* args)
{
    int he;
    if (!PyArg_ParseTuple(args, "i", &he))
        return nullptr;

    he = clamp_he(self, he);
    if (he < 0)
        return Py_BuildValue("(ii)", -1, -1);

    int left = self->m->prim[(size_t)he];
    int right = -1;
    int ht = self->m->twin[(size_t)he];
    if (ht >= 0)
        right = self->m->prim[(size_t)ht];

    return Py_BuildValue("(ii)", left, right);
}

// ---------------------------------------------------------
// Loop helpers (FACE / VERTEX)
// ---------------------------------------------------------
static PyObject* HalfEdgeMesh_face_loop(PyHalfEdgeMesh* self, PyObject* args)
{
    int he0;
    int max_steps = 100000;
    if (!PyArg_ParseTuple(args, "i|i", &he0, &max_steps))
        return nullptr;

    he0 = clamp_he(self, he0);
    if (he0 < 0) return PyList_New(0);

    PyObject* out = PyList_New(0);
    int he = he0;

    for (int i = 0; i < max_steps; ++i)
    {
        PyList_Append(out, PyLong_FromLong(he));
        int hn = self->m->next[(size_t)he];
        if (hn < 0) break;
        if (hn == he0) break;
        he = hn;
    }
    return out;
}

// one-ring around src vertex: he -> twin(prev(he)) -> ...
static PyObject* HalfEdgeMesh_vertex_ring_src(PyHalfEdgeMesh* self, PyObject* args)
{
    int he0;
    int max_steps = 100000;
    if (!PyArg_ParseTuple(args, "i|i", &he0, &max_steps))
        return nullptr;

    he0 = clamp_he(self, he0);
    if (he0 < 0) return PyList_New(0);

    PyObject* out = PyList_New(0);
    int he = he0;

    for (int i = 0; i < max_steps; ++i)
    {
        PyList_Append(out, PyLong_FromLong(he));

        int hp = self->m->prev[(size_t)he];
        if (hp < 0) break;

        int ht = self->m->twin[(size_t)hp];
        if (ht < 0) break; // boundary

        if (ht == he0) break;
        he = ht;
    }
    return out;
}

// one-ring around dst vertex: he -> prev(twin(he)) -> ...
static PyObject* HalfEdgeMesh_vertex_ring_dst(PyHalfEdgeMesh* self, PyObject* args)
{
    int he0;
    int max_steps = 100000;
    if (!PyArg_ParseTuple(args, "i|i", &he0, &max_steps))
        return nullptr;

    he0 = clamp_he(self, he0);
    if (he0 < 0) return PyList_New(0);

    PyObject* out = PyList_New(0);
    int he = he0;

    for (int i = 0; i < max_steps; ++i)
    {
        PyList_Append(out, PyLong_FromLong(he));

        int ht = self->m->twin[(size_t)he];
        if (ht < 0) break; // boundary

        int hn = self->m->prev[(size_t)ht];
        if (hn < 0) break;

        if (hn == he0) break;
        he = hn;
    }
    return out;
}

// ---------------------------------------------------------
// EDGE LOOP (quad strip): opposite-in-face then cross twin
// ---------------------------------------------------------
static inline int face_degree(const HalfEdgeMeshData& M, int he0, int max_steps)
{
    if (he0 < 0) return 0;
    int he = he0;
    for (int i = 1; i <= max_steps; ++i)
    {
        int hn = M.next[(size_t)he];
        if (hn < 0) return 0;
        if (hn == he0) return i;
        he = hn;
    }
    return 0;
}

static inline int face_opposite_quad(const HalfEdgeMeshData& M, int he)
{
    int a = M.next[(size_t)he];
    if (a < 0) return -1;
    int b = M.next[(size_t)a];
    return b;
}

// roll = next( twin( next(he) ) )
static inline int roll_he(const HalfEdgeMeshData& M, int he)
{
    if (he < 0) return -1;
    int hn = M.next[(size_t)he];
    if (hn < 0) return -1;
    int ht = M.twin[(size_t)hn];
    if (ht < 0) return -1;
    return M.next[(size_t)ht];
}

// right turn around dst(he) while keeping continuity at dst vertex:
// right = twin( prev( twin(he) ) )
static inline int turn_right_dst(const HalfEdgeMeshData& M, int he)
{
    if (he < 0) return -1;
    int ht = M.twin[(size_t)he];
    if (ht < 0) return -1;
    int hp = M.prev[(size_t)ht];
    if (hp < 0) return -1;
    int out = M.twin[(size_t)hp];
    return out;
}

// Unique edge valence at a point (counts unique neighbors from outgoing hedges).
// In manifold polygon meshes this matches the point valence.
static inline int point_valence_unique(const HalfEdgeMeshData& M, int p)
{
    if (p < 0) return 0;
    std::unordered_map<int, int> nbrs;
    nbrs.reserve(16);

    const int nhe = (int)M.src.size();
    for (int he = 0; he < nhe; ++he)
    {
        if (M.src[(size_t)he] != p) continue;
        int q = M.dst[(size_t)he];
        if (q < 0) continue;
        nbrs.emplace(q, 1);
    }
    return (int)nbrs.size();
}

static PyObject* HalfEdgeMesh_edge_loop_quad(PyHalfEdgeMesh* self, PyObject* args)
{
    int he0;
    int max_steps = 10000;
    int both_dir = 1;
    if (!PyArg_ParseTuple(args, "i|ii", &he0, &max_steps, &both_dir))
        return nullptr;

    he0 = clamp_he(self, he0);
    if (he0 < 0) return PyList_New(0);

    auto& M = *self->m;

    auto walk = [&](int seed, PyObject* out, std::unordered_map<int, int>& seen) -> void
        {
            int he = seed;
            for (int step = 0; step < max_steps; ++step)
            {
                if (he < 0) break;
                if (seen.find(he) != seen.end()) break;
                seen.emplace(he, 1);

                PyList_Append(out, PyLong_FromLong(he));

                int deg = face_degree(M, he, 64);
                if (deg != 4) break;

                // Continue only through regular quad valence.
                // Stop on extraordinary vertices/boundaries to avoid ambiguity.
                int vd = point_valence_unique(M, M.dst[(size_t)he]);
                if (vd != 4) break;

                int opp = face_opposite_quad(M, he);
                if (opp < 0) break;

                int ht = M.twin[(size_t)opp];
                if (ht < 0) break;

                he = ht;
            }
        };

    PyObject* forward = PyList_New(0);
    std::unordered_map<int, int> seen_f;
    seen_f.reserve(256);
    walk(he0, forward, seen_f);

    if (!both_dir)
        return forward;

    int back_seed = M.twin[(size_t)he0];
    if (back_seed < 0)
        return forward;

    PyObject* backward = PyList_New(0);
    std::unordered_map<int, int> seen_b;
    seen_b.reserve(256);
    walk(back_seed, backward, seen_b);

    PyObject* out = PyList_New(0);

    Py_ssize_t nb = PyList_Size(backward);
    for (Py_ssize_t i = nb - 1; i >= 0; --i)
    {
        PyObject* item = PyList_GetItem(backward, i); // borrowed
        long v = PyLong_AsLong(item);
        if ((int)v == he0) continue;
        PyList_Append(out, item);
        if (i == 0) break;
    }

    Py_ssize_t nf = PyList_Size(forward);
    for (Py_ssize_t i = 0; i < nf; ++i)
    {
        PyObject* item = PyList_GetItem(forward, i); // borrowed
        PyList_Append(out, item);
    }

    Py_DECREF(forward);
    Py_DECREF(backward);
    return out;
}

// EDGE LOOP (roll-based): he = roll_he(he)
static PyObject* HalfEdgeMesh_edge_loop_roll(PyHalfEdgeMesh* self, PyObject* args)
{
    int he0;
    int max_steps = 10000;
    int both_dir = 1;
    if (!PyArg_ParseTuple(args, "i|ii", &he0, &max_steps, &both_dir))
        return nullptr;

    he0 = clamp_he(self, he0);
    if (he0 < 0) return PyList_New(0);

    auto& M = *self->m;

    auto walk = [&](int seed, PyObject* out, std::unordered_map<int, int>& seen) -> void
        {
            int he = seed;
            for (int step = 0; step < max_steps; ++step)
            {
                if (he < 0) break;
                if (seen.find(he) != seen.end()) break;
                seen.emplace(he, 1);

                PyList_Append(out, PyLong_FromLong(he));

                int deg = face_degree(M, he, 64);
                if (deg != 4) break;

                // Continue only through regular quad valence.
                int vd = point_valence_unique(M, M.dst[(size_t)he]);
                if (vd != 4) break;

                he = roll_he(M, he);
            }
        };

    PyObject* forward = PyList_New(0);
    std::unordered_map<int, int> seen_f;
    seen_f.reserve(256);
    walk(he0, forward, seen_f);

    if (!both_dir)
        return forward;

    int back_seed = M.twin[(size_t)he0];
    if (back_seed < 0)
        return forward;

    PyObject* backward = PyList_New(0);
    std::unordered_map<int, int> seen_b;
    seen_b.reserve(256);
    walk(back_seed, backward, seen_b);

    PyObject* out = PyList_New(0);

    Py_ssize_t nb = PyList_Size(backward);
    for (Py_ssize_t i = nb - 1; i >= 0; --i)
    {
        PyObject* item = PyList_GetItem(backward, i); // borrowed
        long v = PyLong_AsLong(item);
        if ((int)v == he0) continue;
        PyList_Append(out, item);
        if (i == 0) break;
    }

    Py_ssize_t nf = PyList_Size(forward);
    for (Py_ssize_t i = 0; i < nf; ++i)
    {
        PyObject* item = PyList_GetItem(forward, i); // borrowed
        PyList_Append(out, item);
    }

    Py_DECREF(forward);
    Py_DECREF(backward);
    return out;
}

// =========================================================
// A* / Dijkstra with TURN COST
// State = (prev_he, cur_he) because turn cost depends on prev.
// If P=None => heuristic=0 => Dijkstra.
// If P is provided (len=3*num_points) => euclid heuristic (A*).
// =========================================================
static inline uint64_t pack_state(int prev_he, int cur_he)
{
    return (uint64_t(uint32_t(prev_he)) << 32) | uint32_t(cur_he);
}

static inline bool parse_positions(PyObject* P_obj, int num_points, std::vector<float>& P)
{
    P.clear();
    if (!P_obj || P_obj == Py_None) return true;

    PyObject* seq = PySequence_Fast(P_obj, "P must be a sequence of floats (len = 3*num_points)");
    if (!seq) return false;

    const Py_ssize_t n = PySequence_Fast_GET_SIZE(seq);
    if (n != (Py_ssize_t)num_points * 3)
    {
        Py_DECREF(seq);
        PyErr_SetString(PyExc_ValueError, "P length must be exactly 3*num_points");
        return false;
    }

    P.resize((size_t)n);
    PyObject** items = PySequence_Fast_ITEMS(seq);
    for (Py_ssize_t i = 0; i < n; ++i)
    {
        PyObject* it = items[i];
        double v = 0.0;

        if (PyFloat_Check(it)) v = PyFloat_AsDouble(it);
        else if (PyLong_Check(it)) v = (double)PyLong_AsLong(it);
        else
        {
            Py_DECREF(seq);
            PyErr_SetString(PyExc_TypeError, "P must contain only float/int values");
            return false;
        }

        if (PyErr_Occurred())
        {
            Py_DECREF(seq);
            PyErr_SetString(PyExc_TypeError, "P must contain only float/int values");
            return false;
        }

        P[(size_t)i] = (float)v;
    }

    Py_DECREF(seq);
    return true;
}

static inline float heur_euclid_dst_to_dst(
    const HalfEdgeMeshData& M,
    const std::vector<float>& P,
    int cur_he,
    int goal_he)
{
    if (P.empty()) return 0.0f;
    if (cur_he < 0 || goal_he < 0) return 0.0f;

    int pc = M.dst[(size_t)cur_he];
    int pg = M.dst[(size_t)goal_he];
    if (pc < 0 || pg < 0) return 0.0f;

    const float cx = P[(size_t)pc * 3 + 0];
    const float cy = P[(size_t)pc * 3 + 1];
    const float cz = P[(size_t)pc * 3 + 2];

    const float gx = P[(size_t)pg * 3 + 0];
    const float gy = P[(size_t)pg * 3 + 1];
    const float gz = P[(size_t)pg * 3 + 2];

    const float dx = cx - gx;
    const float dy = cy - gy;
    const float dz = cz - gz;
    return (float)std::sqrt(dx * dx + dy * dy + dz * dz);
}

static inline float heur_euclid_to_goal_or_twin(
    const HalfEdgeMeshData& M,
    const std::vector<float>& P,
    int cur_he,
    int goal_he,
    int goal_twin_he)
{
    float h0 = heur_euclid_dst_to_dst(M, P, cur_he, goal_he);
    if (goal_twin_he < 0 || goal_twin_he == goal_he) return h0;
    float h1 = heur_euclid_dst_to_dst(M, P, cur_he, goal_twin_he);
    return (h1 < h0) ? h1 : h0;
}

// Turn model (continuity at dst):
// straight = roll(cur)
// left     = next(cur)
// right    = twin(prev(twin(cur)))
// u-turn   = twin(cur) (penalized)
static inline float step_cost_turn_topo(
    const HalfEdgeMeshData& M,
    int /*prev_he*/,
    int cur_he,
    int nxt_he,
    float w_turn,
    float backtrack_pen)
{
    // U-turn (inverse)
    int inv = M.twin[(size_t)cur_he];
    if (nxt_he == inv) return backtrack_pen;

    // Straight
    int straight = roll_he(M, cur_he);
    if (nxt_he == straight) return 0.0f;

    // Left / Right are turns
    int left = M.next[(size_t)cur_he];
    if (nxt_he == left) return w_turn;

    int right = turn_right_dst(M, cur_he);
    if (nxt_he == right) return w_turn;

    return w_turn;
}

struct OpenItem
{
    float f;
    float g;
    int prev;
    int cur;
    bool operator<(const OpenItem& o) const { return f > o.f; }
};

// astar_turn(start_he, goal_he, max_visits=200000, w_step=1.0, w_turn=5.0,
//            backtrack_pen=1e6, require_quads=1, P=None, both_dir_start=1, both_dir_goal=1) -> list[int]
static PyObject* HalfEdgeMesh_astar_turn(PyHalfEdgeMesh* self, PyObject* args, PyObject* kwds)
{
    static const char* kwnames[] = {
        "start_he","goal_he","max_visits","w_step","w_turn","backtrack_pen","require_quads","P","both_dir_start","both_dir_goal", NULL
    };

    int start_he = -1;
    int goal_he = -1;
    int max_visits = 200000;
    float w_step = 1.0f;
    float w_turn = 5.0f;
    float backtrack_pen = 1000000.0f;
    int require_quads = 1;
    PyObject* P_obj = Py_None;
    int both_dir_start = 1;
    int both_dir_goal = 1;

    if (!PyArg_ParseTupleAndKeywords(
        args, kwds, "ii|ifffiOii", (char**)kwnames,
        &start_he, &goal_he, &max_visits, &w_step, &w_turn, &backtrack_pen, &require_quads, &P_obj, &both_dir_start, &both_dir_goal))
    {
        return nullptr;
    }

    if (!self || !self->m) return PyList_New(0);
    auto& M = *self->m;

    start_he = clamp_he(self, start_he);
    goal_he = clamp_he(self, goal_he);
    if (start_he < 0 || goal_he < 0) return PyList_New(0);
    int goal_twin_he = -1;
    if (both_dir_goal)
    {
        int t = M.twin[(size_t)goal_he];
        if (t >= 0 && t != goal_he)
            goal_twin_he = t;
    }

    std::vector<float> P;
    if (!parse_positions(P_obj, M.num_points, P))
        return nullptr;

    std::unordered_map<uint64_t, float> dist;
    std::unordered_map<uint64_t, uint64_t> parent;
    dist.reserve(4096);
    parent.reserve(4096);

    std::priority_queue<OpenItem> open;

    uint64_t s0 = pack_state(-1, start_he);
    dist[s0] = 0.0f;
    parent[s0] = 0;

    float h0 = heur_euclid_to_goal_or_twin(M, P, start_he, goal_he, goal_twin_he);
    open.push({ h0, 0.0f, -1, start_he });

    if (both_dir_start)
    {
        int start_twin = M.twin[(size_t)start_he];
        if (start_twin >= 0 && start_twin != start_he)
        {
            uint64_t s1 = pack_state(-1, start_twin);
            dist[s1] = 0.0f;
            parent[s1] = 0;

            float h1 = heur_euclid_to_goal_or_twin(M, P, start_twin, goal_he, goal_twin_he);
            open.push({ h1, 0.0f, -1, start_twin });
        }
    }

    uint64_t best_goal_state = 0;
    int visits = 0;

    while (!open.empty() && visits < max_visits)
    {
        OpenItem it = open.top();
        open.pop();
        ++visits;

        uint64_t sk = pack_state(it.prev, it.cur);

        auto dit = dist.find(sk);
        if (dit == dist.end()) continue;
        float g_here = dit->second;

        // stale heap entry
        if (g_here != it.g) continue;

        if (it.cur == goal_he || (goal_twin_he >= 0 && it.cur == goal_twin_he))
        {
            best_goal_state = sk;
            break;
        }

        if (require_quads)
        {
            int deg = face_degree(M, it.cur, 64);
            if (deg != 4) continue;
        }

        // SUCCESSORS (continuous at dst):
        // straight: roll(cur)
        // left:     next(cur)
        // right:    twin(prev(twin(cur)))
        // u-turn:   twin(cur) (penalized)
        int succ[4];
        succ[0] = roll_he(M, it.cur);
        succ[1] = M.next[(size_t)it.cur];
        succ[2] = turn_right_dst(M, it.cur);
        succ[3] = M.twin[(size_t)it.cur];

        for (int si = 0; si < 4; ++si)
        {
            int nh = succ[si];
            if (nh < 0) continue;

            float base = w_step;
            float tpen = step_cost_turn_topo(M, it.prev, it.cur, nh, w_turn, backtrack_pen);
            float g2 = g_here + base + tpen;

            uint64_t nk = pack_state(it.cur, nh);

            auto found = dist.find(nk);
            if (found == dist.end() || g2 < found->second)
            {
                dist[nk] = g2;
                parent[nk] = sk;

                float h = heur_euclid_to_goal_or_twin(M, P, nh, goal_he, goal_twin_he);
                float f = g2 + h;
                open.push({ f, g2, it.cur, nh });
            }
        }
    }

    if (!best_goal_state)
        return PyList_New(0);

    // reconstruct (cur hedges)
    std::vector<int> rev;
    rev.reserve(256);

    uint64_t curk = best_goal_state;
    while (curk)
    {
        int cur_he = (int)uint32_t(curk);
        rev.push_back(cur_he);

        auto pit = parent.find(curk);
        if (pit == parent.end()) break;
        curk = pit->second;
        if (curk == 0) break;
    }

    PyObject* out = PyList_New(0);
    for (int i = (int)rev.size() - 1; i >= 0; --i)
        PyList_Append(out, PyLong_FromLong(rev[(size_t)i]));

    return out;
}

// ----------------------------
// Python methods table
// ----------------------------
static PyMethodDef HalfEdgeMesh_methods[] = {
    {"rebuild",         (PyCFunction)HalfEdgeMesh_rebuild,         METH_VARARGS, "rebuild(faces, num_points) -> None"},
    {"rebuild_compact", (PyCFunction)HalfEdgeMesh_rebuild_compact, METH_VARARGS, "rebuild_compact(vtx_points, prim_counts, num_points) -> None"},
    {"clear",           (PyCFunction)HalfEdgeMesh_clear,           METH_NOARGS,  "clear() -> None"},

    {"pt_hedge",    (PyCFunction)HalfEdgeMesh_pt_hedge,    METH_VARARGS, "pt_hedge(a,b)->he or -1"},
    {"next",        (PyCFunction)HalfEdgeMesh_next,        METH_VARARGS, "next(he)->he or -1"},
    {"prev",        (PyCFunction)HalfEdgeMesh_prev,        METH_VARARGS, "prev(he)->he or -1"},
    {"twin",        (PyCFunction)HalfEdgeMesh_twin,        METH_VARARGS, "twin(he)->he or -1"},
    {"equiv_next",  (PyCFunction)HalfEdgeMesh_equiv_next,  METH_VARARGS, "equiv_next(he)->he or -1"},
    {"src",         (PyCFunction)HalfEdgeMesh_src,         METH_VARARGS, "src(he)->point or -1"},
    {"dst",         (PyCFunction)HalfEdgeMesh_dst,         METH_VARARGS, "dst(he)->point or -1"},
    {"hedge_prim",  (PyCFunction)HalfEdgeMesh_hedge_prim,  METH_VARARGS, "hedge_prim(he)->prim or -1"},
    {"hedge_prims", (PyCFunction)HalfEdgeMesh_hedge_prims, METH_VARARGS, "hedge_prims(he)->(left_prim,right_prim)"},

    // loops (KEEP THEM)
    {"face_loop",        (PyCFunction)HalfEdgeMesh_face_loop,       METH_VARARGS, "face_loop(he[,max_steps])->list[int]"},
    {"vertex_ring_src",  (PyCFunction)HalfEdgeMesh_vertex_ring_src, METH_VARARGS, "vertex_ring_src(he[,max_steps])->list[int]"},
    {"vertex_ring_dst",  (PyCFunction)HalfEdgeMesh_vertex_ring_dst, METH_VARARGS, "vertex_ring_dst(he[,max_steps])->list[int]"},
    {"edge_loop_quad",   (PyCFunction)HalfEdgeMesh_edge_loop_quad,  METH_VARARGS, "edge_loop_quad(he[,max_steps=10000,both_dir=1])->list[int]"},
    {"edge_loop_roll",   (PyCFunction)HalfEdgeMesh_edge_loop_roll,  METH_VARARGS, "edge_loop_roll(he[,max_steps=10000,both_dir=1])->list[int] (roll=next(twin(next)))"},

    // pathfinding
    {"astar_turn", (PyCFunction)HalfEdgeMesh_astar_turn, METH_VARARGS | METH_KEYWORDS,
     "astar_turn(start_he, goal_he, max_visits=200000, w_step=1.0, w_turn=5.0, backtrack_pen=1e6, require_quads=1, P=None, both_dir_start=1, both_dir_goal=1)->list[int]"},

    {NULL, NULL, 0, NULL}
};

// IMPORTANT: initialize with PyTypeObject initializer macro, then set fields in init
static PyTypeObject HalfEdgeMeshType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

// ----------------------------
// Existing module functions (optional)
// ----------------------------
static PyObject* py_add(PyObject* /*self*/, PyObject* args)
{
    int a, b;
    if (!PyArg_ParseTuple(args, "ii", &a, &b))
        return nullptr;
    return PyLong_FromLong(a + b);
}

static PyMethodDef SkyforgeMethods[] = {
    {"add", py_add, METH_VARARGS, "Add two integers."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef skyforgemodule = {
    PyModuleDef_HEAD_INIT,
    "skyforge_core",
    NULL,
    -1,
    SkyforgeMethods
};

PyMODINIT_FUNC PyInit_skyforge_core(void)
{
    PyObject* m = PyModule_Create(&skyforgemodule);
    if (!m) return nullptr;

    // Fill type object fields (MSVC-safe)
    HalfEdgeMeshType.tp_name = "skyforge_core.HalfEdgeMesh";
    HalfEdgeMeshType.tp_basicsize = sizeof(PyHalfEdgeMesh);
    HalfEdgeMeshType.tp_itemsize = 0;
    HalfEdgeMeshType.tp_flags = Py_TPFLAGS_DEFAULT;
    HalfEdgeMeshType.tp_doc = "HalfEdgeMesh([faces,num_points] or empty)";
    HalfEdgeMeshType.tp_new = HalfEdgeMesh_new;
    HalfEdgeMeshType.tp_init = (initproc)HalfEdgeMesh_init;
    HalfEdgeMeshType.tp_dealloc = (destructor)HalfEdgeMesh_dealloc;
    HalfEdgeMeshType.tp_methods = HalfEdgeMesh_methods;

    if (PyType_Ready(&HalfEdgeMeshType) < 0)
    {
        Py_DECREF(m);
        return nullptr;
    }

    Py_INCREF(&HalfEdgeMeshType);
    if (PyModule_AddObject(m, "HalfEdgeMesh", (PyObject*)&HalfEdgeMeshType) < 0)
    {
        Py_DECREF(&HalfEdgeMeshType);
        Py_DECREF(m);
        return nullptr;
    }

    // Build id to confirm correct binary loaded
    PyModule_AddStringConstant(m, "BUILD_ID", "HalfEdgeMesh_v11_add_hedge_prims");

    return m;
}
