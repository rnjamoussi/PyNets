#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  7 10:40:07 2017
Copyright (C) 2018
@author: Derek Pisner & James Kunert-Graf
"""
import numpy as np
import warnings
import os
import networkx as nx
from copy import copy
from pathlib import Path
from collections import Counter
warnings.filterwarnings("ignore")


def countmotifs(A, N=4):
    '''
    Counts number of motifs with size N from A.

    Parameters
    ----------
    A : ndarray
        M x M Connectivity matrix
    N : int
        Size of motif type. Default is N=4, only 3 or 4 supported.

    Returns
    -------
    umotifs : int
        Total count of size N motifs for graph A.
    '''
    import gc
    assert N in [3, 4], "Only motifs of size N=3,4 currently supported"
    X2 = np.array([[k] for k in range(A.shape[0]-1)])
    for n in range(N-1):
        X = copy(X2)
        X2 = []
        for vsub in X:
            # in_matind list of nodes neighboring vsub with a larger index than root v
            idx=np.where(np.any(A[(vsub[0]+1):, vsub], 1))[0]+vsub[0]+1
            # Only keep node indices not in vsub
            idx=idx[[k not in vsub for k in idx]]
            if len(idx)>0:
                # If new neighbors found, add all new vsubs to list
                X2.append([np.append(vsub,ik) for ik in idx])
        if len(X2)>0:
            X2 = np.vstack(X2)
        else:
            umotifs = 0
            return umotifs

    X2 = np.sort(X2,1)
    X2 = X2[np.unique(np.ascontiguousarray(X2).view(np.dtype((np.void,
                                                              X2.dtype.itemsize * X2.shape[1]))),
                      return_index=True)[1]]
    umotifs = Counter([''.join(np.sort(np.sum(A[x, :][:, x],
                                              1)).astype(int).astype(str)) for x in X2])
    del X2
    gc.collect()
    return umotifs


def adaptivethresh(in_mat, thr, mlib, N):
    '''
    Counts number of motifs with a given absolute threshold.

    Parameters
    ----------
    in_mat : ndarray
        M x M Connectivity matrix
    thr : float
        Absolute threshold [0, 1].
    mlib : list
        List of motif classes.

    Returns
    -------
    mf : ndarray
        1D vector listing the total motifs of size N for each
        class of mlib.
    '''
    from pynets.stats.netmotifs import countmotifs
    mf = countmotifs((in_mat > thr).astype(int), N=N)
    try:
        mf = np.array([mf[k] for k in mlib])
    except:
        mf = np.zeros(len(mlib))
    return mf


def compare_motifs(struct_mat, func_mat, name, namer_dir, bins=20, N=4):
    from pynets.stats.netmotifs import adaptivethresh
    from pynets.core.thresholding import threshold_absolute
    from pynets.core.thresholding import standardize
    from scipy import spatial
    from nilearn.connectome import sym_matrix_to_vec
    import pandas as pd
    import gc

    mlib = ['1113', '1122', '1223', '2222', '2233', '3333']

    # Standardize structural graph
    struct_mat = standardize(struct_mat)
    dims_struct = struct_mat.shape[0]
    struct_mat[range(dims_struct), range(dims_struct)] = 0
    at_struct = adaptivethresh(struct_mat, float(0.0), mlib, N)
    print("%s%s%s" % ('Layer 1 (structural) has: ', np.sum(at_struct), ' total motifs'))

    # Functional graph threshold window
    func_mat = standardize(func_mat)
    dims_func = func_mat.shape[0]
    func_mat[range(dims_func), range(dims_func)] = 0
    tmin_func = func_mat.min()
    tmax_func = func_mat.max()
    threshes_func = np.linspace(tmin_func, tmax_func, bins)

    assert np.all(struct_mat == struct_mat.T), "Structural Matrix must be symmetric"
    assert np.all(func_mat == func_mat.T), "Functional Matrix must be symmetric"

    # Count motifs
    print("%s%s%s%s" % ('Mining ', N, '-node motifs: ', mlib))
    motif_dict = {}
    motif_dict['struct'] = {}
    motif_dict['func'] = {}

    mat_dict = {}
    mat_dict['struct'] = sym_matrix_to_vec(struct_mat, discard_diagonal=True)
    mat_dict['funcs'] = {}
    for thr_func in threshes_func:
        # Count
        at_func = adaptivethresh(func_mat, float(thr_func), mlib, N)
        motif_dict['struct']["%s%s" % ('thr-', np.round(thr_func, 4))] = at_struct
        motif_dict['func']["%s%s" % ('thr-', np.round(thr_func, 4))] = at_func
        mat_dict['funcs']["%s%s" % ('thr-', np.round(thr_func, 4))] = sym_matrix_to_vec(threshold_absolute(func_mat,
                                                                                                           thr_func),
                                                                                        discard_diagonal=True)

        print("%s%s%s%s%s" % ('Layer 2 (functional) with absolute threshold of: ',
                              np.round(thr_func, 2), ' yields ',
                              np.sum(at_func), ' total motifs'))
        gc.collect()

    df = pd.DataFrame(motif_dict)

    for idx in range(len(df)):
        df.set_value(df.index[idx], 'motif_dist', spatial.distance.cosine(df['struct'][idx], df['func'][idx]))

    df = df[pd.notnull(df['motif_dist'])]

    for idx in range(len(df)):
        df.set_value(df.index[idx], 'graph_dist_cosine',
                     spatial.distance.cosine(mat_dict['struct'].reshape(-1, 1),
                                             mat_dict['funcs'][df.index[idx]].reshape(-1, 1)))
        df.set_value(df.index[idx], 'graph_dist_correlation',
                     spatial.distance.correlation(mat_dict['struct'].reshape(-1, 1),
                                                  mat_dict['funcs'][df.index[idx]].reshape(-1, 1)))

    df['struct_func_3333'] = np.zeros(len(df))
    df['struct_func_2233'] = np.zeros(len(df))
    df['struct_func_2222'] = np.zeros(len(df))
    df['struct_func_1223'] = np.zeros(len(df))
    df['struct_func_1122'] = np.zeros(len(df))
    df['struct_func_1113'] = np.zeros(len(df))
    df['struct_3333'] = np.zeros(len(df))
    df['func_3333'] = np.zeros(len(df))
    df['struct_2233'] = np.zeros(len(df))
    df['func_2233'] = np.zeros(len(df))
    df['struct_2222'] = np.zeros(len(df))
    df['func_2222'] = np.zeros(len(df))
    df['struct_1223'] = np.zeros(len(df))
    df['func_1223'] = np.zeros(len(df))
    df['struct_1122'] = np.zeros(len(df))
    df['func_1122'] = np.zeros(len(df))
    df['struct_1113'] = np.zeros(len(df))
    df['func_1113'] = np.zeros(len(df))

    for idx in range(len(df)):
        df.set_value(df.index[idx], 'struct_3333', df['struct'][idx][-1])
        df.set_value(df.index[idx], 'func_3333', df['func'][idx][-1])

        df.set_value(df.index[idx], 'struct_2233', df['struct'][idx][-2])
        df.set_value(df.index[idx], 'func_2233', df['func'][idx][-2])

        df.set_value(df.index[idx], 'struct_2222', df['struct'][idx][-3])
        df.set_value(df.index[idx], 'func_2222', df['func'][idx][-3])

        df.set_value(df.index[idx], 'struct_1223', df['struct'][idx][-4])
        df.set_value(df.index[idx], 'func_1223', df['func'][idx][-4])

        df.set_value(df.index[idx], 'struct_1122', df['struct'][idx][-5])
        df.set_value(df.index[idx], 'func_1122', df['func'][idx][-5])

        df.set_value(df.index[idx], 'struct_1113', df['struct'][idx][-6])
        df.set_value(df.index[idx], 'func_1113', df['func'][idx][-6])

    df['struct_func_3333'] = np.abs(df['struct_3333'] - df['func_3333'])
    df['struct_func_2233'] = np.abs(df['struct_2233'] - df['func_2233'])
    df['struct_func_2222'] = np.abs(df['struct_2222'] - df['func_2222'])
    df['struct_func_1223'] = np.abs(df['struct_1223'] - df['func_1223'])
    df['struct_func_1122'] = np.abs(df['struct_1122'] - df['func_1122'])
    df['struct_func_1113'] = np.abs(df['struct_1113'] - df['func_1113'])

    df = df.drop(columns=['struct', 'func'])

    df = df.loc[~(df == 0).all(axis=1)]

    df = df.sort_values(by=['motif_dist', 'graph_dist_cosine', 'graph_dist_correlation', 'struct_func_3333',
                            'struct_func_2233', 'struct_func_2222',
                            'struct_func_1223', 'struct_func_1122', 'struct_func_1113', 'struct_3333', 'func_3333',
                            'struct_2233', 'func_2233', 'struct_2222', 'func_2222', 'struct_1223', 'func_1223',
                            'struct_1122', 'func_1122', 'struct_1113', 'func_1113'],
                        ascending=[True, True, False, False, False, False, False, False, False, False, False, False,
                                   False, False, False, False, False, False, False, False, False])

    # Take the top 25th percentile
    df = df.head(int(0.25*len(df)))
    best_threshes = []
    best_mats = []
    best_multigraphs = []
    for key in list(df.index):
        func_mat_tmp = func_mat.copy()
        struct_mat_tmp = struct_mat.copy()
        struct_thr = float(key.split('-')[-1])
        func_thr = float(key.split('-')[-1])
        best_threshes.append(str(func_thr))

        func_mat_tmp[func_mat_tmp < func_thr] = 0
        struct_mat_tmp[struct_mat_tmp < struct_thr] = 0
        best_mats.append((func_mat_tmp, struct_mat_tmp))

        mG = build_mx_multigraph(func_mat, struct_mat, key, namer_dir)
        best_multigraphs.append(mG)

    mg_dict = dict(zip(best_threshes, best_multigraphs))
    g_dict = dict(zip(best_threshes, best_mats))

    return mg_dict, g_dict


def build_mx_multigraph(func_mat, struct_mat, name, namer_dir):
    import networkx as nx
    import multinetx as mx
    try:
        import cPickle as pickle
    except ImportError:
        import _pickle as pickle

    mg = mx.MultilayerGraph()
    N = struct_mat.shape[0]
    adj_block = mx.lil_matrix(np.zeros((N * 2, N * 2)))
    adj_block[0:  N, N:2 * N] = np.identity(N)
    adj_block += adj_block.T
    G_struct = nx.from_numpy_matrix(struct_mat)
    G_func = nx.from_numpy_matrix(func_mat)
    mg.add_layer(G_struct)
    mg.add_layer(G_func)
    mg.layers_interconnect(inter_adjacency_matrix=adj_block)
    mg.name = name

    # Save mG to pickle
    mG_path = f"{namer_dir}/{name}_mG.pkl"
    nx.write_gpickle(mg, mG_path, protocol=2)

    return mG_path


def motif_matching(paths, ID, atlas, namer_dir, name_list, metadata_list, multigraph_list_all, graph_path_list_all,
                   rsn=None):
    import networkx as nx
    import numpy as np
    import glob
    from pynets.core import thresholding
    from pynets.stats.netmotifs import compare_motifs
    from sklearn.metrics.pairwise import cosine_similarity
    from pynets.stats.netstats import community_resolution_selection
    from graspy.match import GraphMatch as GMP
    try:
        import cPickle as pickle
    except ImportError:
        import _pickle as pickle

    [struct_graph_path, func_graph_path] = paths
    struct_mat = np.load(struct_graph_path)
    func_mat = np.load(func_graph_path)

    if rsn is not None:
        struct_coords_path = glob.glob(f"{str(Path(struct_graph_path).parent.parent)}/nodes/{rsn}_coords*.pkl")[0]
        func_coords_path = glob.glob(f"{str(Path(func_graph_path).parent.parent)}/nodes/{rsn}_coords*.pkl")[0]
        struct_labels_path = glob.glob(f"{str(Path(struct_graph_path).parent.parent)}/nodes/{rsn}_labels*.pkl")[0]
        func_labels_path = glob.glob(f"{str(Path(func_graph_path).parent.parent)}/nodes/{rsn}_labels*.pkl")[0]
    else:
        struct_coords_path = glob.glob(f"{str(Path(struct_graph_path).parent.parent)}/nodes/*coords*.pkl")[0]
        func_coords_path = glob.glob(f"{str(Path(func_graph_path).parent.parent)}/nodes/*coords*.pkl")[0]
        struct_labels_path = glob.glob(f"{str(Path(struct_graph_path).parent.parent)}/nodes/*labels*.pkl")[0]
        func_labels_path = glob.glob(f"{str(Path(func_graph_path).parent.parent)}/nodes/*labels*.pkl")[0]

    with open(struct_coords_path, 'rb') as file_:
        struct_coords = pickle.load(file_)
    with open(func_coords_path, 'rb') as file_:
        func_coords = pickle.load(file_)
    with open(struct_labels_path, 'rb') as file_:
        struct_labels = pickle.load(file_)
    with open(func_labels_path, 'rb') as file_:
        func_labels = pickle.load(file_)

    assert len(struct_coords) == len(func_coords)
    assert len(struct_labels) == len(func_labels)

    if func_mat.shape == struct_mat.shape:
        func_mat[~struct_mat.astype('bool')] = 0
        struct_mat[~func_mat.astype('bool')] = 0
        print("Number of edge disagreements after matching: ", sum(sum(abs(func_mat - struct_mat))))

        metadata = {}
        metadata['coords'] = func_coords
        metadata['labels'] = func_labels
        metadata_list.append(metadata)

        struct_mat = np.maximum(struct_mat, struct_mat.T)
        func_mat = np.maximum(func_mat, func_mat.T)

        # struct_mat = nx.to_numpy_array(sorted(nx.connected_component_subgraphs(nx.from_numpy_matrix(
        #     struct_mat)), key=len, reverse=True)[0])

        struct_mat = thresholding.standardize(struct_mat)

        # func_mat = nx.to_numpy_array(sorted(nx.connected_component_subgraphs(nx.from_numpy_matrix(
        #     func_mat)), key=len, reverse=True)[0])

        func_mat = thresholding.standardize(func_mat)

        struct_node_comm_aff_mat = community_resolution_selection(
            nx.from_numpy_matrix(np.abs(struct_mat)))[1]

        func_node_comm_aff_mat = community_resolution_selection(
            nx.from_numpy_matrix(np.abs(func_mat)))[1]

        struct_comms = []
        for i in np.unique(struct_node_comm_aff_mat):
            struct_comms.append(struct_node_comm_aff_mat == i)

        func_comms = []
        for i in np.unique(func_node_comm_aff_mat):
            func_comms.append(func_node_comm_aff_mat == i)

        sims = cosine_similarity(struct_comms, func_comms)
        struct_comm = struct_comms[np.argmax(sims, axis=0)[0]]
        func_comm = func_comms[np.argmax(sims, axis=0)[0]]

        comm_mask = np.equal.outer(struct_comm, func_comm).astype(bool)
        struct_mat[~comm_mask] = 0
        func_mat[~comm_mask] = 0
        struct_name = struct_graph_path.split('/')[-1].split('_raw.npy')[0]
        func_name = func_graph_path.split('/')[-1].split('_raw.npy')[0]
        name = f"{ID}_{atlas}_mplx_Layer-1_{struct_name}_Layer-2_{func_name}"
        name_list.append(name)
        [mldict, g_dict] = compare_motifs(struct_mat, func_mat, name, namer_dir)
        multigraph_list_all.append(list(mldict.values())[0])
        graph_path_list = []
        for thr in list(g_dict.keys()):
            multigraph_path_list_dict = {}
            [struct, func] = g_dict[thr]
            struct_out = f"{namer_dir}/struct_{atlas}_{struct_name}.npy"
            func_out = f"{namer_dir}/struct_{atlas}_{func_name}_motif-{thr}.npy"
            np.save(struct_out, struct)
            np.save(func_out, func)
            multigraph_path_list_dict[f"struct_{atlas}_{thr}"] = struct_out
            multigraph_path_list_dict[f"func_{atlas}_{thr}"] = func_out
            graph_path_list.append(multigraph_path_list_dict)
        graph_path_list_all.append(graph_path_list)
    else:
        print(f"Skipping {rsn} rsn, since structural and functional graphs are not identical shapes.")

    return name_list, metadata_list, multigraph_list_all, graph_path_list_all


def build_multigraphs(est_path_iterlist, ID):
    """
    Constructs a multimodal multigraph for each available resolution of vertices.

    Parameters
    ----------
    est_path_iterlist : list
        List of file paths to .npy file containing graph.
    ID : str
        A subject id or other unique identifier.

    Returns
    -------
    multigraph_list_all : list
        List of multiplex graph dictionaries corresponding to
        each unique node resolution.
    graph_path_list_top : list
        List of lists consisting of pairs of most similar
        structural and functional connectomes for each unique node resolution.
    """
    import pkg_resources
    import yaml
    import os
    import itertools
    from pathlib import Path
    from pynets.core.utils import flatten
    from pynets.stats.netmotifs import motif_matching

    raw_est_path_iterlist = list(set([i.split('_thrtype')[0] + '_raw.npy' for i in list(flatten(est_path_iterlist))]))

    # Available functional and structural connectivity models
    with open(pkg_resources.resource_filename("pynets", "runconfig.yaml"), 'r') as stream:
        hardcoded_params = yaml.load(stream)
        try:
            func_models = hardcoded_params['available_models']['func_models']
        except KeyError:
            print('ERROR: available functional models not sucessfully extracted from runconfig.yaml')
        try:
            struct_models = hardcoded_params['available_models']['struct_models']
        except KeyError:
            print('ERROR: available structural models not sucessfully extracted from runconfig.yaml')
    stream.close()

    atlases = list(set([x.split('/')[-3].split('/')[0] for x in raw_est_path_iterlist]))
    parcel_dict_func = dict.fromkeys(atlases)
    parcel_dict_dwi = dict.fromkeys(atlases)
    est_path_iterlist_dwi = list(set([i for i in raw_est_path_iterlist if i.split('est-')[1].split('_')[0] in
                                      struct_models]))
    est_path_iterlist_func = list(set([i for i in raw_est_path_iterlist if i.split('est-')[1].split('_')[0] in
                                       func_models]))

    func_subnets = list(set([i.split('_est')[0].split('/')[-1] for i in est_path_iterlist_func]))
    dwi_subnets = list(set([i.split('_est')[0].split('/')[-1] for i in est_path_iterlist_dwi]))

    dir_path = str(Path(os.path.dirname(est_path_iterlist_dwi[0])).parent.parent.parent)
    namer_dir = f"{dir_path}/graphs_multilayer"
    if not os.path.isdir(namer_dir):
        os.mkdir(namer_dir)

    name_list = []
    metadata_list = []
    multigraph_list_all = []
    graph_path_list_all = []
    for atlas in atlases:
        if len(func_subnets) > 1:
            parcel_dict_func[atlas] = {}
            for sub_net in func_subnets:
                parcel_dict_func[atlas][sub_net] = []
        else:
            parcel_dict_func[atlas] = []

        if len(dwi_subnets) > 1:
            parcel_dict_dwi[atlas] = {}
            for sub_net in dwi_subnets:
                parcel_dict_dwi[atlas][sub_net] = []
        else:
            parcel_dict_dwi[atlas] = []

        for graph_path in est_path_iterlist_dwi:
            if atlas in graph_path:
                if len(dwi_subnets) > 1:
                    for sub_net in dwi_subnets:
                        if sub_net in graph_path:
                            parcel_dict_dwi[atlas][sub_net].append(graph_path)
                else:
                    parcel_dict_dwi[atlas].append(graph_path)

        for graph_path in est_path_iterlist_func:
            if atlas in graph_path:
                if len(func_subnets) > 1:
                    for sub_net in func_subnets:
                        if sub_net in graph_path:
                            parcel_dict_func[atlas][sub_net].append(graph_path)
                else:
                    parcel_dict_func[atlas].append(graph_path)

        parcel_dict = {}
        # Create dictionary of all possible pairs of structural-functional graphs for each unique resolution
        # of vertices
        if len(dwi_subnets) > 1 and len(func_subnets) > 1:
            parcel_dict[atlas] = {}
            dwi_subnets.sort(key=lambda x: x.split('_rsn-')[1])
            func_subnets.sort(key=lambda x: x.split('_rsn-')[1])

            for sub_net_dwi, sub_net_func in list(zip(dwi_subnets, func_subnets)):
                rsn = sub_net_dwi.split('_rsn-')[1]
                parcel_dict[atlas][rsn] = list(set(itertools.product(parcel_dict_dwi[atlas][sub_net_dwi],
                                                                     parcel_dict_func[atlas][sub_net_func])))
                for paths in list(parcel_dict[atlas][rsn]):
                    [name_list,
                     metadata_list,
                     multigraph_list_all,
                     graph_path_list_all] = motif_matching(paths, ID, atlas, namer_dir, name_list, metadata_list,
                                                           multigraph_list_all, graph_path_list_all, rsn=rsn)
        else:
            parcel_dict[atlas] = list(set(itertools.product(parcel_dict_dwi[atlas], parcel_dict_func[atlas])))
            for paths in list(parcel_dict[atlas]):
                [name_list,
                 metadata_list,
                 multigraph_list_all,
                 graph_path_list_all] = motif_matching(paths, ID, atlas, namer_dir, name_list, metadata_list,
                                                       multigraph_list_all, graph_path_list_all)

    graph_path_list_top = [list(i[0].values()) for i in graph_path_list_all]
    assert len(multigraph_list_all) == len(name_list) == len(metadata_list)

    return multigraph_list_all, graph_path_list_top, len(name_list)*[namer_dir], name_list, metadata_list
